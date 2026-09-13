from pathlib import Path

import numpy as np

from src.backend.chunking import chunk_document
from src.backend.embeddings import EmbeddingService
from src.backend.loaders import load_txt
from src.backend.retrieval import BM25Retriever, HybridRetriever, Reranker, VectorRetriever
from src.backend.schemas import Document
from src.backend.vectorstores import InMemoryVectorStore
from scripts.evaluate_retrieval import evaluate_retrieval


class IntegrationEmbeddingModel:
    def encode(self, texts, **kwargs):
        return np.asarray(
            [
                [1.0 if "graph" in text else 0.0, 1.0 if "retrieval" in text else 0.0]
                for text in texts
            ],
            dtype=np.float32,
        )


class IntegrationRerankerModel:
    def predict(self, pairs, **kwargs):
        return [1.0 if "graph" in text else 0.1 for _, text in pairs]


def test_document_to_three_mode_retrieval_and_metrics(tmp_path: Path) -> None:
    source_path = tmp_path / "paper.txt"
    source_path.write_text(
        "Graph retrieval improves recall.\n\nVector search uses embeddings.",
        encoding="utf-8",
    )
    loaded = load_txt(source_path)
    document = Document(
        document_id=loaded.document_id,
        file_name=loaded.file_name,
        file_type=loaded.file_type,
        text=loaded.text,
        metadata=loaded.metadata,
    )
    chunks = chunk_document(document, strategy="structure", chunk_size=100, chunk_overlap=0)
    embedding_service = EmbeddingService(model=IntegrationEmbeddingModel())
    vector_store = InMemoryVectorStore()
    vector_store.add_chunks(chunks, embedding_service.embed_documents([chunk.text for chunk in chunks]))
    retriever = HybridRetriever(
        vector_retriever=VectorRetriever(vector_store, embedding_service, top_k=2),
        bm25_retriever=BM25Retriever(chunks),
        reranker=Reranker(model=IntegrationRerankerModel()),
        vector_top_k=2,
        bm25_top_k=2,
        final_top_k=2,
        reranker_top_n=2,
    )

    vector = retriever.retrieve("graph", mode="vector")
    hybrid = retriever.retrieve("graph", mode="hybrid")
    reranked = retriever.retrieve("graph", mode="hybrid_rerank")
    report = evaluate_retrieval(
        retriever,
        [{"question": "graph", "relevant_chunk_ids": [chunks[0].chunk_id]}],
    )

    assert vector[0].chunk_id == chunks[0].chunk_id
    assert hybrid[0].rrf_score is not None
    assert reranked[0].rerank_score is not None
    assert all(record["query_count"] == 1 for record in report["records"])
    assert all(record["hit_at_5"] == 1.0 for record in report["records"])
    assert all(record["mrr"] == 1.0 for record in report["records"])
