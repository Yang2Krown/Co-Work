"""Unified vector, hybrid, and hybrid-rerank retrieval."""

from typing import List, Literal, Optional, Protocol

from ..schemas import RetrievalResult
from .reranker import Reranker
from .rrf import rrf_fuse


RetrievalMode = Literal["vector", "hybrid", "hybrid_rerank"]


class RetrieverLike(Protocol):
    def retrieve(self, query: str, top_k: int) -> List[RetrievalResult]:
        ...


class HybridRetriever:
    """Compose independent retrievers while keeping all retrieval modes explicit."""

    def __init__(
        self,
        vector_retriever: RetrieverLike,
        bm25_retriever: Optional[RetrieverLike] = None,
        reranker: Optional[Reranker] = None,
        vector_top_k: int = 20,
        bm25_top_k: int = 20,
        final_top_k: int = 5,
        enable_bm25: bool = True,
        enable_rrf: bool = True,
        rrf_k: int = 60,
        enable_reranker: bool = True,
        reranker_top_n: int = 20,
    ) -> None:
        for name, value in (
            ("vector_top_k", vector_top_k),
            ("bm25_top_k", bm25_top_k),
            ("final_top_k", final_top_k),
            ("rrf_k", rrf_k),
            ("reranker_top_n", reranker_top_n),
        ):
            if value <= 0:
                raise ValueError(name + " must be greater than zero")
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.reranker = reranker
        self.vector_top_k = vector_top_k
        self.bm25_top_k = bm25_top_k
        self.final_top_k = final_top_k
        self.enable_bm25 = enable_bm25
        self.enable_rrf = enable_rrf
        self.rrf_k = rrf_k
        self.enable_reranker = enable_reranker
        self.reranker_top_n = reranker_top_n

    @staticmethod
    def _renumber(results: List[RetrievalResult]) -> List[RetrievalResult]:
        return [
            result.model_copy(update={"rank": rank})
            for rank, result in enumerate(results, start=1)
        ]

    def retrieve(
        self,
        query: str,
        mode: RetrievalMode = "hybrid_rerank",
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        final_top_k = self.final_top_k if top_k is None else top_k
        if final_top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        if mode not in {"vector", "hybrid", "hybrid_rerank"}:
            raise ValueError(
                "Unknown retrieval mode '"
                + str(mode)
                + "'. Choose vector, hybrid, or hybrid_rerank."
            )

        vector_results = self.vector_retriever.retrieve(query, self.vector_top_k)
        if mode == "vector" or not self.enable_bm25 or self.bm25_retriever is None:
            return self._renumber(vector_results[:final_top_k])

        bm25_results = self.bm25_retriever.retrieve(query, self.bm25_top_k)
        if not self.enable_rrf:
            candidates = vector_results + bm25_results
            deduplicated = {}
            for result in candidates:
                deduplicated.setdefault(result.chunk_id, result)
            fused = list(deduplicated.values())
        else:
            fused = rrf_fuse([vector_results, bm25_results], k=self.rrf_k)

        if mode == "hybrid_rerank" and self.enable_reranker:
            if self.reranker is None:
                raise ValueError("reranker is required when reranking is enabled")
            return self.reranker.rerank(
                query,
                fused[: self.reranker_top_n],
                top_k=final_top_k,
            )
        return self._renumber(fused[:final_top_k])


__all__ = ["HybridRetriever", "RetrievalMode"]
