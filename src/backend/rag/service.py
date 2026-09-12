"""RAG orchestration over the existing retrieval and LLM boundaries."""

from time import perf_counter
from typing import Iterator, Optional, Protocol

from ..schemas import RAGResponse, RetrievalResult
from .citation import build_citations
from .context_builder import ContextBuildResult, ContextBuilder
from .llm_client import GenerationConfig, LLMClient
from .prompt import RAGPrompt, build_prompt


class RetrieverLike(Protocol):
    def retrieve(
        self,
        query: str,
        mode: str = "hybrid_rerank",
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Retrieve final ranked chunks."""


class RAGService:
    """Answer questions using bounded retrieved context and citations."""

    def __init__(
        self,
        retriever: RetrieverLike,
        llm_client: LLMClient,
        generation_config: Optional[GenerationConfig] = None,
        retrieval_mode: str = "hybrid_rerank",
        default_top_k: int = 5,
        context_builder: Optional[ContextBuilder] = None,
    ) -> None:
        if default_top_k <= 0:
            raise ValueError("default_top_k must be greater than zero")
        self.retriever = retriever
        self.llm_client = llm_client
        self.generation_config = generation_config or GenerationConfig()
        self.retrieval_mode = retrieval_mode
        self.default_top_k = default_top_k
        self.context_builder = context_builder or ContextBuilder()

    def _prepare(
        self,
        question: str,
        top_k: Optional[int],
    ) -> tuple[ContextBuildResult, RAGPrompt]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        effective_top_k = self.default_top_k if top_k is None else top_k
        if effective_top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        results = self.retriever.retrieve(
            question,
            mode=self.retrieval_mode,
            top_k=effective_top_k,
        )
        context = self.context_builder.build(results)
        return context, build_prompt(question, context.text)

    def answer(self, question: str, top_k: Optional[int] = None) -> RAGResponse:
        """Return an answer, exact retrieved chunks, and traceable citations."""

        started = perf_counter()
        context, prompt = self._prepare(question, top_k)
        generated = self.llm_client.generate(prompt, self.generation_config)
        if not generated.text.strip():
            raise ValueError("LLM returned an empty answer")
        return RAGResponse(
            answer=generated.text,
            citations=build_citations(context.chunks),
            retrieved_chunks=context.chunks,
            latency_ms=(perf_counter() - started) * 1000,
            token_usage=generated.token_usage,
        )

    def stream_answer(self, question: str, top_k: Optional[int] = None) -> Iterator[str]:
        """Yield answer fragments after retrieval and prompt construction."""

        _, prompt = self._prepare(question, top_k)
        yield from self.llm_client.stream(prompt, self.generation_config)


__all__ = ["RAGService", "RetrieverLike"]
