"""Evaluate vector, hybrid, and hybrid-rerank retrieval on a real QA set."""

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.chunking import chunk_document
from src.backend.config import load_config
from src.backend.embeddings import EmbeddingService
from src.backend.loaders import ingest_documents
from src.backend.retrieval import BM25Retriever, HybridRetriever, Reranker, VectorRetriever
from src.backend.vectorstores import InMemoryVectorStore


def hit_at_k(results: Sequence[Any], relevant_ids: Iterable[str], k: int = 5) -> float:
    relevant = set(relevant_ids)
    return float(any(result.chunk_id in relevant for result in results[:k]))


def reciprocal_rank(results: Sequence[Any], relevant_ids: Iterable[str]) -> float:
    relevant = set(relevant_ids)
    for rank, result in enumerate(results, start=1):
        if result.chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def _result_matches(result: Any, row: Dict[str, Any]) -> bool:
    relevant_chunk_ids = row.get("relevant_chunk_ids", [])
    if result.chunk_id in relevant_chunk_ids:
        return True
    relevant_document_ids = row.get("relevant_document_ids", [])
    if result.document_id not in relevant_document_ids:
        return False
    relevant_pages = row.get("relevant_page_numbers")
    return relevant_pages is None or result.page_number in relevant_pages


def _hit_at_k_row(results: Sequence[Any], row: Dict[str, Any], k: int = 5) -> float:
    return float(any(_result_matches(result, row) for result in results[:k]))


