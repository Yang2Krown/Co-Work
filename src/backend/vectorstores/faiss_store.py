"""FAISS vector store adapter with local metadata persistence."""

import json
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

from ..exceptions import VectorStoreError
from ..schemas import Chunk, RetrievalResult
from .base import PathLike, Vector, VectorStore, validate_vectors


class FAISSVectorStore(VectorStore):
    """Inner-product FAISS index for normalized embeddings."""

    def __init__(
        self,
        persist_directory: PathLike = "data/indexes/faiss",
        num_threads: int = 1,
    ) -> None:
        if num_threads <= 0:
            raise ValueError("num_threads must be greater than zero")
        try:
            import faiss
        except ImportError as exc:
            raise VectorStoreError("faiss-cpu is required for FAISSVectorStore") from exc

        self._faiss = faiss
        # On macOS, FAISS OpenMP workers can conflict with the PyTorch runtime
        # used by SentenceTransformers in the same process. A single FAISS
        # worker is the safe default for the local backend and remains tunable.
        self.num_threads = num_threads
        self._faiss.omp_set_num_threads(self.num_threads)
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._index_path = self.persist_directory / "index.faiss"
        self._records_path = self.persist_directory / "records.json"
        self._chunks: Dict[str, Chunk] = {}
        self._vectors: Dict[str, List[float]] = {}
        self._numeric_ids: Dict[str, int] = {}
        self._index = None
        self._dimension = 0
        self._load()

    @staticmethod
    def _normalized(vector: Vector) -> np.ndarray:
        array = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        return array if norm == 0 else array / norm

    def _rebuild_index(self) -> None:
        if not self._vectors:
            self._index = None
            self._dimension = 0
            self._numeric_ids = {}
            return
        dimensions = {len(vector) for vector in self._vectors.values()}
        if len(dimensions) != 1 or 0 in dimensions:
            raise VectorStoreError("FAISS records have inconsistent embedding dimensions")
        self._dimension = dimensions.pop()
        base_index = self._faiss.IndexFlatIP(self._dimension)
        self._index = self._faiss.IndexIDMap2(base_index)
        self._numeric_ids = {
            chunk_id: index for index, chunk_id in enumerate(sorted(self._vectors))
        }
        matrix = np.asarray(
            [self._normalized(self._vectors[chunk_id]) for chunk_id in sorted(self._vectors)],
            dtype=np.float32,
        )
        ids = np.asarray(
            [self._numeric_ids[chunk_id] for chunk_id in sorted(self._vectors)],
            dtype=np.int64,
        )
        self._index.add_with_ids(matrix, ids)

    def _load(self) -> None:
        if not self._records_path.is_file():
            return
        try:
            payload = json.loads(self._records_path.read_text(encoding="utf-8"))
            for record in payload:
                chunk = Chunk.model_validate(record["chunk"])
                self._chunks[chunk.chunk_id] = chunk
                self._vectors[chunk.chunk_id] = list(record["embedding"])
            self._rebuild_index()
        except Exception as exc:
            raise VectorStoreError("Unable to load FAISS metadata") from exc

    def add_chunks(self, chunks: Sequence[Chunk], embeddings: Sequence[Vector]) -> None:
        try:
            vectors = validate_vectors(chunks, embeddings)
            for chunk, vector in zip(chunks, vectors):
                self._chunks[chunk.chunk_id] = chunk
                self._vectors[chunk.chunk_id] = vector
            self._rebuild_index()
        except (TypeError, ValueError) as exc:
            raise VectorStoreError("Invalid chunks or embeddings") from exc

    def search(self, query_embedding: Vector, top_k: int = 5) -> List[RetrievalResult]:
        if top_k <= 0 or self._index is None:
            return []
        query = self._normalized(query_embedding).reshape(1, -1)
        if query.shape[1] != self._dimension:
            raise VectorStoreError("Query embedding dimension does not match index")
        try:
            self._faiss.omp_set_num_threads(self.num_threads)
            scores, identifiers = self._index.search(query, min(top_k, self._index.ntotal))
        except Exception as exc:
            raise VectorStoreError("Unable to search FAISS vector store") from exc

        by_numeric_id = {value: key for key, value in self._numeric_ids.items()}
        results: List[RetrievalResult] = []
        for score, numeric_id in zip(scores[0], identifiers[0]):
            if numeric_id < 0:
                continue
            chunk = self._chunks[by_numeric_id[int(numeric_id)]]
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    document_id=chunk.document_id,
                    file_name=chunk.file_name,
                    page_number=chunk.page_number,
                    vector_score=float(score),
                    rank=len(results) + 1,
                )
            )
        return results

    def delete_document(self, document_id: str) -> None:
        for chunk_id, chunk in list(self._chunks.items()):
            if chunk.document_id == document_id:
                del self._chunks[chunk_id]
                del self._vectors[chunk_id]
        self._rebuild_index()

    def persist(self) -> None:
        try:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            if self._index is not None:
                self._faiss.write_index(self._index, str(self._index_path))
            elif self._index_path.exists():
                self._index_path.unlink()
            payload = [
                {"chunk": self._chunks[chunk_id].model_dump(), "embedding": self._vectors[chunk_id]}
                for chunk_id in sorted(self._chunks)
            ]
            self._records_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            raise VectorStoreError("Unable to persist FAISS vector store") from exc


__all__ = ["FAISSVectorStore"]
