"""Measure embedding speed and optional vector retrieval quality by model."""

import argparse
import json
import resource
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
from src.backend.retrieval import VectorRetriever
from src.backend.vectorstores import InMemoryVectorStore


def _max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _matches(result: Any, row: Dict[str, Any]) -> bool:
    if result.chunk_id in row.get("relevant_chunk_ids", []):
        return True
    if result.document_id not in row.get("relevant_document_ids", []):
        return False
    pages = row.get("relevant_page_numbers")
    return pages is None or result.page_number in pages


def _quality(retriever: VectorRetriever, rows: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    hits: List[float] = []
    reciprocal_ranks: List[float] = []
    for row in rows:
        results = retriever.retrieve(row["question"], top_k=5)
        hits.append(float(any(_matches(result, row) for result in results)))
        rank_score = 0.0
        for rank, result in enumerate(results, start=1):
            if _matches(result, row):
                rank_score = 1.0 / rank
                break
        reciprocal_ranks.append(rank_score)
    count = len(rows)
    return {
        "query_count": count,
        "hit_at_5": sum(hits) / count,
        "mrr": sum(reciprocal_ranks) / count,
    }


def compare(
    paths: Iterable[Path],
    models: Iterable[str],
    config: Any,
    evaluation_rows: Sequence[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    batch = ingest_documents(list(paths))
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
    texts = [chunk.text for chunk in chunks]
    records: List[Dict[str, Any]] = []
    for model_name in models:
        before_rss = _max_rss_bytes()
        service = EmbeddingService(
            model_name=model_name,
            batch_size=config.embedding.batch_size,
            normalize_embeddings=config.embedding.normalize_embeddings,
        )
        cold_started = perf_counter()
        embeddings = service.embed_documents(texts)
        cold_ms = (perf_counter() - cold_started) * 1000
        warm_started = perf_counter()
        service.embed_documents(texts)
        warm_ms = (perf_counter() - warm_started) * 1000
        after_rss = _max_rss_bytes()
        store = InMemoryVectorStore()
        store.add_chunks(chunks, embeddings)
        retriever = VectorRetriever(store, service, top_k=config.retrieval.vector_top_k)
        record: Dict[str, Any] = {
            "model": model_name,
            "resolved_model": service.resolved_model_name,
            "chunk_count": len(chunks),
            "embedding_dimension": service.last_stats.dimension if service.last_stats else 0,
            "cold_first_run_ms": cold_ms,
            "warm_inference_ms": warm_ms,
            "warm_items_per_second": len(texts) / max(warm_ms / 1000, 1e-12),
            "max_rss_delta_bytes": max(0, after_rss - before_rss),
        }
        if evaluation_rows is not None:
            record["retrieval_quality"] = _quality(retriever, evaluation_rows)
        records.append(record)
    return {"records": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="+", type=Path)
    parser.add_argument("--models", nargs="+", default=["bge-large-zh", "m3e-base"])
    parser.add_argument("--evaluation", type=Path, help="Optional real JSONL QA set")
    parser.add_argument("--config", type=Path, default=Path("config/backend.yaml"))
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    config = load_config(args.config)
    rows = None
    if args.evaluation:
        from scripts.evaluate_retrieval import load_evaluation_set

        rows = load_evaluation_set(args.evaluation)
    report = compare(args.documents, args.models, config, rows)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
