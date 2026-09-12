"""Transparent Reciprocal Rank Fusion implementation."""

from typing import Dict, List, Sequence, Tuple

from ..schemas import RetrievalResult


def _merge_scores(
    current: RetrievalResult,
    candidate: RetrievalResult,
) -> RetrievalResult:
    updates = {}
    for field in ("vector_score", "bm25_score", "rerank_score"):
        if getattr(current, field) is None and getattr(candidate, field) is not None:
            updates[field] = getattr(candidate, field)
    return current.model_copy(update=updates) if updates else current


def rrf_fuse(
    ranked_lists: Sequence[Sequence[RetrievalResult]],
    k: int = 60,
) -> List[RetrievalResult]:
    """Fuse ranked lists with ``sum(1 / (k + rank))`` using 1-based ranks."""

    if k <= 0:
        raise ValueError("RRF k must be greater than zero")

    scores: Dict[str, float] = {}
    representatives: Dict[str, RetrievalResult] = {}
    first_seen: Dict[str, int] = {}
    seen_order = 0
    for ranked_list in ranked_lists:
        seen_in_list = set()
        for rank, result in enumerate(ranked_list, start=1):
            if result.chunk_id in seen_in_list:
                continue
            seen_in_list.add(result.chunk_id)
            chunk_id = result.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in representatives:
                representatives[chunk_id] = result
                first_seen[chunk_id] = seen_order
                seen_order += 1
            else:
                representatives[chunk_id] = _merge_scores(
                    representatives[chunk_id], result
                )

    ordered_ids = sorted(
        scores,
        key=lambda chunk_id: (-scores[chunk_id], first_seen[chunk_id], chunk_id),
    )
    return [
        representatives[chunk_id].model_copy(
            update={"rrf_score": scores[chunk_id], "rank": rank}
        )
        for rank, chunk_id in enumerate(ordered_ids, start=1)
    ]


__all__ = ["rrf_fuse"]
