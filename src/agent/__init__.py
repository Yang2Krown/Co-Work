"""Co-Work Agent module public API."""

from .api import create_app
from .config import AgentConfig, AgentLLMConfig, load_agent_config
from .integration import (
    build_agent_service,
    build_deepseek_agent_service,
    build_deepseek_rag_agent_service,
    build_paper_summary_callback,
    build_summary_callback,
    create_agent_app,
    create_deepseek_client,
    paper_catalog_from_documents,
)
from .memory import (
    ConversationMemory,
    InMemorySessionStore,
    MemoryMessage,
    SessionStore,
    estimate_tokens,
)
from .observability import AgentMetrics
from .router import IntentRouter, RouteDecision
from .schemas import (
    AgentEvent,
    AgentRequest,
    AgentRunResult,
    AgentTraceStep,
    CitationRef,
    ToolCall,
    ToolResult,
)
from .service import AgentService
from .tools import (
    InMemoryPaperCatalog,
    PaperRecord,
    ToolRegistry,
    ToolSpec,
    build_default_tool_registry,
)

__all__ = [
    "AgentConfig",
    "AgentLLMConfig",
    "AgentEvent",
    "AgentRequest",
    "AgentRunResult",
    "AgentService",
    "AgentMetrics",
    "AgentTraceStep",
    "CitationRef",
    "ConversationMemory",
    "InMemoryPaperCatalog",
    "InMemorySessionStore",
    "IntentRouter",
    "MemoryMessage",
    "PaperRecord",
    "RouteDecision",
    "SessionStore",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "build_default_tool_registry",
    "build_agent_service",
    "build_deepseek_agent_service",
    "build_deepseek_rag_agent_service",
    "build_paper_summary_callback",
    "build_summary_callback",
    "create_app",
    "create_agent_app",
    "create_deepseek_client",
    "estimate_tokens",
    "load_agent_config",
    "paper_catalog_from_documents",
]
