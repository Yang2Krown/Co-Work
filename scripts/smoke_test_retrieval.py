"""Run a real-model smoke test for the M3/M4 retrieval chain.

This script is intentionally separate from pytest because it may download large
model weights and requires a working network and sufficient local resources.
It never fabricates evaluation metrics: the returned results are only smoke-test
observations for the built-in four-text corpus.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Sequence

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.chunking import chunk_document
from src.backend.config import load_config
from src.backend.embeddings import EmbeddingService
from src.backend.retrieval import BM25Retriever, HybridRetriever, Reranker, VectorRetriever
from src.backend.schemas import Chunk, Document, RetrievalResult
from src.backend.vectorstores import ChromaVectorStore, FAISSVectorStore


SMOKE_TEXTS = [
    "本文研究基于向量表示的中文论文检索方法，重点比较语义相似度对召回率的影响。",
    "实验结果表明，混合检索将向量检索与关键词匹配结合，可以提升长尾查询的召回效果。",
    "我们使用跨编码器对初始候选重新排序，重排模型能够利用查询与段落之间的细粒度语义关系。",
    "数据集包含科研论文摘要和章节文本，文本在建立索引前按照固定长度和段落边界进行切分。",
]
SMOKE_QUERY = "混合检索如何提升中文论文的召回效果？"


def _build_chunks() -> List[Chunk]:
    chunks = []
    for index, text in enumerate(SMOKE_TEXTS, start=1):
        document = Document(
            document_id=f"smoke-doc-{index}",
            file_name=f"smoke-{index}.txt",
            file_type="txt",
            text=text,
            metadata={"source_path": f"smoke://smoke-{index}.txt", "title": f"Smoke {index}"},
        )
        chunks.extend(
            chunk_document(
                document,
                strategy="structure",
                chunk_size=512,
                chunk_overlap=0,
            )
        )
    return chunks


def _serialize_results(results: Sequence[RetrievalResult]) -> List[Dict[str, Any]]:
    return [result.model_dump() for result in results]


def _error_chain(error: BaseException) -> str:
    messages = []
    current: BaseException | None = error
    while current is not None:
        if str(current):
            messages.append(f"{current.__class__.__name__}: {current}")
        current = current.__cause__
    return " <- ".join(messages)


def run_smoke_test(
    embedding_model: str = "m3e-base",
    reranker_model: str = "bge-reranker-base",
    query: str = SMOKE_QUERY,
    top_k: int = 3,
    persist_root: Path = Path("data/indexes/smoke_test"),
) -> Dict[str, Any]:
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    timings: Dict[str, float] = {}
    current_stage = "initialization"

    def timed(stage: str, operation):
        nonlocal current_stage
        current_stage = stage
        started = perf_counter()
        value = operation()
        timings[stage] = (perf_counter() - started) * 1000
        return value

    config = load_config()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_root = persist_root / f"smoke-{run_id}"
    run_root.mkdir(parents=True, exist_ok=True)

    embedding_service = timed(
        "embedding_service_initialize",
        lambda: EmbeddingService(
            model_name=embedding_model,
            batch_size=config.embedding.batch_size,
            normalize_embeddings=config.embedding.normalize_embeddings,
        ),
    )
    chunks = _build_chunks()
    chunk_texts = [chunk.text for chunk in chunks]
    embeddings = timed(
        "embedding_cold_load_first_run",
        lambda: embedding_service.embed_documents(chunk_texts),
    )
    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(chunks) or matrix.shape[1] == 0:
        raise RuntimeError(f"Invalid embedding shape: {matrix.shape}")
    if not np.isfinite(matrix).all() or np.any(np.linalg.norm(matrix, axis=1) == 0):
        raise RuntimeError("Embedding contains non-finite values or zero vectors")
    embedding_shape = [int(matrix.shape[0]), int(matrix.shape[1])]
    warm_embeddings = timed(
        "embedding_warm_inference",
        lambda: embedding_service.embed_documents(chunk_texts),
    )
    warm_matrix = np.asarray(warm_embeddings, dtype=np.float32)
    if warm_matrix.shape != matrix.shape or not np.isfinite(warm_matrix).all():
        raise RuntimeError(
            "Warm embedding shape or values differ from the cold embedding run"
        )

    chroma_store = timed(
        "chroma_initialize_and_write",
        lambda: ChromaVectorStore(
            run_root / "chroma",
            collection_name=f"smoke_{run_id.replace('-', '_')}",
        ),
    )
    timed(
        "chroma_persist",
        lambda: (chroma_store.add_chunks(chunks, embeddings), chroma_store.persist()),
    )
    faiss_store = timed(
        "faiss_initialize_and_write",
        lambda: FAISSVectorStore(run_root / "faiss"),
    )
    timed(
        "faiss_persist",
        lambda: (faiss_store.add_chunks(chunks, embeddings), faiss_store.persist()),
    )

    chroma_vector = VectorRetriever(
        chroma_store,
        embedding_service,
        top_k=config.retrieval.vector_top_k,
    )
    faiss_vector = VectorRetriever(
        faiss_store,
        embedding_service,
        top_k=config.retrieval.vector_top_k,
    )
    vector_chroma = timed(
        "vector_retrieval_chroma",
        lambda: chroma_vector.retrieve(query, top_k),
    )
    vector_faiss = timed(
        "vector_retrieval_faiss",
        lambda: faiss_vector.retrieve(query, top_k),
    )
    if not vector_chroma or not vector_faiss:
        raise RuntimeError("Vector retrieval returned no results")

    bm25 = BM25Retriever(chunks)
    reranker = Reranker(
        model_name=reranker_model,
        enabled=True,
        batch_size=config.retrieval.reranker_batch_size,
    )
    hybrid = HybridRetriever(
        vector_retriever=chroma_vector,
        bm25_retriever=bm25,
        reranker=reranker,
        vector_top_k=config.retrieval.vector_top_k,
        bm25_top_k=config.retrieval.bm25_top_k,
        final_top_k=top_k,
        enable_bm25=True,
        enable_rrf=True,
        rrf_k=config.retrieval.rrf_k,
        enable_reranker=True,
        reranker_top_n=config.retrieval.reranker_top_n,
    )
    hybrid_results = timed(
        "hybrid_retrieval_rrf",
        lambda: hybrid.retrieve(query, mode="hybrid", top_k=top_k),
    )
    hybrid_rerank_results = timed(
        "hybrid_rerank_cold_load_first_run",
        lambda: hybrid.retrieve(query, mode="hybrid_rerank", top_k=top_k),
    )
    hybrid_rerank_warm_results = timed(
        "hybrid_rerank_warm_inference",
        lambda: hybrid.retrieve(query, mode="hybrid_rerank", top_k=top_k),
    )
    if not hybrid_results or not hybrid_rerank_results or not hybrid_rerank_warm_results:
        raise RuntimeError("Hybrid retrieval returned no results")

    return {
        "status": "passed",
        "python": sys.version.split()[0],
        "embedding_model": embedding_model,
        "embedding_model_resolved": embedding_service.resolved_model_name,
        "reranker_model": reranker_model,
        "reranker_model_resolved": reranker.resolved_model_name,
        "input_text_count": len(SMOKE_TEXTS),
        "embedding_shape": embedding_shape,
        "embedding_values_finite": bool(np.isfinite(matrix).all()),
        "persist_root": str(run_root),
        "query": query,
        "top_k": top_k,
        "chroma_results": _serialize_results(
            chroma_store.search(embedding_service.embed_query(query), top_k)
        ),
        "faiss_results": _serialize_results(
            faiss_store.search(embedding_service.embed_query(query), top_k)
        ),
        "vector_results": _serialize_results(vector_chroma),
        "vector_faiss_results": _serialize_results(vector_faiss),
        "hybrid_results": _serialize_results(hybrid_results),
        "hybrid_rerank_results": _serialize_results(hybrid_rerank_results),
        "hybrid_rerank_warm_results": _serialize_results(hybrid_rerank_warm_results),
        "timings_ms": timings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embedding-model", default="m3e-base")
    parser.add_argument("--reranker-model", default="bge-reranker-base")
    parser.add_argument("--query", default=SMOKE_QUERY)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--persist-root",
        type=Path,
        default=Path("data/indexes/smoke_test"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        report = run_smoke_test(
            embedding_model=args.embedding_model,
            reranker_model=args.reranker_model,
            query=args.query,
            top_k=args.top_k,
            persist_root=args.persist_root,
        )
    except Exception as exc:  # noqa: BLE001 - report real environment failures clearly.
        report = {
            "status": "failed",
            "python": sys.version.split()[0],
            "error": _error_chain(exc),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
