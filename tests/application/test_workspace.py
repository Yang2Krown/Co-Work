"""Offline lifecycle tests use real composition, parsing, BM25 and memory vector storage."""
import os
import threading
from pathlib import Path
from types import SimpleNamespace
import pytest
from src.application.runtime import Application
from src.application.bootstrap import BackendResources, compose, SafeClient
from src.application.persistence import Database, SQLiteSessionStore
from src.backend.vectorstores.memory_store import InMemoryVectorStore
from src.backend.rag.llm_client import LLMResponse
from src.backend.schemas import RAGStreamEvent
from src.agent.schemas import ToolCall

class Embedding:
    def embed_documents(self, texts):
        return [[1.0, 0.5] for _ in texts]
    def embed_query(self, text):
        return [1.0, 0.5]

class Rerank:
    def rerank(self, query, candidates, top_k=5):
        return [c.model_copy(update={'rank': i}) for i, c in enumerate(candidates[:top_k], 1)]

class LLM:
    model_name = 'deepseek-offline-fixture'
    api_base = 'https://api.deepseek.com'
    api_key_env = 'DEEPSEEK_API_KEY'
    timeout_seconds = 60
    def generate(self, prompt, config):
        return LLMResponse('{"type":"final","answer":"fixture"}', {'total_tokens': 7})
    def stream(self, prompt, config):
        yield '论文'
        yield '回答 [1]'

@pytest.fixture
def factory(tmp_path, monkeypatch):
    import src.agent.integration as integration
    monkeypatch.setattr(integration, 'create_deepseek_client', lambda **kwargs: LLM())
    apps = []
    def create(root=None):
        root = root or tmp_path
        resources = BackendResources(root)
        resources.embedding = Embedding()
        resources.store = InMemoryVectorStore()
        resources.reranker = Rerank()
        app = Application(root, resources=resources)
        apps.append(app)
        return app
    yield create
    for app in apps:
        if app.db.connection:
            try:
                app.close()
            except Exception:
                pass

def wait(app):
    app.executor.submit(lambda: None).result(timeout=10)
    assert not app.busy


def test_import_query_delete_updates_all_indexes(factory):
    app = factory()
    job = app.submit_import([('paper.txt', b'Transformer attention research'), ('bad.pdf', b'not a PDF')])
    wait(app)
    assert app.get_job(job)['status'] == 'partial'
    assert len(app.documents.ready()) == 1
    assert app.agent.llm_client is app.rag.llm_client
    assert app.agent.llm_client.api_base == 'https://api.deepseek.com'
    conversation = app.create_conversation('rag')
    run = app.start_turn(conversation['conversation_id'], 'attention')
    wait(app)
    events = app.read_events(run)
    assert [e['event'] for e in events['events']] == [
        'retrieval_started', 'metadata', 'retrieval_finished', 'llm_started',
        'token', 'token', 'llm_finished', 'end',
    ]
    assert app.read_events(run, events['cursor'])['events'] == []
    answer = app.get_conversation(conversation['conversation_id'])['messages'][-1]
    assert answer['content'] == '论文回答 [1]'
    assert answer['citations'][0]['page_number'] is None
    identifier = app.documents.ready()[0].document_id
    version = app.rag.knowledge_base_version
    app.delete_document(identifier)
    wait(app)
    assert not app.documents.ready()
    assert app.rag.retriever.retrieve('attention') == []
    assert app.resources.store.search([1.0, 0.5]) == []
    assert app.rag.knowledge_base_version != version
    result = app.agent.registry.execute(ToolCall(name='paper_metadata', arguments={'paper_id': identifier}))
    assert not result.ok


def test_duplicate_and_same_name_different_content(factory):
    app = factory()
    job = app.submit_import([('paper.txt', b'one attention'), ('paper.txt', b'two research'), ('duplicate.txt', b'one attention')])
    wait(app)
    assert len(app.documents.ready()) == 2
    assert [i['status'] for i in app.get_job(job)['items']] == ['ready', 'ready', 'skipped']
    assert len({r['path'] for r in app.list_documents()}) == 2


