"""Configurable lazy-loaded cross-encoder reranker."""

from typing import Any, Dict, List, Sequence

import numpy as np

from ..exceptions import RerankerError
from ..schemas import RetrievalResult


RERANKER_MODELS: Dict[str, str] = {
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
}


class Reranker:
    """Reorder RRF candidates with a configurable cross-encoder."""

    def __init__(
        self,
        model_name: str = "bge-reranker-base",
        enabled: bool = True,
        batch_size: int = 16,
        model: Any = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        self.model_name = model_name
        self.enabled = enabled
        self.batch_size = batch_size
        self._model = model

    @property
    def resolved_model_name(self) -> str:
        return RERANKER_MODELS.get(self.model_name.lower(), self.model_name)

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.resolved_model_name)
            return self._model
        except ImportError as exc:
            raise RerankerError(
                "sentence-transformers is required for reranking"
            ) from exc
        except Exception as exc:
            raise RerankerError(
                "Unable to load reranker model " + self.resolved_model_name
            ) from exc

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        if not candidates:
            return []
        if not self.enabled:
            return [
                candidate.model_copy(update={"rank": rank})
                for rank, candidate in enumerate(candidates[:top_k], start=1)
            ]
        if not query.strip():
            raise RerankerError("Reranker query must not be empty")

        pairs = [(query, candidate.text) for candidate in candidates]
        try:
            scores = np.asarray(
                self._get_model().predict(pairs, batch_size=self.batch_size),
                dtype=np.float32,
            ).reshape(-1)
        except RerankerError:
            raise
        except Exception as exc:
            raise RerankerError("Reranker scoring failed") from exc
        if len(scores) != len(candidates):
            raise RerankerError("Reranker returned an invalid score count")

        ranked = sorted(
            zip(candidates, scores),
            key=lambda item: (-float(item[1]), item[0].chunk_id),
        )[:top_k]
        return [
            candidate.model_copy(
                update={"rerank_score": float(score), "rank": rank}
            )
            for rank, (candidate, score) in enumerate(ranked, start=1)
        ]


__all__ = ["RERANKER_MODELS", "Reranker"]
