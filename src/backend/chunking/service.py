"""Shared chunk construction, page mapping, and strategy dispatch."""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..schemas import Chunk, Document


PageSpan = Tuple[int, int, Optional[int]]
TextSpan = Tuple[int, int]


def _validate_chunk_parameters(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")


def _text_and_page_spans(document: Document) -> Tuple[str, List[PageSpan]]:
    """Return text and page spans when the loader supplied page metadata."""

    pages = document.metadata.get("pages")
    if not isinstance(pages, list) or not pages:
        return document.text, [(0, len(document.text), None)]

    page_texts: List[str] = []
    page_numbers: List[Optional[int]] = []
    for page in pages:
        if not isinstance(page, dict) or "text" not in page:
            return document.text, [(0, len(document.text), None)]
        page_texts.append(str(page["text"]))
        raw_page_number = page.get("page_number")
        page_numbers.append(
            int(raw_page_number) if raw_page_number is not None else None
        )

    separator = "\n\f\n"
    reconstructed_text = separator.join(page_texts)
    if reconstructed_text != document.text:
        return document.text, [(0, len(document.text), None)]

    spans: List[PageSpan] = []
    cursor = 0
    for index, page_text in enumerate(page_texts):
        end = cursor + len(page_text)
        spans.append((cursor, end, page_numbers[index]))
        cursor = end
        if index < len(page_texts) - 1:
            cursor += len(separator)
    return document.text, spans


def _page_numbers_for_range(
    start: int,
    end: int,
    page_spans: Sequence[PageSpan],
) -> List[int]:
    page_numbers: List[int] = []
    for page_start, page_end, page_number in page_spans:
        if page_number is None:
            continue
        if start < page_end and end > page_start:
            page_numbers.append(page_number)
    return page_numbers


def _chunk_metadata(
    document: Document,
    strategy: str,
    chunk_index: int,
    start: int,
    end: int,
    page_numbers: Sequence[int],
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "strategy": strategy,
        "chunk_index": chunk_index,
        "start_char": start,
        "end_char": end,
        "page_numbers": list(page_numbers),
    }
    for key in ("source_path", "title"):
        if key in document.metadata:
            metadata[key] = document.metadata[key]
    return metadata


def chunks_from_spans(
    document: Document,
    spans: Iterable[TextSpan],
    strategy: str,
) -> List[Chunk]:
    """Convert text ranges into traceable unified Chunk models."""

    text, page_spans = _text_and_page_spans(document)
    chunks: List[Chunk] = []
    for index, (start, end) in enumerate(spans):
        if start < 0 or end > len(text) or start >= end:
            continue
        page_numbers = _page_numbers_for_range(start, end, page_spans)
        chunks.append(
            Chunk(
                chunk_id=f"{document.document_id}:{strategy}:{index}",
                document_id=document.document_id,
                text=text[start:end],
                page_number=page_numbers[0] if page_numbers else None,
                file_name=document.file_name,
                metadata=_chunk_metadata(
                    document, strategy, index, start, end, page_numbers
                ),
            )
        )
    return chunks


def fixed_spans(text_length: int, chunk_size: int, chunk_overlap: int) -> List[TextSpan]:
    """Return fixed-size character windows with validated overlap."""

    _validate_chunk_parameters(chunk_size, chunk_overlap)
    if text_length <= 0:
        return []
    spans: List[TextSpan] = []
    start = 0
    step = chunk_size - chunk_overlap
    while start < text_length:
        end = min(start + chunk_size, text_length)
        spans.append((start, end))
        if end == text_length:
            break
        start += step
    return spans


def _pack_spans(
    units: Sequence[TextSpan],
    chunk_size: int,
    chunk_overlap: int,
) -> List[TextSpan]:
    """Pack semantic units while keeping a bounded character overlap."""

    _validate_chunk_parameters(chunk_size, chunk_overlap)
    packed: List[TextSpan] = []
    current_start: Optional[int] = None
    current_end: Optional[int] = None

    for unit_start, unit_end in units:
        if unit_start >= unit_end:
            continue
        if unit_end - unit_start > chunk_size:
            if current_start is not None and current_end is not None:
                packed.append((current_start, current_end))
                current_start = None
                current_end = None
            local_spans = fixed_spans(unit_end - unit_start, chunk_size, chunk_overlap)
            # The long unit spans are local; shift them back to document offsets.
            packed.extend(
                (start + unit_start, end + unit_start)
                for start, end in local_spans
            )
            continue

        if current_start is None or current_end is None:
            current_start, current_end = unit_start, unit_end
            continue

        if unit_end - current_start <= chunk_size:
            current_end = unit_end
            continue

        packed.append((current_start, current_end))
        next_start = max(current_start, current_end - chunk_overlap)
        if unit_end - next_start > chunk_size:
            next_start = unit_start
        current_start, current_end = next_start, unit_end

    if current_start is not None and current_end is not None:
        packed.append((current_start, current_end))
    return packed


def chunks_from_units(
    document: Document,
    units: Sequence[TextSpan],
    strategy: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Chunk]:
    text, _ = _text_and_page_spans(document)
    spans = _pack_spans(units, chunk_size, chunk_overlap)
    spans = [(start, min(end, len(text))) for start, end in spans]
    return chunks_from_spans(document, spans, strategy)


def supported_strategies() -> Tuple[str, ...]:
    return ("fixed", "recursive", "semantic", "structure")


def chunk_document(
    document: Document,
    strategy: str = "recursive",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> List[Chunk]:
    """Chunk a Document using one of the configured M2 strategies."""

    normalized_strategy = strategy.strip().lower()
    if normalized_strategy == "fixed":
        from .fixed import fixed_size_chunks

        return fixed_size_chunks(document, chunk_size, chunk_overlap)
    if normalized_strategy == "recursive":
        from .recursive import recursive_chunks

        return recursive_chunks(document, chunk_size, chunk_overlap)
    if normalized_strategy == "semantic":
        from .semantic import semantic_chunks

        return semantic_chunks(document, chunk_size, chunk_overlap)
    if normalized_strategy in {"structure", "paragraph"}:
        from .semantic import paragraph_chunks

        return paragraph_chunks(document, chunk_size, chunk_overlap)
    raise ValueError(
        "Unknown chunking strategy '"
        + strategy
        + "'. Choose one of: "
        + ", ".join(supported_strategies())
    )


__all__ = [
    "chunks_from_spans",
    "chunks_from_units",
    "chunk_document",
    "fixed_spans",
    "supported_strategies",
]
