"""Fixed-size character chunking."""

from ..schemas import Chunk, Document
from .service import chunks_from_spans, fixed_spans


def fixed_size_chunks(
    document: Document,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """Split text into fixed character windows with configurable overlap."""

    return chunks_from_spans(
        document,
        fixed_spans(len(document.text), chunk_size, chunk_overlap),
        "fixed",
    )


__all__ = ["fixed_size_chunks"]

