"""UTF-8 TXT and Markdown loading."""

from typing import Any, Dict

from ..exceptions import DocumentLoadError
from ..schemas import Document
from .base import PathLike, document_id_for, ensure_file


def load_text(path: PathLike) -> Document:
    """Load a TXT or Markdown file as strict UTF-8 text."""

    file_path = ensure_file(path)
    extension = file_path.suffix.lower()
    if extension not in {".txt", ".md"}:
        raise DocumentLoadError("Expected a .txt or .md file: " + str(file_path))

    try:
        text = file_path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentLoadError(
            "Unable to decode "
            + str(file_path)
            + " as UTF-8; please convert the file to UTF-8."
        ) from exc
    except OSError as exc:
        raise DocumentLoadError("Unable to read " + str(file_path)) from exc

    metadata: Dict[str, Any] = {
        "source_path": str(file_path),
        "title": file_path.stem,
        "encoding": "utf-8",
    }
    return Document(
        document_id=document_id_for(file_path),
        file_name=file_path.name,
        file_type=extension.lstrip("."),
        text=text,
        metadata=metadata,
    )


def load_txt(path: PathLike) -> Document:
    """Explicit TXT loader alias."""

    file_path = ensure_file(path)
    if file_path.suffix.lower() != ".txt":
        raise DocumentLoadError("Expected a .txt file: " + str(file_path))
    return load_text(file_path)


def load_markdown(path: PathLike) -> Document:
    """Explicit Markdown loader alias."""

    file_path = ensure_file(path)
    if file_path.suffix.lower() != ".md":
        raise DocumentLoadError("Expected a .md file: " + str(file_path))
    return load_text(file_path)


__all__ = ["load_markdown", "load_text", "load_txt"]

