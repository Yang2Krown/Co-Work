"""Document lifecycle; called only under the application's exclusive operation gate."""
import hashlib
from pathlib import Path
from uuid import uuid4
from src.backend.loaders import load_file
from src.backend.schemas import Document
from .contracts import DocumentRecord, ImportJob

ALLOWED = {'.pdf', '.docx', '.txt', '.md'}
MAX_SIZE = 50 * 1024 * 1024

class Documents:
    def __init__(self, db, root, resources):
        self.db, self.root, self.resources = db, Path(root), resources
        (self.root / 'raw').mkdir(parents=True, exist_ok=True)

    def list(self):
        return self.db.list('document')

    def ready(self):
        return [Document.model_validate(r['document']) for r in self.list() if r['status'] == 'ready']

    def stage(self, files):
        if not 1 <= len(files) <= 20:
            raise ValueError('每批请选择 1–20 个文件')
        # Validate the whole envelope before writing any file.
        for name, content in files:
            if Path(name).suffix.lower() not in ALLOWED:
                raise ValueError('仅支持 PDF、DOCX、TXT、Markdown')
            if not content or len(content) > MAX_SIZE:
                raise ValueError('文件不能为空，且每个文件不得超过 50MB')
        job = ImportJob(job_id=str(uuid4()), total=len(files))
        seen = set()
        for name, content in files:
            name = Path(name.replace('\\', '/')).name
            identifier = hashlib.sha256(content).hexdigest()
            existing = self.db.get('document', identifier)
            if identifier in seen or (existing and existing['status'] == 'ready'):
                job.items.append({'document_id': identifier, 'file_name': name, 'status': 'skipped'})
                continue
            seen.add(identifier)
            folder = self.root / 'raw' / identifier
            folder.mkdir(exist_ok=True)
            path = folder / name
            path.write_bytes(content)
            record = DocumentRecord(document_id=identifier, file_name=name, size=len(content), path=str(path), document=existing.get('document') if existing else None)
            self.db.put('document', identifier, record)
            job.items.append({'document_id': identifier, 'file_name': name, 'status': 'pending'})
        self.db.put('job', job.job_id, job)
        return job

    def import_job(self, job, refresh):
        job.status = 'running'
        for item in job.items:
            if item['status'] == 'skipped':
                job.completed += 1
                self.db.put('job', job.job_id, job)
                continue
            identifier = item['document_id']
            record = self.db.get('document', identifier)
            try:
                job.stage = '解析文档 · ' + record['file_name']
                record.update(status='processing', error=None)
                self.db.put('document', identifier, record)
                self.db.put('job', job.job_id, job)
                document = load_file(record['path'])
                if not document.text.strip():
                    raise ValueError('empty text')
                record['document'] = document.model_dump(mode='json')
                job.stage = '分块与向量化 · ' + record['file_name']
                self.db.put('job', job.job_id, job)
                self.db.put('meta', 'kb', {'dirty': True})
                record.update(status='ready', chunk_count=self.resources.chunk_count(document))
                self.db.put('document', identifier, record)
                refresh()
                item['status'] = 'ready'
            except Exception as exc:
                record.update(status='failed', error=self.resources.user_error(exc))
                item.update(status='failed', error=record['error'])
                self.db.put('document', identifier, record)
                # A failed upsert may have written vectors. Remove before exposing any new snapshot.
                try:
                    if record.get('document'):
                        self.resources.remove(Document.model_validate(record['document']))
                    refresh()
                except Exception:
                    self.db.put('meta', 'kb', {'dirty': True})
            job.completed += 1
            self.db.put('job', job.job_id, job)
        job.status = 'partial' if any(i['status'] == 'failed' for i in job.items) else 'completed'
        job.stage = '部分文件失败' if job.status == 'partial' else '处理完成'
        self.db.put('job', job.job_id, job)

    def delete(self, identifier, refresh):
        record = self.db.get('document', identifier)
        if record is None:
            raise ValueError('文档不存在')
        record['status'] = 'deleting'
        self.db.put('document', identifier, record)
        self.db.put('meta', 'kb', {'dirty': True})
        if record.get('document'):
            self.resources.remove(Document.model_validate(record['document']))
        refresh()
        Path(record['path']).unlink(missing_ok=True)
        self.db.delete('document', identifier)

    def recover(self, refresh, force=False):
        if force or (self.db.get('meta', 'kb') or {}).get('dirty'):
            self.resources.reset_manifest()
        # Finish interrupted deletion, and remove vectors from incomplete imports.
        for record in self.list():
            if record['status'] in {'processing', 'pending', 'failed', 'deleting'}:
                if record.get('document'):
                    self.resources.remove(Document.model_validate(record['document']))
                if record['status'] == 'deleting':
                    Path(record['path']).unlink(missing_ok=True)
                    self.db.delete('document', record['document_id'])
                else:
                    record.update(status='failed', error='上次处理未完成，可重试导入。')
                    self.db.put('document', record['document_id'], record)
        refresh()
