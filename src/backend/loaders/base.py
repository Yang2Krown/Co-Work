"""Shared loader dispatch and batch-ingestion contracts."""

from hashlib import sha256
from pathlib import Path
from typing import Callable, List, Literal, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field

from ..exceptions import BackendError, DocumentLoadError, UnsupportedFileTypeError
from ..schemas import Document


PathLike = Union[str, Path]
IngestionStatus = Literal["pending", "processing", "success", "failed"]
LoaderFunction = Callable[[PathLike], Document]


class _LoaderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestionItem(_LoaderModel):
    """Per-file status and output for a batch ingestion attempt."""

    path: str
    status: IngestionStatus = "pending"
    document: Optional[Document] = None
    error: Optional[str] = None
    attempts: int = Field(default=0, ge=0)


class IngestionResult(_LoaderModel):
    """Stable result returned by batch document ingestion."""

    items: List[IngestionItem] = Field(default_factory=list)
    successful_files: List[str] = Field(default_factory=list)
    failed_files: List[str] = Field(default_factory=list)
    processed_chunk_count: int = Field(default=0, ge=0)
    index_version: Optional[str] = None
    errors: dict[str, str] = Field(default_factory=dict)


def ensure_file(path: PathLike) -> Path:
    """Return a file path or raise a clear document loading error."""

    file_path = Path(path)
    if not file_path.exists():
        raise DocumentLoadError("Document file does not exist: " + str(file_path))
    if not file_path.is_file():
        raise DocumentLoadError("Document path is not a file: " + str(file_path))
    return file_path


def document_id_for(path: PathLike) -> str:
    """Create a stable content-based document ID for incremental workflows."""

    file_path = ensure_file(path)
    return sha256(file_path.read_bytes()).hexdigest()


def load_file(path: PathLike) -> Document:
    """Dispatch a supported file to its format-specific loader."""

    file_path = ensure_file(path)
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        from .pdf_loader import load_pdf

        return load_pdf(file_path)
    if extension == ".docx":
        from .docx_loader import load_docx

        return load_docx(file_path)
    if extension in {".txt", ".md"}:
        from .text_loader import load_text

        return load_text(file_path)

    raise UnsupportedFileTypeError(
        "Unsupported document type '"
        + (extension or "<none>")
        + "'. Supported types: .pdf, .docx, .txt, .md"
    )


def _attempt_ingestion(item: IngestionItem) -> None:
    item.status = "processing"
    item.attempts += 1
    item.error = None
    try:
        item.document = load_file(item.path)
        item.status = "success"
    except BackendError as exc:
        item.document = None
        item.status = "failed"
        item.error = str(exc)
    except Exception as exc:  # noqa: BLE001 - isolate one bad file in a batch.
        item.document = None
        item.status = "failed"
        item.error = f"{exc.__class__.__name__}: {exc}"


def _refresh_result_summary(result: IngestionResult) -> None:
    result.successful_files = [
        item.path for item in result.items if item.status == "success"
    ]
    result.failed_files = [
        item.path for item in result.items if item.status == "failed"
    ]
    result.errors = {
        item.path: item.error or "Unknown document loading error"
        for item in result.items
        if item.status == "failed"
    }


def ingest_documents(paths: Sequence[PathLike]) -> IngestionResult:
    """Load multiple documents without aborting when one file fails."""

    result = IngestionResult(
        items=[IngestionItem(path=str(Path(path))) for path in paths]
    )
    for item in result.items:
        _attempt_ingestion(item)
    _refresh_result_summary(result)
    return result


def retry_failed_documents(result: IngestionResult) -> IngestionResult:
    """Retry only failed items while retaining successful batch results."""

    for item in result.items:
        if item.status == "failed":
            item.status = "pending"
            _attempt_ingestion(item)
    _refresh_result_summary(result)
    return result


__all__ = [
    "IngestionItem",
    "IngestionResult",
    "document_id_for",
    "ensure_file",
    "ingest_documents",
    "load_file",
    "retry_failed_documents",
]

