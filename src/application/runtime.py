"""Exclusive background operations, persistent events, and the frontend facade."""
import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from src.agent.schemas import AgentRequest
from .bootstrap import BackendResources, EmptyRetriever, compose, friendly_error, local_dependency_error
from .contracts import ImportJob, MessageRecord, RunRecord
from .conversations import Conversations, now
from .documents import Documents
from .persistence import Database, SQLiteSessionStore

class Application:
    def __init__(self, root, resources=None, composer=compose):
        self.root = Path(root)
        self.db = Database(self.root / 'workspace.sqlite3')
        self.memory = SQLiteSessionStore(self.db)
        self.conversations = Conversations(self.db, self.memory)
        self.resources = resources or BackendResources(root)
        self.composer = composer
        self.documents = Documents(self.db, root, self.resources)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cowork')
        self.gate = threading.RLock()
        self.busy = False
        self.operation = None
        self.loaded = not bool(self.documents.list())
        self.agent, self.rag = self.composer(EmptyRetriever(), [], self.memory, 'empty', None)
        for kind in ('run', 'message', 'job'):
            for item in self.db.list(kind):
                if item.get('status') in ('queued', 'running'):
                    item.update(status='interrupted', error='进程重启，任务未完成，请主动重试。')
                    self.db.put(kind, item[kind + '_id'], item)

    def _reserve(self, name):
        if self.busy:
            raise ValueError('当前任务尚未结束，请完成后再操作。')
        self.busy, self.operation = True, name

    def _submit(self, callback):
        def worker():
            try:
                callback()
            finally:
                with self.gate:
                    self.busy, self.operation = False, None
        try:
            self.executor.submit(worker)
        except Exception:
            self.busy, self.operation = False, None
            raise

    def _refresh(self):
        documents = self.documents.ready()
        retriever = self.resources.assemble(documents)
        version = hashlib.sha256('|'.join(sorted(d.document_id for d in documents)).encode()).hexdigest()[:16]
        agent, rag = self.composer(retriever, documents, self.memory, version, self.resources.embedding)
        # Keep process metrics across KB snapshots.
        if hasattr(agent, 'metrics') and hasattr(self.agent, 'metrics'):
            agent.metrics = self.agent.metrics
        self.agent, self.rag = agent, rag
        self.loaded = True
        self.db.put('meta', 'kb', {'dirty': False, 'version': version})

    def _ensure(self):
        if not self.loaded or (self.db.get('meta', 'kb') or {}).get('dirty'):
            self.documents.recover(self._refresh)

    def list_documents(self):
        return self.documents.list()

    def submit_import(self, files):
        with self.gate:
            self._reserve('导入文档')
            try:
                job = self.documents.stage(files)
                def work():
                    try:
                        self._ensure()
                        self.documents.import_job(job, self._refresh)
                    except Exception:
                        job.status, job.error = 'failed', '导入未完成，请修复知识库后重试。'
                        for item in job.items:
                            if item['status'] == 'pending':
                                item.update(status='failed', error=job.error)
                                record = self.db.get('document', item['document_id'])
                                if record:
                                    record.update(status='failed', error=job.error)
                                    self.db.put('document', item['document_id'], record)
                        self.db.put('job', job.job_id, job)
                        self.db.put('meta', 'kb', {'dirty': True})
                self._submit(work)
                return job.job_id
            except Exception:
                self.busy, self.operation = False, None
                raise

    def get_job(self, job_id):
        return self.db.get('job', job_id)

    def retry_import(self, job_id, document_ids):
        job = self.get_job(job_id)
        if not job or not document_ids:
            raise ValueError('请选择失败文件')
        allowed = {i['document_id'] for i in job['items'] if i['status'] == 'failed'}
        if not set(document_ids) <= allowed:
            raise ValueError('只能重试该任务中失败的文件')
        files = []
        for identifier in document_ids:
            record = self.db.get('document', identifier)
            if not record:
                raise ValueError('原文件已删除，请重新上传')
            files.append((record['file_name'], Path(record['path']).read_bytes()))
        return self.submit_import(files)

    def delete_document(self, identifier):
        with self.gate:
            self._reserve('删除文档')
            job = ImportJob(job_id=str(uuid4()), total=1, stage='删除与同步索引')
            self.db.put('job', job.job_id, job)
            def work():
                try:
                    self.documents.delete(identifier, self._refresh)
                    job.status, job.completed, job.stage = 'completed', 1, '删除完成'
                except Exception:
                    job.status, job.error = 'failed', '删除未完成，知识库需要修复。'
                    self.db.put('meta', 'kb', {'dirty': True})
                self.db.put('job', job.job_id, job)
            self._submit(work)
            return job.job_id

    def repair(self):
        with self.gate:
            self._reserve('修复知识库')
            job = ImportJob(job_id=str(uuid4()), total=1, stage='恢复知识库')
            self.db.put('job', job.job_id, job)
            def work():
                try:
                    self.db.put('meta', 'kb', {'dirty': True})
                    self.documents.recover(self._refresh, force=True)
                    job.status, job.completed, job.stage = 'completed', 1, '修复完成'
                except Exception:
                    job.status, job.error = 'failed', '恢复失败，请检查本地模型和文件。'
                    self.db.put('meta', 'kb', {'dirty': True})
                self.db.put('job', job.job_id, job)
            self._submit(work)
            return job.job_id

    def create_conversation(self, mode):
        return self.conversations.create(mode)

    def list_conversations(self):
        return self.conversations.list()

    def get_conversation(self, identifier):
        return self.conversations.get(identifier)

    def delete_conversation(self, identifier):
        with self.gate:
            if self.busy:
                raise ValueError('任务进行中，暂时不能删除会话。')
            self.conversations.delete(identifier)

    def start_turn(self, conversation_id, message, metadata=None):
        request = AgentRequest(session_id=conversation_id, message=message, metadata=metadata or {})
        with self.gate:
            conversation = self.get_conversation(conversation_id)
            self._reserve('生成回答')
            try:
                run = RunRecord(run_id=str(uuid4()), conversation_id=conversation_id, mode=conversation['mode'], created_at=now(), metadata=request.metadata)
                user = MessageRecord(message_id=str(uuid4()), conversation_id=conversation_id, run_id=run.run_id,
                    role='user', content=request.message, status='completed', created_at=now())
                answer = MessageRecord(message_id=str(uuid4()), conversation_id=conversation_id, run_id=run.run_id,
                    role='assistant', created_at=now())
                for kind, item in [('run', run), ('message', user), ('message', answer)]:
                    self.db.put(kind, getattr(item, kind + '_id'), item)
                if not conversation['messages']:
                    conversation.pop('messages')
                    conversation['title'] = request.message[:28]
                    self.db.put('conversation', conversation_id, conversation)
                self._submit(lambda: self._turn(run, answer, request))
                return run.run_id
            except Exception:
                self.busy, self.operation = False, None
                raise

    def _turn(self, run, answer, request):
        started = perf_counter()
        terminal = False
        run.status = 'running'
        try:
            self._ensure()
            stream = self.rag.stream_answer_events(request.message, top_k=5) if run.mode == 'rag' else self.agent.stream(request)
            for event in stream:
                data = event.model_dump(mode='json')
                run.events.append(data)
                name = data['event']
                if run.mode == 'rag':
                    if name == 'metadata':
                        answer.citations = data['citations']
                        answer.retrieved_chunks = data['retrieved_chunks']
                    elif name == 'token':
                        answer.content += data.get('text') or ''
                    elif name == 'error':
                        answer.error = data.get('error') or '生成中断，请重试。'
                    elif name == 'end':
                        terminal = True
                        answer.error = data.get('error') or answer.error
                        answer.status = 'failed' if answer.error else 'completed'
                else:
                    payload = data.get('payload', {})
                    if name == 'final':
                        answer.content = payload.get('answer', '')
                        answer.citations = payload.get('citations', [])
                    elif name == 'tool_finished':
                        result = payload.get('result', {})
                        observation = result.get('data')
                        if isinstance(observation, dict):
                            answer.retrieved_chunks.extend(observation.get('retrieved_chunks') or [])
                    elif name == 'run_finished':
                        result = payload['result']
                        terminal = True
                        for field in ('answer', 'citations', 'trace', 'token_usage', 'error', 'status'):
                            setattr(answer, 'content' if field == 'answer' else field, result.get(field))
                self.db.put('run', run.run_id, run)
                self.db.put('message', answer.message_id, answer)
            if not terminal:
                answer.status, answer.error = 'interrupted', '连接中断，回答未完成，请主动重试。'
        except Exception as exc:
            answer.status, answer.error = 'failed', friendly_error(exc)
        finally:
            answer.latency_ms = (perf_counter() - started) * 1000
            run.status, run.error = answer.status, answer.error
            self.db.put('message', answer.message_id, answer)
            self.db.put('run', run.run_id, run)

    def read_events(self, run_id, cursor=0):
        run = self.db.get('run', run_id)
        if not run:
            raise ValueError('运行不存在')
        if cursor < 0 or cursor > len(run['events']):
            raise ValueError('无效事件游标')
        return {'events': run['events'][cursor:], 'cursor': len(run['events']), 'status': run['status'], 'error': run['error']}

    def get_status(self):
        return {'provider': 'DeepSeek API', 'model': self.agent.llm_client.model_name,
            'llm': '已配置，未验证连接' if os.getenv('DEEPSEEK_API_KEY') else '未配置 DEEPSEEK_API_KEY',
            'knowledge_base': self.db.get('meta', 'kb') or {'dirty': False, 'version': 'empty'},
            'runtime_loaded': self.loaded, 'busy': self.busy, 'operation': self.operation,
            'web_search': '未启用', 'metrics': self.agent.metrics.snapshot(),
            'probe': self.db.get('meta', 'probe')}

    def verify_api_key(self, api_key=None):
        """Verify a candidate key before exposing the workspace."""
        candidate = (api_key or os.getenv('DEEPSEEK_API_KEY', '')).strip()
        if not candidate:
            return False, '请输入 DeepSeek API Key。'
        previous = os.getenv('DEEPSEEK_API_KEY')
        os.environ['DEEPSEEK_API_KEY'] = candidate
        try:
            from src.backend.rag.prompt import RAGPrompt
            from src.backend.rag import GenerationConfig
            self.agent.llm_client.generate(
                RAGPrompt(system='Reply with OK only.', user='Connection check'),
                GenerationConfig(temperature=0, max_output_tokens=128),
            )
        except Exception as exc:
            if previous is None:
                os.environ.pop('DEEPSEEK_API_KEY', None)
            else:
                os.environ['DEEPSEEK_API_KEY'] = previous
            return False, friendly_error(exc)
        self.db.delete('meta', 'probe')
        return True, '连接成功'

    def clear_api_key(self):
        os.environ.pop('DEEPSEEK_API_KEY', None)
        self.db.delete('meta', 'probe')

    def probe_dependencies(self):
        with self.gate:
            self._reserve('检查服务连接')
            def work():
                from src.backend.rag.prompt import RAGPrompt
                from src.backend.rag import GenerationConfig
                result = {'checked_at': now()}
                try:
                    self.agent.llm_client.generate(RAGPrompt(system='Reply OK.', user='Connectivity check'), GenerationConfig(max_output_tokens=128))
                    result['llm'] = {'ok': True, 'message': 'DeepSeek API 连接成功'}
                except Exception as exc:
                    result['llm'] = {'ok': False, 'message': friendly_error(exc)}
                try:
                    self._ensure()
                    if self.documents.ready():
                        self.rag.retriever.retrieve('connection check', top_k=1)
                        result['retrieval'] = {'ok': True, 'message': '本地检索检查通过'}
                    else:
                        result['retrieval'] = {'ok': None, 'message': '知识库为空，未验证本地检索'}
                except Exception as exc:
                    result['retrieval'] = {'ok': False, 'message': local_dependency_error(exc)}
                self.db.put('meta', 'probe', result)
            self._submit(work)

    def close(self):
        self.executor.shutdown(wait=True)
        self.db.close()
