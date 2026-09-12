"""In-memory semantic cache for completed RAG responses."""

import json
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional, Sequence

import numpy as np

from ..schemas import RAGResponse
from .llm_client import GenerationConfig


EmbeddingFunction = Callable[[str], Sequence[float]]


@dataclass
class _CacheEntry:
    question: str
    embedding: np.ndarray
    knowledge_base_version: str
    generation_signature: str
    response: RAGResponse


class SemanticCache:
    """Cache responses only when question, KB version, and config are compatible."""

    def __init__(
        self,
        embedding_function: Optional[EmbeddingFunction],
        similarity_threshold: float = 0.95,
        max_entries: int = 256,
        enabled: bool = True,
    ) -> None:
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between zero and one")
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        self.embedding_function = embedding_function
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.enabled = enabled
        self._entries: List[_CacheEntry] = []

    @staticmethod
    def _signature(config: GenerationConfig) -> str:
        return json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _vector(question: str, embedding_function: EmbeddingFunction) -> np.ndarray:
        vector = np.asarray(embedding_function(question), dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(vector)
        if vector.size == 0 or not np.isfinite(vector).all() or norm == 0:
            raise ValueError("cache embedding must be a finite non-zero vector")
        return vector / norm

    def get(
        self,
        question: str,
        knowledge_base_version: str,
        generation_config: GenerationConfig,
    ) -> Optional[RAGResponse]:
        """Return the best compatible response at or above the threshold."""

        if not self.enabled or self.embedding_function is None:
            return None
        query_vector = self._vector(question, self.embedding_function)
        signature = self._signature(generation_config)
        best_index = -1
        best_similarity = -1.0
        for index, entry in enumerate(self._entries):
            if (
                entry.knowledge_base_version != knowledge_base_version
                or entry.generation_signature != signature
                or entry.embedding.shape != query_vector.shape
            ):
                continue
            similarity = float(np.dot(query_vector, entry.embedding))
            if similarity >= self.similarity_threshold and similarity > best_similarity:
                best_index = index
                best_similarity = similarity
        if best_index < 0:
            return None
        entry = self._entries.pop(best_index)
        self._entries.append(entry)
        return entry.response

    def put(
        self,
        question: str,
        response: RAGResponse,
        knowledge_base_version: str,
        generation_config: GenerationConfig,
    ) -> None:
        """Store a completed response and evict the oldest entry if necessary."""

        if not self.enabled or self.embedding_function is None:
            return
        embedding = self._vector(question, self.embedding_function)
        signature = self._signature(generation_config)
        self._entries = [
            entry
            for entry in self._entries
            if not (
                entry.question == question
                and entry.knowledge_base_version == knowledge_base_version
                and entry.generation_signature == signature
            )
        ]
        self._entries.append(
            _CacheEntry(
                question=question,
                embedding=embedding,
                knowledge_base_version=knowledge_base_version,
                generation_signature=signature,
                response=response,
            )
        )
        del self._entries[: max(0, len(self._entries) - self.max_entries)]

    def clear(self) -> None:
        """Remove all cached responses."""

        self._entries.clear()


__all__ = ["EmbeddingFunction", "SemanticCache"]
