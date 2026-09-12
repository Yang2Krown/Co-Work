from typing import List

import numpy as np
import pytest

from src.backend.embeddings import EmbeddingService
from src.backend.retrieval import (
    BM25Retriever,
    HybridRetriever,
    Reranker,
    VectorRetriever,
    rrf_fuse,
)
from src.backend.schemas import Chunk, RetrievalResult
from src.backend.vectorstores import InMemoryVectorStore


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=chunk_id.split(":")[0],
        text=text,
        file_name="paper.txt",
        page_number=1,
        metadata={},
    )


def _result(chunk_id: str, **scores: float) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=chunk_id,
        document_id="doc",
        file_name="paper.txt",
        page_number=1,
        rank=1,
        **scores,
    )


class FakeRerankerModel:
    def predict(self, pairs, **kwargs):
        return [1.0 if "target" in text else 0.1 for _, text in pairs]


class FakeEmbeddingModel:
    def encode(self, texts, **kwargs):
        return np.asarray(
            [[1.0 if "alpha" in text else 0.0, 1.0 if "beta" in text else 0.0] for text in texts],
            dtype=np.float32,
        )


def test_bm25_retriever_runs_independently() -> None:
    chunks = [
        _chunk("a:0", "quantum retrieval"),
        _chunk("b:0", "classical indexing"),
        _chunk("c:0", "neural ranking"),
    ]
    results = BM25Retriever(chunks).retrieve("quantum", top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "a:0"
    assert results[0].bm25_score is not None


def test_rrf_fuse_covers_overlap_singleton_ties_and_empty_lists() -> None:
    first = _result("a", vector_score=0.9)
    second = _result("b", vector_score=0.8)
    bm25_a = _result("a", bm25_score=2.0)
    bm25_c = _result("c", bm25_score=1.0)

    fused = rrf_fuse([[first, second], [bm25_a, bm25_c]], k=60)

    assert [result.chunk_id for result in fused] == ["a", "b", "c"]
    assert fused[0].vector_score == 0.9
    assert fused[0].bm25_score == 2.0
    assert fused[0].rrf_score == pytest.approx(2 / 61)
    assert [result.chunk_id for result in rrf_fuse([[], []])] == []
    tied = rrf_fuse([[_result("x")], [_result("y")]], k=60)
    assert [result.chunk_id for result in tied] == ["x", "y"]


def test_reranker_can_be_enabled_or_disabled() -> None:
    candidates = [_result("a", rrf_score=0.2), _result("b", rrf_score=0.3)]
    enabled = Reranker(model=FakeRerankerModel()).rerank(
        "question", [candidates[0].model_copy(update={"text": "ordinary"}), candidates[1].model_copy(update={"text": "target"})]
    )
    disabled = Reranker(enabled=False).rerank("question", candidates)

    assert enabled[0].text == "target"
    assert enabled[0].rerank_score == 1.0
    assert disabled[0].chunk_id == "a"
    assert disabled[0].rerank_score is None


def test_hybrid_retriever_supports_three_modes() -> None:
    chunks = [_chunk("a:0", "alpha topic"), _chunk("b:0", "beta target")]
    embedding_service = EmbeddingService(model=FakeEmbeddingModel())
    store = InMemoryVectorStore()
    store.add_chunks(chunks, embedding_service.embed_documents([chunk.text for chunk in chunks]))
    vector = VectorRetriever(store, embedding_service, top_k=2)
    bm25 = BM25Retriever(chunks)
    retriever = HybridRetriever(
        vector_retriever=vector,
        bm25_retriever=bm25,
        reranker=Reranker(model=FakeRerankerModel()),
        vector_top_k=2,
        bm25_top_k=2,
        final_top_k=1,
        reranker_top_n=2,
    )

    vector_results = retriever.retrieve("alpha", mode="vector")
    hybrid_results = retriever.retrieve("alpha", mode="hybrid")
    reranked_results = retriever.retrieve("alpha", mode="hybrid_rerank")

    assert vector_results[0].vector_score is not None
    assert hybrid_results[0].rrf_score is not None
    assert reranked_results[0].rerank_score is not None
    assert all(result.rank == 1 for result in [vector_results[0], hybrid_results[0], reranked_results[0]])