def test_memory_and_history_persist_and_delete(factory, tmp_path):
    app = factory()
    c = app.create_conversation('agent')['conversation_id']
    app.start_turn(c, '3 * 7')
    wait(app)
    assert '21' in app.get_conversation(c)['messages'][-1]['content']
    assert app.memory.get(c).snapshot()
    db2 = Database(tmp_path / 'workspace.sqlite3')
    memory2 = SQLiteSessionStore(db2)
    assert memory2.get(c).snapshot() == app.memory.get(c).snapshot()
    db2.close()
    app.delete_conversation(c)
    assert not app.list_conversations()
    assert not app.db.list('run')
    assert not app.db.list('message')
    assert app.db.get('memory', c) is None


def test_interruption_keeps_partial_and_excludes_duplicate_runs(factory):
    app = factory()
    started, release = threading.Event(), threading.Event()
    def stream(*args, **kwargs):
        yield RAGStreamEvent(event='token', request_id='r', text='partial')
        started.set()
        assert release.wait(5)
    app.rag.stream_answer_events = stream
    c = app.create_conversation('rag')['conversation_id']
    run = app.start_turn(c, 'question')
    assert started.wait(5)
    try:
        with pytest.raises(ValueError, match='尚未结束'):
            app.start_turn(c, 'duplicate')
        with pytest.raises(ValueError):
            app.submit_import([('x.txt', b'data')])
        with pytest.raises(ValueError):
            app.delete_conversation(c)
    finally:
        release.set()
    wait(app)
    assert app.read_events(run)['status'] == 'interrupted'
    assert app.get_conversation(c)['messages'][-1]['content'] == 'partial'
    assert len(app.db.list('run')) == 1


def test_startup_marks_unfinished_tasks(factory, tmp_path):
    app = factory()
    c = app.create_conversation('rag')['conversation_id']
    app.db.put('run', 'lost', {'run_id':'lost', 'conversation_id':c, 'status':'running', 'events':[]})
    another = factory(tmp_path)
    assert another.db.get('run', 'lost')['status'] == 'interrupted'


def test_provider_errors_are_sanitized_before_logging(factory, caplog):
    app = factory()
    def bad(*args, **kwargs):
        raise RuntimeError('401 auth secret-value-should-never-appear')
        yield
    app.rag.llm_client.client.stream = bad
    c = app.create_conversation('rag')['conversation_id']
    run = app.start_turn(c, 'question')
    wait(app)
    assert app.read_events(run)['status'] == 'failed'
    assert 'secret-value' not in str(app.db.list('run')) + caplog.text
    assert '鉴权失败' in app.get_conversation(c)['messages'][-1]['error']


def test_validation_happens_before_writes(factory):
    app = factory()
    for files in [[], [('bad.exe', b'data')], [('empty.txt', b'')], [('x.txt', b'data')]*21]:
        with pytest.raises(ValueError):
            app.submit_import(files)
        assert not app.busy
        assert not app.list_documents()


def test_dirty_deletion_can_be_recovered(factory, monkeypatch):
    app = factory()
    app.submit_import([('paper.txt', b'attention paper')])
    wait(app)
    identifier = app.documents.ready()[0].document_id
    original = app.resources.remove
    monkeypatch.setattr(app.resources, 'remove', lambda doc: (_ for _ in ()).throw(RuntimeError('disk')))
    app.delete_document(identifier)
    wait(app)
    assert app.get_status()['knowledge_base']['dirty']
    monkeypatch.setattr(app.resources, 'remove', original)
    app.repair()
    wait(app)
    assert not app.list_documents()
    assert not app.get_status()['knowledge_base']['dirty']


