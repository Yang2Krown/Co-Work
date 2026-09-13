"""Small in-memory vector store used for tests and local smoke runs."""

from typing import Dict, List, Sequence, Tuple

import numpy as np

from ..exceptions import VectorStoreError
from ..schemas import Chunk, RetrievalResult
from .base import Vector, VectorStore, validate_vectors


class InMemoryVectorStore(VectorStore):
    """Cosine-similarity store with the same contract as persistent adapters."""

    def __init__(self) -> None:
        self._records: Dict[str, Tuple[Chunk, np.ndarray]] = {}

    @staticmethod
    def _normalized(vector: Vector) -> np.ndarray:
        array = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        return array if norm == 0 else array / norm

    def add_chunks(self, chunks: Sequence[Chunk], embeddings: Sequence[Vector]) -> None:
        try:
            vectors = validate_vectors(chunks, embeddings)
            for chunk, vector in zip(chunks, vectors):
                self._records[chunk.chunk_id] = (
                    chunk,
                    self._normalized(vector),
                )
        except (TypeError, ValueError) as exc:
            raise VectorStoreError("Invalid chunks or embeddings") from exc

    def search(self, query_embedding: Vector, top_k: int = 5) -> List[RetrievalResult]:
        if top_k <= 0 or not self._records:
            return []
        query = self._normalized(query_embedding)
        ranked = []
        for chunk, vector in self._records.values():
            if vector.shape != query.shape:
                raise VectorStoreError("Query embedding dimension does not match index")
            ranked.append((float(np.dot(query, vector)), chunk))
        ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [
            RetrievalResult(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                document_id=chunk.document_id,
                file_name=chunk.file_name,
                page_number=chunk.page_number,
                vector_score=score,
                rank=rank,
            )
            for rank, (score, chunk) in enumerate(ranked[:top_k], start=1)
        ]

    def delete_document(self, document_id: str) -> None:
        for chunk_id, (chunk, _) in list(self._records.items()):
            if chunk.document_id == document_id:
                del self._records[chunk_id]

    def persist(self) -> None:
        return None

    @property
    def size(self) -> int:
        return len(self._records)


__all__ = ["InMemoryVectorStore"]

