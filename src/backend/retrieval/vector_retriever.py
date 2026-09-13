"""Thin vector retrieval wrapper for the hybrid retrieval layer."""

from typing import List, Optional

from ..embeddings import EmbeddingService
from ..schemas import RetrievalResult
from ..vectorstores import VectorStore


class VectorRetriever:
    """Embed a query and retrieve ranked chunks from a VectorStore."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        top_k: int = 20,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.top_k = top_k

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RetrievalResult]:
        effective_top_k = self.top_k if top_k is None else top_k
        if effective_top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        embedding = self.embedding_service.embed_query(query)
        return self.vector_store.search(embedding, effective_top_k)


__all__ = ["VectorRetriever"]
