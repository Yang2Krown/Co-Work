"""Citation construction from retrieved chunks only."""

from typing import List, Sequence

from ..schemas import Citation, RetrievalResult


def build_citations(results: Sequence[RetrievalResult]) -> List[Citation]:
    """Create traceable citations without inferring missing page numbers."""

    return [
        Citation(
            citation_id=index,
            file_name=result.file_name,
            page_number=result.page_number,
            chunk_id=result.chunk_id,
        )
        for index, result in enumerate(results, start=1)
    ]


__all__ = ["build_citations"]