def _reciprocal_rank_row(results: Sequence[Any], row: Dict[str, Any]) -> float:
    for rank, result in enumerate(results, start=1):
        if _result_matches(result, row):
            return 1.0 / rank
    return 0.0


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def load_evaluation_set(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or not isinstance(row.get("question"), str):
            raise ValueError(f"Invalid evaluation row at line {line_number}")
        relevant_ids = row.get("relevant_chunk_ids")
        document_ids = row.get("relevant_document_ids")
        if relevant_ids is not None and (
            not isinstance(relevant_ids, list)
            or not all(isinstance(item, str) for item in relevant_ids)
        ):
            raise ValueError(
                f"Evaluation row {line_number} has invalid relevant_chunk_ids"
            )
        if document_ids is not None and (
            not isinstance(document_ids, list)
            or not all(isinstance(item, str) for item in document_ids)
        ):
            raise ValueError(
                f"Evaluation row {line_number} has invalid relevant_document_ids"
            )
        if not relevant_ids and not document_ids:
            raise ValueError(
                f"Evaluation row {line_number} needs relevant_chunk_ids or relevant_document_ids"
            )
        relevant_pages = row.get("relevant_page_numbers")
        if relevant_pages is not None and (
            not isinstance(relevant_pages, list)
            or not all(isinstance(item, int) and item > 0 for item in relevant_pages)
        ):
            raise ValueError(
                f"Evaluation row {line_number} has invalid relevant_page_numbers"
            )
        rows.append(row)
    if not rows:
        raise ValueError("Evaluation set is empty")
    return rows


def evaluate_retrieval(
    retriever: HybridRetriever,
    evaluation_rows: Sequence[Dict[str, Any]],
    chunking_strategy: str = "configured",
    chunk_size: int = 0,
    chunk_overlap: int = 0,
) -> Dict[str, Any]:
    records = []
    for mode in ("vector", "hybrid", "hybrid_rerank"):
        hits = []
        reciprocal_ranks = []
        query_latencies = []
        for row in evaluation_rows:
            started = perf_counter()
            results = retriever.retrieve(row["question"], mode=mode, top_k=5)
            query_latencies.append((perf_counter() - started) * 1000)
            hits.append(_hit_at_k_row(results, row, k=5))
            reciprocal_ranks.append(_reciprocal_rank_row(results, row))
        count = len(evaluation_rows)
        record: Dict[str, Any] = {
            "mode": mode,
            "query_count": count,
            "top_k": 5,
            "embedding_model": getattr(
                getattr(retriever.vector_retriever, "embedding_service", None),
                "model_name",
                None,
            ),
            "reranker_model": getattr(retriever.reranker, "model_name", None),
            "vector_store": type(retriever.vector_retriever.vector_store).__name__,
            "chunking_strategy": chunking_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "hit_at_5": sum(hits) / count if count else 0.0,
            "mrr": sum(reciprocal_ranks) / count if count else 0.0,
            "average_query_ms": sum(query_latencies) / count if count else 0.0,
            "p50_query_ms": _percentile(query_latencies, 0.50),
            "p95_query_ms": _percentile(query_latencies, 0.95),
        }
        if mode == "hybrid_rerank" and query_latencies:
            record["cold_first_query_ms"] = query_latencies[0]
            record["warm_average_query_ms"] = (
                sum(query_latencies[1:]) / len(query_latencies[1:])
                if len(query_latencies) > 1
                else query_latencies[0]
            )
        records.append(record)
    return {"records": records}


def _build_retriever(document_paths: Sequence[Path], config: Any) -> HybridRetriever:
    batch = ingest_documents(document_paths)
    if batch.failed_files:
        raise RuntimeError("Document ingestion failed: " + json.dumps(batch.errors))
    documents = [item.document for item in batch.items if item.document is not None]
    chunks = [
        chunk
        for document in documents
        for chunk in chunk_document(
            document,
            strategy=config.chunking.strategy,
            chunk_size=config.chunking.chunk_size,
            chunk_overlap=config.chunking.chunk_overlap,
        )
    ]
    embedding_service = EmbeddingService(
        model_name=config.embedding.model_name,
        batch_size=config.embedding.batch_size,
        normalize_embeddings=config.embedding.normalize_embeddings,
    )
    vector_store = InMemoryVectorStore()
    vector_store.add_chunks(
        chunks,
        embedding_service.embed_documents([chunk.text for chunk in chunks]),
    )
    vector_retriever = VectorRetriever(
        vector_store, embedding_service, top_k=config.retrieval.vector_top_k
    )
    return HybridRetriever(
        vector_retriever=vector_retriever,
        bm25_retriever=BM25Retriever(chunks),
        reranker=Reranker(
            model_name=config.retrieval.reranker_model_name,
            enabled=config.retrieval.enable_reranker,
            batch_size=config.retrieval.reranker_batch_size,
        ),
        vector_top_k=config.retrieval.vector_top_k,
        bm25_top_k=config.retrieval.bm25_top_k,
        final_top_k=config.retrieval.final_top_k,
        enable_bm25=config.retrieval.enable_bm25,
        enable_rrf=config.retrieval.enable_rrf,
        rrf_k=config.retrieval.rrf_k,
        enable_reranker=config.retrieval.enable_reranker,
        reranker_top_n=config.retrieval.reranker_top_n,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="+", type=Path)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/backend.yaml"))
    parser.add_argument("--embedding-model", help="Override the configured embedding alias")
    parser.add_argument("--reranker-model", help="Override the configured reranker alias")
    parser.add_argument("--chunking-strategy", help="Strategy used to create evaluation chunks")
    parser.add_argument("--chunk-size", type=int, help="Chunk size used to create evaluation chunks")
    parser.add_argument("--chunk-overlap", type=int, help="Chunk overlap used to create evaluation chunks")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    config = load_config(args.config)
    if any(
        value is not None
        for value in (
            args.embedding_model,
            args.reranker_model,
            args.chunking_strategy,
            args.chunk_size,
            args.chunk_overlap,
        )
    ):
        embedding = config.embedding.model_copy(
            update={"model_name": args.embedding_model}
            if args.embedding_model
            else {}
        )
        retrieval = config.retrieval.model_copy(
            update={"reranker_model_name": args.reranker_model}
            if args.reranker_model
            else {}
        )
        chunking = config.chunking.model_copy(
            update={
                key: value
                for key, value in {
                    "strategy": args.chunking_strategy,
                    "chunk_size": args.chunk_size,
                    "chunk_overlap": args.chunk_overlap,
                }.items()
                if value is not None
            }
        )
        config = config.model_copy(
            update={"embedding": embedding, "retrieval": retrieval, "chunking": chunking}
        )
    report = evaluate_retrieval(
        _build_retriever(args.documents, config),
        load_evaluation_set(args.evaluation),
        chunking_strategy=config.chunking.strategy,
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
