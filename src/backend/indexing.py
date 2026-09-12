"""Incremental document-to-vector indexing service."""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .chunking import chunk_document
from .embeddings import EmbeddingService
from .exceptions import VectorStoreError
from .schemas import Document, RetrievalResult
from .vectorstores import VectorStore


class IndexUpdateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_documents: List[str] = Field(default_factory=list)
    skipped_documents: List[str] = Field(default_factory=list)
    replaced_documents: List[str] = Field(default_factory=list)
    processed_chunk_count: int = Field(default=0, ge=0)
    index_version: str


class IncrementalIndex:
    """Index only new or changed documents using a persistent manifest."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        manifest_path: str = "data/indexes/manifest.json",
        chunking_strategy: str = "recursive",
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        vector_top_k: int = 20,
    ) -> None:
        if vector_top_k <= 0:
            raise ValueError("vector_top_k must be greater than zero")
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.manifest_path = Path(manifest_path)
        self.chunking_strategy = chunking_strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vector_top_k = vector_top_k

    def _load_manifest(self) -> Dict[str, str]:
        if not self.manifest_path.is_file():
            return {}
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in payload.items()
            ):
                raise ValueError("manifest must map source paths to document IDs")
            return payload
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise VectorStoreError("Unable to read index manifest") from exc

    def _save_manifest(self, manifest: Dict[str, str]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _source_key(document: Document) -> str:
        return str(document.metadata.get("source_path") or document.file_name)

    @staticmethod
    def _version(manifest: Dict[str, str]) -> str:
        serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()[:16]

    def index_documents(self, documents: Sequence[Document]) -> IndexUpdateResult:
        manifest = self._load_manifest()
        added: List[str] = []
        skipped: List[str] = []
        replaced: List[str] = []
        processed_chunk_count = 0

        for document in documents:
            source_key = self._source_key(document)
            previous_document_id = manifest.get(source_key)
            if previous_document_id == document.document_id:
                skipped.append(source_key)
                continue

            chunks = chunk_document(
                document,
                strategy=self.chunking_strategy,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            embeddings = self.embedding_service.embed_documents(
                [chunk.text for chunk in chunks]
            )
            if previous_document_id is not None:
                self.vector_store.delete_document(previous_document_id)
                replaced.append(source_key)
            else:
                added.append(source_key)

            self.vector_store.add_chunks(chunks, embeddings)
            processed_chunk_count += len(chunks)
            manifest[source_key] = document.document_id

        self.vector_store.persist()
        self._save_manifest(manifest)
        return IndexUpdateResult(
            added_documents=added,
            skipped_documents=skipped,
            replaced_documents=replaced,
            processed_chunk_count=processed_chunk_count,
            index_version=self._version(manifest),
        )

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """Return configurable Top-K vector results."""

        query_embedding = self.embedding_service.embed_query(query)
        return self.vector_store.search(query_embedding, top_k or self.vector_top_k)


__all__ = ["IncrementalIndex", "IndexUpdateResult"]
