"""Typed data structures for document, retrieval, and RAG boundaries."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Document(_SchemaModel):
    document_id: str
    file_name: str
    file_type: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Chunk(_SchemaModel):
    chunk_id: str
    document_id: str
    text: str
    page_number: Optional[int] = None
    file_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(_SchemaModel):
    chunk_id: str
    text: str
    document_id: str
    file_name: str
    page_number: Optional[int] = None
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None
    rank: int = Field(ge=1)


class Citation(_SchemaModel):
    """A citation that can be traced to a retrieved chunk."""

    citation_id: int = Field(ge=1)
    file_name: str
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None


class RAGResponse(_SchemaModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    retrieved_chunks: List[RetrievalResult] = Field(default_factory=list)
    latency_ms: float = Field(ge=0)
    token_usage: Optional[Dict[str, Any]] = None
    fallback_used: bool = False
    error: Optional[str] = None


class RAGStreamEvent(_SchemaModel):
    """Structured, transport-neutral event emitted by RAG streaming."""

    event: Literal["metadata", "token", "end", "error"]
    request_id: str
    text: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
    retrieved_chunks: List[RetrievalResult] = Field(default_factory=list)
    error: Optional[str] = None


__all__ = [
    "Citation",
    "Chunk",
    "Document",
    "RAGResponse",
    "RAGStreamEvent",
    "RetrievalResult",
]
