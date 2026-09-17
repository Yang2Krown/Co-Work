"""Application-owned records; backend and Agent contracts remain unchanged."""
from typing import Any, Literal
from pydantic import BaseModel, Field

Mode = Literal['rag', 'agent']

class DocumentRecord(BaseModel):
    document_id: str
    file_name: str
    size: int
    path: str
    status: Literal['pending', 'processing', 'ready', 'failed', 'deleting'] = 'pending'
    chunk_count: int = 0
    error: str | None = None
    document: dict[str, Any] | None = None

class ImportJob(BaseModel):
    job_id: str
    status: str = 'queued'
    stage: str = '等待处理'
    total: int = 0
    completed: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None

class Conversation(BaseModel):
    conversation_id: str
    mode: Mode
    title: str = '新会话'
    created_at: str

class MessageRecord(BaseModel):
    message_id: str
    conversation_id: str
    run_id: str
    role: Literal['user', 'assistant']
    content: str = ''
    status: str = 'running'
    citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float | None = None
    created_at: str

class RunRecord(BaseModel):
    run_id: str
    conversation_id: str
    mode: Mode
    status: str = 'queued'
    events: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str
