from pathlib import Path

import numpy as np

from src.backend.embeddings import EmbeddingService
from src.backend.indexing import IncrementalIndex
from src.backend.schemas import Document
from src.backend.vectorstores import InMemoryVectorStore


class KeywordEmbeddingModel:
    def encode(self, texts, **kwargs):
        return np.asarray(
            [
                [1.0 if "alpha" in text else 0.0, 1.0 if "beta" in text else 0.0]
                for text in texts
            ],
            dtype=np.float32,
        )


def _document(source_path: str, document_id: str, text: str) -> Document:
    return Document(
        document_id=document_id,
        file_name=Path(source_path).name,
        file_type="txt",
        text=text,
        metadata={"source_path": source_path},
    )


def test_incremental_index_skips_unchanged_and_replaces_changed_documents(
    tmp_path: Path,
) -> None:
    store = InMemoryVectorStore()
    embeddings = EmbeddingService(model=KeywordEmbeddingModel())
    index = IncrementalIndex(
        vector_store=store,
        embedding_service=embeddings,
        manifest_path=str(tmp_path / "manifest.json"),
        chunking_strategy="fixed",
        chunk_size=100,
        chunk_overlap=0,
        vector_top_k=2,
    )
    first = _document("paper.txt", "doc-v1", "alpha content")
    changed = _document("paper.txt", "doc-v2", "beta content")

    added = index.index_documents([first])
    skipped = index.index_documents([first])
    replaced = index.index_documents([changed])

    assert added.added_documents == ["paper.txt"]
    assert added.processed_chunk_count == 1
    assert skipped.skipped_documents == ["paper.txt"]
    assert skipped.processed_chunk_count == 0
    assert replaced.replaced_documents == ["paper.txt"]
    assert replaced.index_version != added.index_version
    assert store.size == 1
    assert index.retrieve("beta", top_k=1)[0].document_id == "doc-v2"

