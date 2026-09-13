"""Chroma vector store adapter."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..exceptions import VectorStoreError
from ..schemas import Chunk, RetrievalResult
from .base import PathLike, Vector, VectorStore, validate_vectors


class ChromaVectorStore(VectorStore):
    """Persistent Chroma adapter with chunk-level metadata reconstruction."""

    def __init__(
        self,
        persist_directory: PathLike = "data/indexes/chroma",
        collection_name: str = "cowork_documents",
        client: Any = None,
    ) -> None:
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        try:
            if client is None:
                import chromadb

                client = chromadb.PersistentClient(path=str(self.persist_directory))
            self._collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except ImportError as exc:
            raise VectorStoreError("chromadb is required for ChromaVectorStore") from exc
        except Exception as exc:
            raise VectorStoreError("Unable to initialize Chroma vector store") from exc

    @staticmethod
    def _metadata(chunk: Chunk) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "document_id": chunk.document_id,
            "file_name": chunk.file_name,
            "page_number": chunk.page_number if chunk.page_number is not None else -1,
        }
        for key in (
            "source_path",
            "title",
            "strategy",
            "chunk_index",
            "start_char",
            "end_char",
        ):
            value = chunk.metadata.get(key)
            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value
        return metadata

    def add_chunks(self, chunks: Sequence[Chunk], embeddings: Sequence[Vector]) -> None:
        try:
            vectors = validate_vectors(chunks, embeddings)
            if not chunks:
                return
            self._collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                embeddings=vectors,
                documents=[chunk.text for chunk in chunks],
                metadatas=[self._metadata(chunk) for chunk in chunks],
            )
        except (TypeError, ValueError) as exc:
            raise VectorStoreError("Invalid chunks or embeddings") from exc
        except Exception as exc:
            raise VectorStoreError("Unable to add chunks to Chroma") from exc

    def search(self, query_embedding: Vector, top_k: int = 5) -> List[RetrievalResult]:
        if top_k <= 0:
            return []
        try:
            if self._collection.count() == 0:
                return []
            result = self._collection.query(
                query_embeddings=[list(map(float, query_embedding))],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError("Unable to search Chroma vector store") from exc

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        results: List[RetrievalResult] = []
        for rank, chunk_id in enumerate(ids, start=1):
            metadata = metadatas[rank - 1] or {}
            page_number = metadata.get("page_number")
            results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    text=documents[rank - 1] or "",
                    document_id=str(metadata.get("document_id", "")),
                    file_name=str(metadata.get("file_name", "")),
                    page_number=None if page_number in (None, -1) else int(page_number),
                    vector_score=(
                        None
                        if len(distances) < rank or distances[rank - 1] is None
                        else 1.0 - float(distances[rank - 1])
                    ),
                    rank=rank,
                )
            )
        return results

    def delete_document(self, document_id: str) -> None:
        try:
            self._collection.delete(where={"document_id": document_id})
        except Exception as exc:
            raise VectorStoreError("Unable to delete document from Chroma") from exc

    def persist(self) -> None:
        # PersistentClient writes changes to disk; this method keeps the common API.
        return None


__all__ = ["ChromaVectorStore"]
