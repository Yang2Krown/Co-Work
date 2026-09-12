from pathlib import Path

import pytest

from src.backend.schemas import Chunk
from src.backend.vectorstores import (
    ChromaVectorStore,
    FAISSVectorStore,
    InMemoryVectorStore,
)


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id="doc-a:0",
            document_id="doc-a",
            text="alpha",
            page_number=1,
            file_name="a.txt",
            metadata={"source_path": "a.txt"},
        ),
        Chunk(
            chunk_id="doc-b:0",
            document_id="doc-b",
            text="beta",
            page_number=None,
            file_name="b.txt",
            metadata={"source_path": "b.txt"},
        ),
    ]


def test_in_memory_vector_store_supports_add_search_delete_and_top_k() -> None:
    store = InMemoryVectorStore()
    store.add_chunks(_chunks(), [[1.0, 0.0], [0.0, 1.0]])

    results = store.search([0.9, 0.1], top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "doc-a:0"
    assert results[0].rank == 1
    assert results[0].vector_score is not None
    store.delete_document("doc-a")
    assert store.size == 1


def test_chroma_vector_store_implements_common_contract(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    store = ChromaVectorStore(tmp_path / "chroma", "test_collection")
    store.add_chunks(_chunks(), [[1.0, 0.0], [0.0, 1.0]])

    results = store.search([1.0, 0.0], top_k=1)

    assert results[0].chunk_id == "doc-a:0"
    assert results[0].document_id == "doc-a"
    store.delete_document("doc-a")
    assert store.search([1.0, 0.0], top_k=5)[0].chunk_id == "doc-b:0"
    store.persist()


def test_faiss_vector_store_persists_and_reloads(tmp_path: Path) -> None:
    pytest.importorskip("faiss")
    index_path = tmp_path / "faiss"
    store = FAISSVectorStore(index_path)
    store.add_chunks(_chunks(), [[1.0, 0.0], [0.0, 1.0]])
    store.persist()

    reloaded = FAISSVectorStore(index_path)
    results = reloaded.search([0.0, 1.0], top_k=1)

    assert results[0].chunk_id == "doc-b:0"
    reloaded.delete_document("doc-b")
    reloaded.persist()
    remaining = reloaded.search([0.0, 1.0], top_k=5)
    assert [result.chunk_id for result in remaining] == ["doc-a:0"]
