"""Configurable local and DashScope embedding service."""

from dataclasses import dataclass
import json
import os
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

from ..env import load_dotenv
from ..exceptions import EmbeddingError


EMBEDDING_MODELS: Dict[str, str] = {
    "bge-large-zh": "BAAI/bge-large-zh-v1.5",
    "m3e-base": "moka-ai/m3e-base",
    "qwen3.7-text-embedding": "qwen3.7-text-embedding",
    "qwen3.7-text-embedding-flash": "qwen3.7-text-embedding-flash",
    "text-embedding-v4": "text-embedding-v4",
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
    """Generate embeddings locally or through DashScope's compatible API.

    DashScope requests are made only when embedding is invoked. API keys and
    workspace hosts stay in environment variables, never in source code.
    """

    def __init__(
        self,
        model_name: str = "bge-large-zh",
        batch_size: int = 32,
        device: Optional[str] = None,
        normalize_embeddings: bool = True,
        model: Any = None,
        provider: str = "local",
        api_base: Optional[str] = None,
        api_base_env: str = "DASHSCOPE_API_BASE",
        api_key_env: str = "DASHSCOPE_API_KEY",
        timeout_seconds: float = 60.0,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if provider not in {"local", "dashscope"}:
            raise ValueError("provider must be 'local' or 'dashscope'")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self._model = model
        self.provider = provider
        self.api_base = api_base
        self.api_base_env = api_base_env
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
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

    def _dashscope_endpoint(self) -> str:
        api_base = (self.api_base or os.getenv(self.api_base_env, "")).strip()
        if not api_base:
            raise EmbeddingError(
                "DashScope embedding endpoint is not configured; set "
                + self.api_base_env
            )
        if not api_base.startswith(("https://", "http://")):
            raise EmbeddingError("DashScope embedding endpoint must be an HTTP(S) URL")
        return api_base.rstrip("/") + "/embeddings"

    def _dashscope_embeddings(self, texts: Sequence[str]) -> List[List[float]]:
        load_dotenv()
        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            raise EmbeddingError(
                "DashScope API key is not set in environment variable " + self.api_key_env
            )
        payload = json.dumps(
            {"model": self.resolved_model_name, "input": list(texts)},
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self._dashscope_endpoint(),
            data=payload,
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise EmbeddingError(
                "DashScope embedding request failed with HTTP " + str(exc.code)
            ) from exc
        except URLError as exc:
            raise EmbeddingError("DashScope embedding request could not be completed") from exc
        except OSError as exc:
            raise EmbeddingError("DashScope embedding request failed") from exc
        try:
            decoded = json.loads(body)
            items = decoded["data"]
            ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
            vectors = [item["embedding"] for item in ordered]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EmbeddingError("DashScope returned an invalid embedding response") from exc
        if len(vectors) != len(texts):
            raise EmbeddingError("DashScope returned an unexpected embedding count")
        return vectors

    def _normalize(self, matrix: np.ndarray) -> np.ndarray:
        if not self.normalize_embeddings:
            return matrix
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if np.any(~np.isfinite(norms)) or np.any(norms == 0):
            raise EmbeddingError("Embedding model returned a non-finite or zero vector")
        return matrix / norms

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
            if self.provider == "dashscope":
                batches = [
                    list(texts)[index : index + self.batch_size]
                    for index in range(0, len(texts), self.batch_size)
                ]
                encoded = [
                    vector for batch in batches for vector in self._dashscope_embeddings(batch)
                ]
            else:
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
        if self.provider == "dashscope":
            matrix = self._normalize(matrix)

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
