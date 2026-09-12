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
from .prompt import RAGPrompt, build_prompt
from .service import RAGService

__all__ = [
    "ContextBuildResult",
    "ContextBuilder",
    "GenerationConfig",
    "LLMClient",
    "LLMResponse",
    "OpenAICompatibleClient",
    "RAGPrompt",
    "RAGService",
    "build_citations",
    "build_context",
    "build_prompt",
    "create_llm_client",
]
