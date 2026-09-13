"""Bounded, traceable context construction for RAG prompts."""

import re
from dataclasses import dataclass
from typing import List, Sequence

from ..schemas import RetrievalResult


@dataclass(frozen=True)
class ContextBuildResult:
    """Prompt context plus the exact retrieved chunks represented in it."""

    text: str
    chunks: List[RetrievalResult]


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


class ContextBuilder:
    """Sort, deduplicate, annotate, and truncate retrieved chunks."""

    def __init__(self, max_chars: int = 6000) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be greater than zero")
        self.max_chars = max_chars

    @staticmethod
    def _source_label(index: int, result: RetrievalResult) -> str:
        page = (
            f"p.{result.page_number}"
            if result.page_number is not None
            else "page unavailable"
        )
        return f"[{index}] {result.file_name}, {page} (chunk_id={result.chunk_id})"

    def build(self, results: Sequence[RetrievalResult]) -> ContextBuildResult:
        """Return a bounded context and only the chunks included in it."""

        ordered = sorted(enumerate(results), key=lambda item: (item[1].rank, item[0]))
        selected: List[RetrievalResult] = []
        blocks: List[str] = []
        seen_chunk_ids = set()
        seen_texts = set()
        current_length = 0

        for _, result in ordered:
            normalized = _normalized_text(result.text)
            if result.chunk_id in seen_chunk_ids or not normalized or normalized in seen_texts:
                continue

            citation_number = len(selected) + 1
            source = self._source_label(citation_number, result)
            separator = "\n\n" if blocks else ""
            available = self.max_chars - current_length - len(separator)
            if available <= 0:
                break

            text = result.text.strip()
            full_block = source + "\n" + text
            if len(full_block) > available:
                text_budget = available - len(source) - 2
                if text_budget <= 0:
                    break
                text = text[:text_budget].rstrip() + "…"
                full_block = source + "\n" + text

            if len(full_block) > available:
                break
            blocks.append(full_block)
            selected.append(result)
            seen_chunk_ids.add(result.chunk_id)
            seen_texts.add(normalized)
            current_length += len(separator) + len(full_block)

        return ContextBuildResult(text="\n\n".join(blocks), chunks=selected)


def build_context(
    results: Sequence[RetrievalResult],
    max_chars: int = 6000,
) -> ContextBuildResult:
    """Convenience wrapper around :class:`ContextBuilder`."""

    return ContextBuilder(max_chars=max_chars).build(results)


__all__ = ["ContextBuildResult", "ContextBuilder", "build_context"]
