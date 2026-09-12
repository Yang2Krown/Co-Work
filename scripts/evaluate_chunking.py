"""Compare chunking strategies on real input documents.

This script reports measured chunk statistics only. It does not invent
retrieval-quality metrics; those require a real evaluation set and retrieval
layer from later milestones.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.chunking import chunk_document, supported_strategies
from src.backend.loaders import load_file


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
                    }
                )
    return {"records": records, "errors": errors}


def main() -> int:
    args = _build_parser().parse_args()
    report = evaluate(args.paths, args.strategies, args.chunk_size, args.chunk_overlap)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

