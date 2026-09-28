"""Thread-safe SQLite records and durable Agent conversation memory."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from src.agent.memory import ConversationMemory, InMemorySessionStore

class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id))')
        self.connection.commit()

    def put(self, kind, identifier, value):
        if hasattr(value, 'model_dump'):
            value = value.model_dump(mode='json')
        with self.lock, self.connection:
            self.connection.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (kind, identifier, json.dumps(value, ensure_ascii=False)))

    def get(self, kind, identifier):
        with self.lock:
            row = self.connection.execute('SELECT payload FROM records WHERE kind=? AND id=?', (kind, identifier)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind):
        with self.lock:
            rows = self.connection.execute('SELECT payload FROM records WHERE kind=? ORDER BY rowid', (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def delete(self, kind, identifier):
        with self.lock, self.connection:
            self.connection.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, identifier))

    def close(self):
        with self.lock:
            self.connection.close()

class DurableMemory(ConversationMemory):
    @classmethod
    def restore(cls, session_id, value):
        memory = cls(session_id)
        if value:
            for item in value.get('messages', []):
                memory.add(item['role'], item['content'], item.get('name'))
            memory._summary = value.get('summary')
        return memory

class SQLiteSessionStore(InMemorySessionStore):
    def __init__(self, db):
        super().__init__()
        self.db = db

    def get(self, session_id):
        if not session_id.strip():
            raise ValueError('session_id must not be blank')
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = DurableMemory.restore(session_id, self.db.get('memory', session_id))
            return self._sessions[session_id]

    @contextmanager
    def locked(self, session_id):
        memory = self.get(session_id)
        with memory.lock:
            try:
                yield memory
            finally:
                self.db.put('memory', session_id, {'summary': memory.summary, 'messages': [m.as_dict() for m in memory.snapshot()]})

    def clear(self, session_id):
        super().clear(session_id)
        self.db.delete('memory', session_id)
