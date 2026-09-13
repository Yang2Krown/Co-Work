"""RAG orchestration with semantic caching, fallback, and request logging."""

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Iterator, List, Optional, Protocol, Tuple
from uuid import uuid4

from ..exceptions import LLMServiceError
from ..schemas import RAGResponse, RAGStreamEvent, RetrievalResult
from .cache import SemanticCache
from .citation import build_citations
from .context_builder import ContextBuildResult, ContextBuilder
from .llm_client import GenerationConfig, LLMClient
from .observability import log_rag_request
from .prompt import RAGPrompt, build_prompt


class RetrieverLike(Protocol):
    def retrieve(
        self,
        query: str,
        mode: str = "hybrid_rerank",
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Retrieve final ranked chunks."""


class RAGService:
    """Answer questions with bounded context and M6 runtime safeguards."""

    def __init__(
        self,
        retriever: RetrieverLike,
        llm_client: LLMClient,
        generation_config: Optional[GenerationConfig] = None,
        retrieval_mode: str = "hybrid_rerank",
        default_top_k: int = 5,
        context_builder: Optional[ContextBuilder] = None,
        cache: Optional[SemanticCache] = None,
        knowledge_base_version: str = "default",
        allow_llm_fallback: bool = True,
        low_relevance_threshold: float = 0.2,
        low_relevance_score_source: str = "vector",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if default_top_k <= 0:
            raise ValueError("default_top_k must be greater than zero")
        if low_relevance_threshold < 0:
            raise ValueError("low_relevance_threshold must be non-negative")
        if low_relevance_score_source != "vector":
            raise ValueError("low_relevance_score_source must be 'vector'")
        self.retriever = retriever
        self.llm_client = llm_client
        self.generation_config = generation_config or GenerationConfig()
        self.retrieval_mode = retrieval_mode
        self.default_top_k = default_top_k
        self.context_builder = context_builder or ContextBuilder()
        self.cache = cache
        self.knowledge_base_version = knowledge_base_version
        self.allow_llm_fallback = allow_llm_fallback
        self.low_relevance_threshold = low_relevance_threshold
        self.low_relevance_score_source = low_relevance_score_source
        self.logger = logger or logging.getLogger("backend.rag")

    @staticmethod
    def _score(result: RetrievalResult) -> Optional[float]:
        # The threshold is deliberately defined only on the vector store's
        # cosine score. BM25, RRF and reranker scores have different scales.
        return None if result.vector_score is None else float(result.vector_score)

    def _is_low_relevance(self, results: List[RetrievalResult]) -> bool:
        if not results or self.low_relevance_threshold == 0:
            return False
        score = self._score(results[0])
        return score is not None and score < self.low_relevance_threshold

    def _prepare(
        self,
        question: str,
        top_k: Optional[int],
    ) -> Tuple[List[RetrievalResult], ContextBuildResult, RAGPrompt, bool]:
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
        low_relevance = self._is_low_relevance(results)
        context = self.context_builder.build(results)
        return results, context, build_prompt(
            question,
            context.text,
            low_relevance=low_relevance,
        ), low_relevance

    def _event(
        self,
        request_id: str,
        question: str,
        top_k: int,
        results: List[RetrievalResult],
        answer: str,
        latency_ms: float,
        fallback_used: bool,
        error: Optional[str] = None,
        token_usage: Optional[Dict[str, Any]] = None,
        cache_hit: bool = False,
    ) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_question": question,
            "retrieval_mode": self.retrieval_mode,
            "top_k": top_k,
            "retrieved_chunks": [
                {
                    "chunk_id": result.chunk_id,
                    "vector_score": result.vector_score,
                    "bm25_score": result.bm25_score,
                    "rrf_score": result.rrf_score,
                    "rerank_score": result.rerank_score,
                }
                for result in results
            ],
            "llm_model": getattr(self.llm_client, "model_name", type(self.llm_client).__name__),
            "generation_parameters": asdict(self.generation_config),
            "answer": answer,
            "latency_ms": latency_ms,
            "token_usage": token_usage,
            "fallback_used": fallback_used,
            "cache_hit": cache_hit,
            "error": error,
        }

    def _log(
        self,
        request_id: str,
        question: str,
        top_k: int,
        results: List[RetrievalResult],
        answer: str,
        started: float,
        fallback_used: bool,
        error: Optional[str] = None,
        token_usage: Optional[Dict[str, Any]] = None,
        cache_hit: bool = False,
    ) -> None:
        log_rag_request(
            self.logger,
            self._event(
                request_id,
                question,
                top_k,
                results,
                answer,
                (perf_counter() - started) * 1000,
                fallback_used,
                error,
                token_usage,
                cache_hit,
            ),
        )

    def answer(
        self,
        question: str,
        top_k: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> RAGResponse:
        """Return a response or a structured friendly error without crashing."""

        started = perf_counter()
        request_id = request_id or str(uuid4())
        effective_top_k = self.default_top_k if top_k is None else top_k
        if effective_top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        if self.cache is not None:
            cached = self.cache.get(
                question,
                self.knowledge_base_version,
                self.generation_config,
            )
            if cached is not None:
                cached_response = cached.model_copy(
                    update={"latency_ms": (perf_counter() - started) * 1000}
                )
                self._log(
                    request_id,
                    question,
                    effective_top_k,
                    cached_response.retrieved_chunks,
                    cached_response.answer,
                    started,
                    cached_response.fallback_used,
                    cached_response.error,
                    cached_response.token_usage,
                    cache_hit=True,
                )
                return cached_response

        results, context, prompt, _ = self._prepare(question, top_k)
        fallback_used = not results
        if fallback_used and not self.allow_llm_fallback:
            answer = "当前知识库中未找到相关文档，无法基于知识库回答。"
            response = RAGResponse(
                answer=answer,
                retrieved_chunks=context.chunks,
                latency_ms=(perf_counter() - started) * 1000,
                fallback_used=True,
            )
            self._log(request_id, question, effective_top_k, results, answer, started, True)
            return response

        try:
            generated = self.llm_client.generate(prompt, self.generation_config)
            if not generated.text.strip():
                raise LLMServiceError("LLM returned an empty answer")
        except Exception as exc:  # noqa: BLE001 - provider failures become structured responses.
            error = f"{type(exc).__name__}: {exc}"
            answer = "生成服务暂时不可用，请稍后重试。"
            response = RAGResponse(
                answer=answer,
                citations=build_citations(context.chunks),
                retrieved_chunks=context.chunks,
                latency_ms=(perf_counter() - started) * 1000,
                fallback_used=fallback_used,
                error=error,
            )
            self._log(
                request_id,
                question,
                effective_top_k,
                results,
                answer,
                started,
                fallback_used,
                error,
            )
            return response

        response = RAGResponse(
            answer=generated.text,
            citations=build_citations(context.chunks),
            retrieved_chunks=context.chunks,
            latency_ms=(perf_counter() - started) * 1000,
            token_usage=generated.token_usage,
            fallback_used=fallback_used,
        )
        if self.cache is not None:
            self.cache.put(
                question,
                response,
                self.knowledge_base_version,
                self.generation_config,
            )
        self._log(
            request_id,
            question,
            effective_top_k,
            results,
            response.answer,
            started,
            fallback_used,
            token_usage=response.token_usage,
        )
        return response

    def stream_answer(
        self,
        question: str,
        top_k: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> Iterator[str]:
        """Yield response fragments and convert provider failures to a message."""

        started = perf_counter()
        request_id = request_id or str(uuid4())
        effective_top_k = self.default_top_k if top_k is None else top_k
        if effective_top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        results, _, prompt, _ = self._prepare(question, top_k)
        fallback_used = not results
        answer_parts: List[str] = []
        error: Optional[str] = None
        if fallback_used and not self.allow_llm_fallback:
            answer = "当前知识库中未找到相关文档，无法基于知识库回答。"
            answer_parts.append(answer)
            yield answer
        else:
            try:
                for fragment in self.llm_client.stream(prompt, self.generation_config):
                    answer_parts.append(fragment)
                    yield fragment
            except Exception as exc:  # noqa: BLE001 - provider failures are surfaced to callers.
                error = f"{type(exc).__name__}: {exc}"
                answer = "生成服务暂时不可用，请稍后重试。"
                answer_parts.append(answer)
                yield answer
        self._log(
            request_id,
            question,
            effective_top_k,
            results,
            "".join(answer_parts),
            started,
            fallback_used,
            error,
        )

    def stream_answer_events(
        self,
        question: str,
        top_k: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> Iterator[RAGStreamEvent]:
        """Yield structured streaming events with retrieval-grounded metadata.

        ``stream_answer`` remains the backward-compatible text-only interface.
        Citation data is copied from retrieved chunks before generation and is
        never parsed from, or inferred from, model output.
        """

        started = perf_counter()
        request_id = request_id or str(uuid4())
        effective_top_k = self.default_top_k if top_k is None else top_k
        if effective_top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        results, context, prompt, _ = self._prepare(question, top_k)
        citations = build_citations(context.chunks)
        yield RAGStreamEvent(
            event="metadata",
            request_id=request_id,
            citations=citations,
            retrieved_chunks=context.chunks,
        )

        fallback_used = not results
        answer_parts: List[str] = []
        error: Optional[str] = None
        if fallback_used and not self.allow_llm_fallback:
            answer = "当前知识库中未找到相关文档，无法基于知识库回答。"
            answer_parts.append(answer)
            yield RAGStreamEvent(event="token", request_id=request_id, text=answer)
        else:
            try:
                for fragment in self.llm_client.stream(prompt, self.generation_config):
                    answer_parts.append(fragment)
                    yield RAGStreamEvent(
                        event="token",
                        request_id=request_id,
                        text=fragment,
                    )
            except Exception as exc:  # noqa: BLE001 - provider failures are surfaced as events.
                error = f"{type(exc).__name__}: {exc}"
                answer = "生成服务暂时不可用，请稍后重试。"
                answer_parts.append(answer)
                yield RAGStreamEvent(
                    event="error",
                    request_id=request_id,
                    text=answer,
                    error=error,
                )

        self._log(
            request_id,
            question,
            effective_top_k,
            results,
            "".join(answer_parts),
            started,
            fallback_used,
            error,
        )
        yield RAGStreamEvent(event="end", request_id=request_id, error=error)


__all__ = ["RAGService", "RetrieverLike"]
