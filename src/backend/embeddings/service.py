"""Configurable, lazy-loaded embedding service."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..exceptions import EmbeddingError


EMBEDDING_MODELS: Dict[str, str] = {
    "bge-large-zh": "BAAI/bge-large-zh-v1.5",
    "m3e-base": "moka-ai/m3e-base",
}


@dataclass(frozen=True)
class EmbeddingStats:
    """Measured statistics for the most recent embedding batch."""

    model_name: str
    item_count: int
    dimension: int
    elapsed_ms: float
    items_per_second: float


def resolve_embedding_model(model_name: str) -> str:
    """Resolve a course-facing model alias or accept a full model identifier."""

    return EMBEDDING_MODELS.get(model_name.strip().lower(), model_name)


class EmbeddingService:
    """Generate embeddings without loading or downloading models at import time."""

    def __init__(
        self,
        model_name: str = "bge-large-zh",
        batch_size: int = 32,
        device: Optional[str] = None,
        normalize_embeddings: bool = True,
        model: Any = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self._model = model
        self.last_stats: Optional[EmbeddingStats] = None

    @property
    def resolved_model_name(self) -> str:
        return resolve_embedding_model(self.model_name)

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.resolved_model_name,
                device=self.device,
            )
            return self._model
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers is required for embedding generation"
            ) from exc
        except Exception as exc:
            raise EmbeddingError(
                "Unable to load embedding model " + self.resolved_model_name
            ) from exc

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts and record basic speed/dimension statistics."""

        if not texts:
            self.last_stats = EmbeddingStats(
                model_name=self.model_name,
                item_count=0,
                dimension=0,
                elapsed_ms=0.0,
                items_per_second=0.0,
            )
            return []
        if any(not isinstance(text, str) for text in texts):
            raise EmbeddingError("All embedding inputs must be strings")

        started = perf_counter()
        try:
            encoded = self._get_model().encode(
                list(texts),
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize_embeddings,
            )
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError("Embedding generation failed") from exc

        matrix = np.asarray(encoded, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.ndim != 2 or matrix.shape[0] != len(texts):
            raise EmbeddingError("Embedding model returned an invalid shape")

        elapsed_ms = (perf_counter() - started) * 1000
        elapsed_seconds = max(elapsed_ms / 1000, 1e-12)
        self.last_stats = EmbeddingStats(
            model_name=self.model_name,
            item_count=len(texts),
            dimension=int(matrix.shape[1]),
            elapsed_ms=elapsed_ms,
            items_per_second=len(texts) / elapsed_seconds,
        )
        return matrix.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embed one query using the same model and normalization settings."""

        if not isinstance(text, str) or not text:
            raise EmbeddingError("Query text must be a non-empty string")
        return self.embed_documents([text])[0]


__all__ = ["EMBEDDING_MODELS", "EmbeddingService", "EmbeddingStats", "resolve_embedding_model"]