def test_production_factory_uses_deepseek_without_network(tmp_path, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    app = Application(tmp_path)
    try:
        assert app.agent.llm_client is app.rag.llm_client
        assert app.agent.llm_client.api_key_env == 'DEEPSEEK_API_KEY'
        assert app.agent.llm_client.api_base == 'https://api.deepseek.com'
        c = app.create_conversation('agent')['conversation_id']
        app.start_turn(c, '2 + 2')
        wait(app)
        assert '4' in app.get_conversation(c)['messages'][-1]['content']
    finally:
        app.close()

@pytest.mark.parametrize('code,expected', [('401','鉴权失败'), ('429','限流'), ('timeout','超时')])
def test_safe_client_error_categories(code, expected):
    client = LLM()
    def fail(*args):
        raise RuntimeError(code + ' SECRET')
    client.generate = fail
    with pytest.raises(Exception, match=expected) as exc:
        SafeClient(client).generate(None, None)
    assert 'SECRET' not in str(exc.value)


def test_api_key_is_kept_only_after_successful_verification(factory, monkeypatch):
    app = factory()
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    ok, message = app.verify_api_key('candidate-key')
    assert ok and message == '连接成功'
    assert os.environ['DEEPSEEK_API_KEY'] == 'candidate-key'

    monkeypatch.setenv('DEEPSEEK_API_KEY', 'previous-key')
    monkeypatch.setattr(app.agent.llm_client, 'generate', lambda *args: (_ for _ in ()).throw(RuntimeError('401')))
    ok, message = app.verify_api_key('bad-key')
    assert not ok and '鉴权失败' in message
    assert os.environ['DEEPSEEK_API_KEY'] == 'previous-key'


def test_agent_tool_error_does_not_end_run_early(factory):
    from src.agent.schemas import AgentEvent
    app = factory()
    c = app.create_conversation('agent')['conversation_id']
    def stream(request):
        for name, payload in [
            ('run_started', {}),
            ('tool_finished', {'result': {'tool_name': 'web_search', 'ok': False, 'error': 'disabled'}}),
            ('error', {'kind': 'max_iterations'}),
            ('run_finished', {'result': {'answer':'达到最大推理次数', 'citations':[], 'trace':[], 'token_usage':None, 'status':'max_iterations', 'error':'limit'}}),
        ]:
            yield AgentEvent(event=name, run_id='fixture', session_id=request.session_id, payload=payload)
    app.agent.stream = stream
    run = app.start_turn(c, 'test')
    wait(app)
    assert app.read_events(run)['status'] == 'max_iterations'
    assert len(app.read_events(run)['events']) == 4
    assert app.get_conversation(c)['messages'][-1]['content'] == '达到最大推理次数'


def test_memory_summary_survives_reload(tmp_path):
    db = Database(tmp_path / 'test.sqlite')
    store = SQLiteSessionStore(db)
    with store.locked('s') as memory:
        for i in range(12):
            memory.add('user', 'Message ' + str(i))
        memory.compact(max_tokens=80, trigger_messages=6, keep_messages=2, summarizer=lambda text: 'Prior research summary')
    restored = SQLiteSessionStore(db).get('s')
    assert restored.summary == 'Prior research summary'
    assert len(restored.snapshot()) == 2
    db.close()


def test_upload_size_validation(factory, monkeypatch):
    import src.application.documents as documents
    monkeypatch.setattr(documents, 'MAX_SIZE', 4)
    app = factory()
    with pytest.raises(ValueError, match='50MB'):
        app.submit_import([('x.txt', b'12345')])
    assert not app.list_documents()


def test_http_stream_eof_is_not_success(monkeypatch):
    from src.backend.rag.llm_client import OpenAICompatibleClient, GenerationConfig
    from src.backend.rag.prompt import RAGPrompt
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n'
    client = OpenAICompatibleClient('test', 'https://api.deepseek.com')
    monkeypatch.setattr(client, '_request', lambda *a, **kw: Response())
    stream = client.stream(RAGPrompt(system='test', user='test'), GenerationConfig())
    assert next(stream) == 'partial'
    with pytest.raises(Exception, match='before completion'):
        next(stream)


def test_failed_index_retry_is_idempotent(factory, monkeypatch):
    app = factory()
    original = app.resources.assemble
    broken = [True]
    def assemble(documents):
        if documents and broken[0]:
            broken[0] = False
            raise RuntimeError('model temporarily unavailable')
        return original(documents)
    monkeypatch.setattr(app.resources, 'assemble', assemble)
    job = app.submit_import([('paper.txt', b'attention research')])
    wait(app)
    assert app.get_job(job)['status'] == 'partial'
    identifier = app.get_job(job)['items'][0]['document_id']
    retry = app.retry_import(job, [identifier])
    wait(app)
    assert app.get_job(retry)['status'] == 'completed'
    assert len(app.documents.ready()) == 1
    assert len(app.rag.retriever.retrieve('attention')) == 1
