from datetime import datetime, timezone
from uuid import uuid4
from .contracts import Conversation

def now():
    return datetime.now(timezone.utc).isoformat()

class Conversations:
    def __init__(self, db, memory):
        self.db, self.memory = db, memory

    def create(self, mode):
        item = Conversation(conversation_id=str(uuid4()), mode=mode, created_at=now())
        self.db.put('conversation', item.conversation_id, item)
        return item.model_dump()

    def list(self):
        return sorted(self.db.list('conversation'), key=lambda x: x['created_at'], reverse=True)

    def get(self, identifier):
        result = self.db.get('conversation', identifier)
        if result is None:
            raise ValueError('会话不存在')
        result['messages'] = sorted([m for m in self.db.list('message') if m['conversation_id'] == identifier], key=lambda m: m['created_at'])
        return result

    def delete(self, identifier):
        self.get(identifier)
        for kind in ('message', 'run'):
            for item in self.db.list(kind):
                if item['conversation_id'] == identifier:
                    self.db.delete(kind, item[kind + '_id'])
        self.memory.clear(identifier)
        self.db.delete('conversation', identifier)
