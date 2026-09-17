"""Configurable local or DashScope text reranker."""

import json
import os
from typing import Any, Dict, List, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

from ..env import load_dotenv
from ..exceptions import RerankerError
from ..schemas import RetrievalResult


RERANKER_MODELS: Dict[str, str] = {
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
    "qwen3.7-text-rerank": "qwen3.7-text-rerank",
}


class Reranker:
    """Reorder RRF candidates locally or through DashScope."""

    def __init__(
        self,
        model_name: str = "bge-reranker-base",
        enabled: bool = True,
        batch_size: int = 16,
        model: Any = None,
        provider: str = "local",
        api_base: str | None = None,
        api_base_env: str = "DASHSCOPE_API_BASE",
        api_key_env: str = "DASHSCOPE_API_KEY",
        timeout_seconds: float = 30.0,
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
        self.enabled = enabled
        self.batch_size = batch_size
        self._model = model
        self.provider = provider
        self.api_base = api_base
        self.api_base_env = api_base_env
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

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

    def _dashscope_endpoint(self) -> str:
        base = (self.api_base or os.getenv(self.api_base_env, "")).strip().rstrip("/")
        if not base:
            raise RerankerError(
                "DashScope reranker endpoint is not configured; set " + self.api_base_env
            )
        if not base.startswith(("https://", "http://")):
            raise RerankerError("DashScope reranker endpoint must be an HTTP(S) URL")
        # Embedding uses the OpenAI-compatible path. qwen3.7-text-rerank uses
        # DashScope's native rerank endpoint on the same configured host.
        if "/compatible-mode/" in base:
            base = base.split("/compatible-mode/", 1)[0]
        elif base.endswith("/v1"):
            base = base[:-3]
        return base.rstrip("/") + "/api/v1/services/rerank/text-rerank/text-rerank"

    def _dashscope_rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
        top_k: int,
    ) -> List[RetrievalResult]:
        load_dotenv()
        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            raise RerankerError(
                "DashScope API key is not set in environment variable " + self.api_key_env
            )
        payload = {
            "model": self.resolved_model_name,
            "input": {
                "query": query,
                "documents": [candidate.text for candidate in candidates],
            },
            "parameters": {"top_n": min(top_k, len(candidates)), "return_documents": False},
        }
        request = Request(
            self._dashscope_endpoint(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RerankerError(
                "DashScope rerank request failed with HTTP " + str(exc.code)
            ) from exc
        except URLError as exc:
            raise RerankerError("DashScope rerank request could not be completed") from exc
        except OSError as exc:
            raise RerankerError("DashScope rerank request failed") from exc
        try:
            results = decoded["output"]["results"]
            ranked = []
            seen = set()
            for rank, item in enumerate(results, start=1):
                index = int(item["index"])
                if index < 0 or index >= len(candidates) or index in seen:
                    raise ValueError("invalid result index")
                seen.add(index)
                ranked.append(
                    candidates[index].model_copy(
                        update={"rerank_score": float(item["relevance_score"]), "rank": rank}
                    )
                )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RerankerError("DashScope returned an invalid rerank response") from exc
        if not ranked:
            raise RerankerError("DashScope rerank returned no results")
        return ranked

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
        if self.provider == "dashscope":
            return self._dashscope_rerank(query, candidates, top_k)

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
