"""Compare measured extraction output from the supported PDF loaders."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.loaders import PDF_ENGINES, load_pdf


def _text_anomalies(text: str) -> List[str]:
    """Report deterministic extraction anomalies without judging content quality."""

    anomalies: List[str] = []
    if not text.strip():
        anomalies.append("empty_text")
    if "\ufffd" in text:
        anomalies.append("replacement_character")
    control_count = sum(
        1 for character in text if ord(character) < 32 and character not in "\n\r\t\f"
    )
    if control_count:
        anomalies.append(f"control_characters:{control_count}")
    return anomalies


def compare(paths: Iterable[Path], engines: Iterable[str]) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    for path in paths:
        for engine in engines:
            started = perf_counter()
            record: Dict[str, Any] = {
                "path": str(path),
                "engine": engine,
            }
            try:
                document = load_pdf(path, engine=engine)
                pages = document.metadata.get("pages", [])
                page_texts = [page.get("text", "") for page in pages if isinstance(page, dict)]
                record.update(
                    {
                        "success": True,
                        "document_id": document.document_id,
                        "page_count": len(page_texts),
                        "nonempty_page_count": sum(bool(text.strip()) for text in page_texts),
                        "character_count": len(document.text),
                        "text_sha256": hashlib.sha256(
                            document.text.encode("utf-8")
                        ).hexdigest(),
                        "text_anomalies": _text_anomalies(document.text),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - one engine must not hide another.
                record.update(
                    {
                        "success": False,
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )
            record["elapsed_ms"] = (perf_counter() - started) * 1000
            records.append(record)
    return {"records": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="+", type=Path)
    parser.add_argument("--engines", nargs="+", choices=PDF_ENGINES, default=list(PDF_ENGINES))
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    report = compare(args.documents, args.engines)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if all(record["success"] for record in report["records"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
