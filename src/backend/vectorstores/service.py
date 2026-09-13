"""Vector store factory driven by backend configuration."""

from typing import Any

from ..exceptions import ConfigurationError
from .base import VectorStore


def create_vector_store(
    store_type: str,
    persist_directory: str = "data/indexes",
    collection_name: str = "cowork_documents",
    faiss_num_threads: int = 1,
) -> VectorStore:
    """Create a configured Chroma, FAISS, or in-memory store."""

    normalized = store_type.strip().lower()
    if normalized == "chroma":
        from .chroma_store import ChromaVectorStore

        return ChromaVectorStore(persist_directory, collection_name)
    if normalized == "faiss":
        from .faiss_store import FAISSVectorStore

        return FAISSVectorStore(persist_directory, num_threads=faiss_num_threads)
    if normalized in {"memory", "in-memory", "inmemory"}:
        from .memory_store import InMemoryVectorStore

        return InMemoryVectorStore()
    raise ConfigurationError(
        "Unsupported vector store type '"
        + store_type
        + "'. Choose chroma, faiss, or memory."
    )


__all__ = ["create_vector_store"]
