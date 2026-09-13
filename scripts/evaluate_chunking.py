"""Compare chunking strategies on real input documents.

Without ``--evaluation`` this script reports chunk statistics only. With a
real JSONL evaluation set it additionally measures vector Hit@5 and MRR for
each chunking strategy and size. No retrieval metric is produced without that
set.
"""

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.chunking import chunk_document, supported_strategies
from src.backend.embeddings import EmbeddingService
from src.backend.loaders import load_file
from src.backend.retrieval import VectorRetriever
from src.backend.vectorstores import InMemoryVectorStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Input documents")
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=supported_strategies(),
        default=list(supported_strategies()),
    )
    parser.add_argument(
        "--chunk-size",
        nargs="+",
        type=int,
        default=[256, 512, 1024],
        help="Chunk sizes to compare (default: 256 512 1024)",
    )
    parser.add_argument("--chunk-overlap", type=int, default=64)
    parser.add_argument(
        "--evaluation",
        type=Path,
        help="Optional real JSONL QA set; enables vector Hit@5/MRR measurements",
    )
    parser.add_argument(
        "--embedding-model",
        default="m3e-base",
        help="Embedding alias used only with --evaluation (default: m3e-base)",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser


def evaluate(paths: Iterable[Path], strategies: Iterable[str], sizes: Iterable[int], overlap: int) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for path in paths:
        try:
            document = load_file(path)
        except Exception as exc:  # noqa: BLE001 - report one bad input and continue.
            errors.append(
                {"path": str(path), "error": f"{exc.__class__.__name__}: {exc}"}
            )
            continue
        for strategy in strategies:
            for size in sizes:
                try:
                    chunks = chunk_document(
                        document,
                        strategy=strategy,
                        chunk_size=size,
                        chunk_overlap=overlap,
                    )
                except Exception as exc:  # noqa: BLE001 - preserve batch comparison.
                    errors.append(
                        {
                            "path": str(path),
                            "strategy": strategy,
                            "chunk_size": str(size),
                            "error": f"{exc.__class__.__name__}: {exc}",
                        }
                    )
                    continue
                lengths = [len(chunk.text) for chunk in chunks]
                records.append(
                    {
                        "path": str(path),
                        "document_id": document.document_id,
                        "strategy": strategy,
                        "chunk_size": size,
                        "chunk_overlap": overlap,
                        "chunk_count": len(chunks),
                        "min_chars": min(lengths) if lengths else 0,
                        "max_chars": max(lengths) if lengths else 0,
                        "avg_chars": (sum(lengths) / len(lengths)) if lengths else 0,
                        "avg_chunk_length": (sum(lengths) / len(lengths)) if lengths else 0,
                    }
                )
    return {"records": records, "errors": errors}


def _result_matches(result: Any, row: Dict[str, Any]) -> bool:
    if result.chunk_id in row.get("relevant_chunk_ids", []):
        return True
    if result.document_id not in row.get("relevant_document_ids", []):
        return False
    pages = row.get("relevant_page_numbers")
    return pages is None or result.page_number in pages


def _evaluate_vector_quality(
    documents: Sequence[Any],
    strategies: Iterable[str],
    sizes: Iterable[int],
    overlap: int,
    evaluation_rows: Sequence[Dict[str, Any]],
    embedding_model: str,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for strategy in strategies:
        for size in sizes:
            chunks = [
                chunk
                for document in documents
                for chunk in chunk_document(
                    document,
                    strategy=strategy,
                    chunk_size=size,
                    chunk_overlap=overlap,
                )
            ]
            index_started = perf_counter()
            embedding_service = EmbeddingService(model_name=embedding_model)
            store = InMemoryVectorStore()
            store.add_chunks(
                chunks,
                embedding_service.embed_documents([chunk.text for chunk in chunks]),
            )
            index_build_ms = (perf_counter() - index_started) * 1000
            retriever = VectorRetriever(store, embedding_service, top_k=5)
            hits: List[float] = []
            reciprocal_ranks: List[float] = []
            query_latencies: List[float] = []
            for row in evaluation_rows:
                query_started = perf_counter()
                results = retriever.retrieve(row["question"], top_k=5)
                query_latencies.append((perf_counter() - query_started) * 1000)
                hits.append(float(any(_result_matches(result, row) for result in results)))
                reciprocal_rank = 0.0
                for rank, result in enumerate(results, start=1):
                    if _result_matches(result, row):
                        reciprocal_rank = 1.0 / rank
                        break
                reciprocal_ranks.append(reciprocal_rank)
            count = len(evaluation_rows)
            records.append(
                {
                    "strategy": strategy,
                    "chunk_size": size,
                    "chunk_overlap": overlap,
                    "chunk_count": len(chunks),
                    "avg_chunk_length": (
                        sum(len(chunk.text) for chunk in chunks) / len(chunks)
                        if chunks
                        else 0
                    ),
                    "embedding_model": embedding_model,
                    "query_count": count,
                    "hit_at_5": sum(hits) / count,
                    "mrr": sum(reciprocal_ranks) / count,
                    "index_build_ms": index_build_ms,
                    "average_query_ms": sum(query_latencies) / count,
                }
            )
    return records


def main() -> int:
    args = _build_parser().parse_args()
    report = evaluate(args.paths, args.strategies, args.chunk_size, args.chunk_overlap)
    if args.evaluation:
        from scripts.evaluate_retrieval import load_evaluation_set

        documents = []
        for path in args.paths:
            documents.append(load_file(path))
        report["evaluation"] = {
            "records": _evaluate_vector_quality(
                documents,
                args.strategies,
                args.chunk_size,
                args.chunk_overlap,
                load_evaluation_set(args.evaluation),
                args.embedding_model,
            )
        }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
