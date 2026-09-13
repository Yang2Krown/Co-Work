"""PDF loading with switchable PyPDF2, pdfplumber, and PyMuPDF engines."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..exceptions import DocumentLoadError
from ..schemas import Document
from .base import PathLike, document_id_for, ensure_file


PDF_ENGINES = ("pypdf2", "pdfplumber", "pymupdf")
_ENGINE_ALIASES = {
    "pypdf": "pypdf2",
    "pypdf2": "pypdf2",
    "pdfplumber": "pdfplumber",
    "fitz": "pymupdf",
    "mupdf": "pymupdf",
    "pymupdf": "pymupdf",
}


def _normalize_engine(engine: str) -> str:
    normalized = _ENGINE_ALIASES.get(engine.strip().lower())
    if normalized is None:
        supported = ", ".join(PDF_ENGINES)
        raise DocumentLoadError(
            "Unsupported PDF engine '" + engine + "'. Choose one of: " + supported
        )
    return normalized


def _load_with_pypdf2(path: Path) -> Tuple[List[str], Dict[str, Any]]:
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path), strict=False)
        pages = [(page.extract_text() or "") for page in reader.pages]
        metadata = {
            str(key).lstrip("/"): value
            for key, value in (reader.metadata or {}).items()
            if value is not None
        }
        return pages, metadata
    except ImportError as exc:
        raise DocumentLoadError(
            "PyPDF2 is required for engine 'pypdf2'"
        ) from exc
    except Exception as exc:
        raise DocumentLoadError("PyPDF2 failed to parse " + str(path)) from exc


def _load_with_pdfplumber(path: Path) -> Tuple[List[str], Dict[str, Any]]:
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            pages = [(page.extract_text() or "") for page in pdf.pages]
            metadata = dict(pdf.metadata or {})
        return pages, metadata
    except ImportError as exc:
        raise DocumentLoadError(
            "pdfplumber is required for engine 'pdfplumber'"
        ) from exc
    except Exception as exc:
        raise DocumentLoadError("pdfplumber failed to parse " + str(path)) from exc


def _load_with_pymupdf(path: Path) -> Tuple[List[str], Dict[str, Any]]:
    try:
        import fitz

        with fitz.open(str(path)) as pdf:
            pages = [page.get_text("text") or "" for page in pdf]
            metadata = dict(pdf.metadata or {})
        return pages, metadata
    except ImportError as exc:
        raise DocumentLoadError(
            "PyMuPDF is required for engine 'pymupdf'"
        ) from exc
    except Exception as exc:
        raise DocumentLoadError("PyMuPDF failed to parse " + str(path)) from exc


def _document_from_pages(
    path: Path,
    pages: List[str],
    pdf_metadata: Dict[str, Any],
) -> Document:
    page_records = [
        {"page_number": page_number, "text": text}
        for page_number, text in enumerate(pages, start=1)
    ]
    metadata: Dict[str, Any] = {
        "source_path": str(path),
        "page_count": len(page_records),
        "pages": page_records,
        "title": pdf_metadata.get("title") or path.stem,
    }
    if pdf_metadata:
        metadata["pdf_metadata"] = pdf_metadata

    return Document(
        document_id=document_id_for(path),
        file_name=path.name,
        file_type="pdf",
        text="\n\f\n".join(page["text"] for page in page_records),
        metadata=metadata,
    )


def load_pdf(path: PathLike, engine: str = "pymupdf") -> Document:
    """Load a PDF using a selectable parser while retaining page metadata."""

    file_path = ensure_file(path)
    if file_path.suffix.lower() != ".pdf":
        raise DocumentLoadError("Expected a .pdf file: " + str(file_path))
    normalized_engine = _normalize_engine(engine)

    if normalized_engine == "pypdf2":
        pages, metadata = _load_with_pypdf2(file_path)
    elif normalized_engine == "pdfplumber":
        pages, metadata = _load_with_pdfplumber(file_path)
    else:
        pages, metadata = _load_with_pymupdf(file_path)

    return _document_from_pages(file_path, pages, metadata)


__all__ = ["PDF_ENGINES", "load_pdf"]

