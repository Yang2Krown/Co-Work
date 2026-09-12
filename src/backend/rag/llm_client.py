"""Provider-neutral LLM boundary and OpenAI-compatible HTTP transport."""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..exceptions import LLMServiceError
from .prompt import RAGPrompt


@dataclass(frozen=True)
class GenerationConfig:
    """Generation parameters forwarded to an LLM provider."""

    temperature: float = 0.2
    top_p: float = 0.9
    top_k: Optional[int] = None
    max_output_tokens: int = 512

    def __post_init__(self) -> None:
        if self.temperature < 0:
            raise ValueError("temperature must be non-negative")
        if not 0 < self.top_p <= 1:
            raise ValueError("top_p must be in the interval (0, 1]")
        if self.top_k is not None and self.top_k <= 0:
            raise ValueError("top_k must be greater than zero when provided")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be greater than zero")


@dataclass(frozen=True)
class LLMResponse:
    text: str
    token_usage: Optional[Dict[str, Any]] = None


class LLMClient(Protocol):
    def generate(self, prompt: RAGPrompt, config: GenerationConfig) -> LLMResponse:
        """Generate one complete response."""

    def stream(self, prompt: RAGPrompt, config: GenerationConfig) -> Iterator[str]:
        """Yield response text fragments."""


class OpenAICompatibleClient:
    """Minimal JSON/SSE client for OpenAI-compatible chat endpoints."""

    def __init__(
        self,
        model_name: str,
        api_base: str,
        api_key_env: str = "OPENAI_API_KEY",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if not api_base.strip():
            raise ValueError("api_base must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.model_name = model_name
        self.api_base = api_base.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

    @property
    def endpoint(self) -> str:
        if self.api_base.endswith("/chat/completions"):
            return self.api_base
        return self.api_base + "/chat/completions"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key_env:
            api_key = os.getenv(self.api_key_env)
            if not api_key:
                raise LLMServiceError(
                    "LLM API key is not set in environment variable " + self.api_key_env
                )
            headers["Authorization"] = "Bearer " + api_key
        return headers

    def _payload(
        self,
        prompt: RAGPrompt,
        config: GenerationConfig,
        stream: bool,
    ) -> bytes:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": prompt.messages,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_output_tokens,
            "stream": stream,
        }
        if config.top_k is not None:
            payload["top_k"] = config.top_k
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _request(self, prompt: RAGPrompt, config: GenerationConfig, stream: bool):
        request = Request(
            self.endpoint,
            data=self._payload(prompt, config, stream),
            headers=self._headers(),
            method="POST",
        )
        try:
            return urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except OSError:
                detail = str(exc)
            raise LLMServiceError(f"LLM HTTP error {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LLMServiceError("LLM request failed: " + str(exc)) from exc

    @staticmethod
    def _message_text(message: Any) -> str:
        if isinstance(message, str):
            return message
        if isinstance(message, list):
            return "".join(
                part.get("text", "")
                for part in message
                if isinstance(part, Mapping) and isinstance(part.get("text"), str)
            )
        return ""

    def generate(self, prompt: RAGPrompt, config: GenerationConfig) -> LLMResponse:
        with self._request(prompt, config, stream=False) as response:
            try:
                payload = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LLMServiceError("LLM returned invalid JSON") from exc

        try:
            choice = payload["choices"][0]
            text = self._message_text(choice["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMServiceError("LLM response did not contain message content") from exc
        if not text:
            raise LLMServiceError("LLM returned an empty response")
        usage = payload.get("usage")
        return LLMResponse(
            text=text,
            token_usage=dict(usage) if isinstance(usage, Mapping) else None,
        )

    def stream(self, prompt: RAGPrompt, config: GenerationConfig) -> Iterator[str]:
        try:
            with self._request(prompt, config, stream=True) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        payload = json.loads(data)
                        delta = payload["choices"][0].get("delta", {})
                        text = self._message_text(delta.get("content"))
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                        raise LLMServiceError("LLM stream returned invalid JSON") from exc
                    if text:
                        yield text
        except LLMServiceError:
            raise
        except (UnicodeDecodeError, OSError) as exc:
            raise LLMServiceError("LLM streaming request failed") from exc


def create_llm_client(
    provider: str,
    model_name: str,
    api_base: str,
    api_key_env: str = "OPENAI_API_KEY",
    timeout_seconds: float = 60.0,
) -> LLMClient:
    """Create the configured M5 client without performing a network call."""

    if provider.strip().lower() in {"openai", "openai_compatible"}:
        return OpenAICompatibleClient(
            model_name=model_name,
            api_base=api_base,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError("Unsupported LLM provider: " + provider)


__all__ = [
    "GenerationConfig",
    "LLMClient",
    "LLMResponse",
    "OpenAICompatibleClient",
    "create_llm_client",
]
