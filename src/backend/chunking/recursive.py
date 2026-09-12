"""Recursive separator-based chunking without a framework dependency."""

from typing import List, Sequence, Tuple

from ..schemas import Chunk, Document
from .service import TextSpan, chunks_from_units, _validate_chunk_parameters


DEFAULT_SEPARATORS = (
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    ". ",
    "! ",
    "? ",
    " ",
    "",
)


def _split_by_separator(text: str, start: int, end: int, separator: str) -> List[TextSpan]:
    if separator == "":
        return [(index, index + 1) for index in range(start, end)]

    spans: List[TextSpan] = []
    cursor = start
    while cursor < end:
        separator_start = text.find(separator, cursor, end)
        if separator_start < 0:
            break
        separator_end = separator_start + len(separator)
        if separator_end > cursor:
            spans.append((cursor, separator_end))
        cursor = separator_end
    if cursor < end:
        spans.append((cursor, end))
    return spans


def _recursive_spans(
    text: str,
    start: int,
    end: int,
    chunk_size: int,
    separators: Sequence[str],
) -> List[TextSpan]:
    if end - start <= chunk_size:
        return [(start, end)]
    if not separators:
        return [(index, index + 1) for index in range(start, end)]

    for separator_index, separator in enumerate(separators):
        if separator and text.find(separator, start, end) < 0:
            continue
        pieces = _split_by_separator(text, start, end, separator)
        if len(pieces) <= 1:
            continue
        spans: List[TextSpan] = []
        for piece_start, piece_end in pieces:
            spans.extend(
                _recursive_spans(
                    text,
                    piece_start,
                    piece_end,
                    chunk_size,
                    separators[separator_index + 1 :],
                )
            )
        return spans

    return [(index, index + 1) for index in range(start, end)]


def recursive_chunks(
    document: Document,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """Split recursively at paragraph, line, sentence, then character boundaries."""

    _validate_chunk_parameters(chunk_size, chunk_overlap)
    spans = _recursive_spans(
        document.text,
        0,
        len(document.text),
        chunk_size,
        DEFAULT_SEPARATORS,
    )
    return chunks_from_units(
        document, spans, "recursive", chunk_size, chunk_overlap
    )


__all__ = ["DEFAULT_SEPARATORS", "recursive_chunks"]

