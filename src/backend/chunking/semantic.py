"""Sentence- and paragraph-aware structural chunking."""

from typing import List, Tuple

from ..schemas import Chunk, Document
from .service import TextSpan, chunks_from_units, _validate_chunk_parameters


_SENTENCE_TERMINATORS = set("。！？!?；")
_CLOSING_MARKS = set('"\'”’）)]】》')


def _sentence_spans(text: str) -> List[TextSpan]:
    spans: List[TextSpan] = []
    start = 0
    for index, character in enumerate(text):
        is_english_terminator = character in ".!?" and (
            index + 1 == len(text) or text[index + 1].isspace()
        )
        if character not in _SENTENCE_TERMINATORS and not is_english_terminator:
            continue
        end = index + 1
        while end < len(text) and text[end] in _CLOSING_MARKS:
            end += 1
        if end > start:
            spans.append((start, end))
            start = end
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _paragraph_spans(text: str) -> List[TextSpan]:
    spans: List[TextSpan] = []
    start = 0
    index = 0
    while index < len(text) - 1:
        if text[index] == "\n" and text[index + 1] == "\n":
            end = index + 2
            while end < len(text) and text[end] in " \t\n":
                end += 1
            spans.append((start, end))
            start = end
            index = end
            continue
        index += 1
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def semantic_chunks(
    document: Document,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """Pack sentence units while avoiding unnecessary mid-sentence cuts."""

    _validate_chunk_parameters(chunk_size, chunk_overlap)
    return chunks_from_units(
        document,
        _sentence_spans(document.text),
        "semantic",
        chunk_size,
        chunk_overlap,
    )


def paragraph_chunks(
    document: Document,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """Pack paragraph units, falling back to smaller units for long paragraphs."""

    _validate_chunk_parameters(chunk_size, chunk_overlap)
    return chunks_from_units(
        document,
        _paragraph_spans(document.text),
        "structure",
        chunk_size,
        chunk_overlap,
    )


__all__ = ["paragraph_chunks", "semantic_chunks"]

