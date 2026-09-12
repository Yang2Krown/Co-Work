"""Retrieval-augmented generation components."""

from .citation import build_citations
from .context_builder import ContextBuildResult, ContextBuilder, build_context
from .llm_client import (
    GenerationConfig,
    LLMClient,
    LLMResponse,
    OpenAICompatibleClient,
    create_llm_client,
)
from .cache import EmbeddingFunction, SemanticCache
from .observability import (
    StructuredJSONFormatter,
    configure_structured_logging,
    log_rag_request,
)
from .prompt import RAGPrompt, build_prompt
from .service import RAGService

__all__ = [
    "ContextBuildResult",
    "ContextBuilder",
    "EmbeddingFunction",
    "GenerationConfig",
    "LLMClient",
    "LLMResponse",
    "OpenAICompatibleClient",
    "RAGPrompt",
    "RAGService",
    "SemanticCache",
    "StructuredJSONFormatter",
    "build_citations",
    "build_context",
    "build_prompt",
    "create_llm_client",
    "configure_structured_logging",
    "log_rag_request",
]
