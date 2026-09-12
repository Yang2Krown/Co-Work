"""Common vector store contract."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Sequence, Union

from ..schemas import Chunk, RetrievalResult


PathLike = Union[str, Path]
Vector = Sequence[float]


class VectorStore(ABC):
    """Backend-independent interface used by indexing and retrieval layers."""

    @abstractmethod
    def add_chunks(self, chunks: Sequence[Chunk], embeddings: Sequence[Vector]) -> None:
        """Add or upsert chunk vectors."""

    @abstractmethod
    def search(self, query_embedding: Vector, top_k: int = 5) -> List[RetrievalResult]:
        """Return vector-ranked results with their vector scores."""

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Delete every chunk belonging to a document."""

    @abstractmethod
    def persist(self) -> None:
        """Persist the index when the implementation supports persistence."""


def validate_vectors(
    chunks: Sequence[Chunk], embeddings: Sequence[Vector]
) -> List[List[float]]:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    vectors = [list(map(float, embedding)) for embedding in embeddings]
    if vectors:
        dimension = len(vectors[0])
        if dimension == 0 or any(len(vector) != dimension for vector in vectors):
            raise ValueError("all embeddings must have the same non-zero dimension")
    return vectors


__all__ = ["PathLike", "Vector", "VectorStore", "validate_vectors"]

