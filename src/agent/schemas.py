"""Public Agent request, trace, tool, and transport schemas.

The Agent layer deliberately keeps these schemas independent from the private
implementation details of ``src.backend``.  The only backend-shaped value that
crosses the boundary is a normalized citation reference.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentRequest(_SchemaModel):
    """One user turn sent to the Agent."""

    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8000)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("session_id", "message")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class CitationRef(_SchemaModel):
    """A citation copied from a backend RAG result."""

    citation_id: int = Field(ge=1)
    file_name: str = Field(min_length=1)
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None


class ToolCall(_SchemaModel):
    """A single model-requested tool invocation."""

    call_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    name: str = Field(min_length=1, max_length=128)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(_SchemaModel):
    """A safe, serializable observation returned to the ReAct loop."""

    tool_name: str
    call_id: Optional[str] = None
    ok: bool
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = Field(default=0.0, ge=0.0)
    citations: List[CitationRef] = Field(default_factory=list)
    token_usage: Optional[Dict[str, Any]] = None


class AgentTraceStep(_SchemaModel):
    """One Thought -> Action -> Observation step."""

    step_index: int = Field(ge=0)
    thought: str = ""
    calls: List[ToolCall] = Field(default_factory=list)
    observations: List[ToolResult] = Field(default_factory=list)
    latency_ms: float = Field(default=0.0, ge=0.0)
    status: Literal["completed", "failed", "repeated", "timeout"] = "completed"
    token_usage: Optional[Dict[str, Any]] = None


class AgentEvent(_SchemaModel):
    """Transport-neutral event used by the Python and SSE interfaces."""

    event: Literal[
        "run_started",
        "route_selected",
        "llm_started",
        "llm_finished",
        "retrieval_started",
        "retrieval_finished",
        "thought",
        "tool_started",
        "tool_finished",
        "answer_token",
        "final",
        "error",
        "run_finished",
    ]
    run_id: str
    session_id: str
    step_index: Optional[int] = None
    tool_name: Optional[str] = None
    sequence: int = Field(default=0, ge=0)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(_SchemaModel):
    """Final result returned by ``AgentService.run``."""

    run_id: str
    session_id: str
    answer: str
    citations: List[CitationRef] = Field(default_factory=list)
    trace: List[AgentTraceStep] = Field(default_factory=list)
    iterations: int = Field(default=0, ge=0)
    status: Literal["completed", "failed", "max_iterations"]
    token_usage: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def to_jsonable(value: Any) -> Any:
    """Convert Pydantic models recursively without leaking implementation objects."""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


__all__ = [
    "AgentEvent",
    "AgentRequest",
    "AgentRunResult",
    "AgentTraceStep",
    "CitationRef",
    "ToolCall",
    "ToolResult",
    "to_jsonable",
]
