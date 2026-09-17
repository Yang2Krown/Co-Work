"""Provider-neutral LLM boundary and OpenAI-compatible HTTP transport."""

import json
import os
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterator, Mapping, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..env import load_dotenv
from ..exceptions import LLMServiceError
from .prompt import RAGPrompt


@dataclass(frozen=True)
class GenerationConfig:
    """Generation parameters forwarded to an LLM provider."""

    temperature: float = 0.2
    top_p: float = 0.9
    top_k: Optional[int] = None
    # ``None`` omits max_tokens and lets the provider use its model default.
    max_output_tokens: Optional[int] = None

    def __post_init__(self) -> None:
        if self.temperature < 0:
            raise ValueError("temperature must be non-negative")
        if not 0 < self.top_p <= 1:
            raise ValueError("top_p must be in the interval (0, 1]")
        if self.top_k is not None and self.top_k <= 0:
            raise ValueError("top_k must be greater than zero when provided")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
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

    # Some reasoning models spend the first part of the completion budget on
    # hidden reasoning. Retry only the specific "length + no visible answer"
    # response, with a bounded expansion rather than retrying provider errors.
    _AUTO_EXPANSION_TOKENS = (4096, 6144, 8192)

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
        load_dotenv()
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
            "stream": stream,
        }
        if config.max_output_tokens is not None:
            payload["max_tokens"] = config.max_output_tokens
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

    @classmethod
    def _expanded_config(cls, config: GenerationConfig) -> Optional[GenerationConfig]:
        """Return the next length-recovery budget, or ``None`` when exhausted."""

        current = config.max_output_tokens
        for budget in cls._AUTO_EXPANSION_TOKENS:
            if current is None or budget > current:
                return replace(config, max_output_tokens=budget)
        return None

    @staticmethod
    def _merge_usage(
        accumulated: Optional[Dict[str, Any]],
        current: Any,
    ) -> Optional[Dict[str, Any]]:
        """Preserve token consumption from a length-recovery retry."""

        if not isinstance(current, Mapping):
            return accumulated
        merged = dict(accumulated or {})
        for key, value in current.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                previous = merged.get(key, 0)
                merged[key] = previous + value if isinstance(previous, (int, float)) else value
            elif key not in merged:
                merged[key] = value
        return merged

    @staticmethod
    def _truncated_without_text(choice: Any, text: str) -> bool:
        return (
            isinstance(choice, Mapping)
            and not text
            and str(choice.get("finish_reason", "")).lower() == "length"
        )

    def generate(self, prompt: RAGPrompt, config: GenerationConfig) -> LLMResponse:
        effective_config = config
        accumulated_usage: Optional[Dict[str, Any]] = None
        while True:
            with self._request(prompt, effective_config, stream=False) as response:
                try:
                    payload = json.loads(response.read().decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise LLMServiceError("LLM returned invalid JSON") from exc

            try:
                choice = payload["choices"][0]
                text = self._message_text(choice["message"]["content"])
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMServiceError("LLM response did not contain message content") from exc
            accumulated_usage = self._merge_usage(accumulated_usage, payload.get("usage"))
            if text:
                return LLMResponse(text=text, token_usage=accumulated_usage)
            if not self._truncated_without_text(choice, text):
                raise LLMServiceError("LLM returned an empty response")
            expanded_config = self._expanded_config(effective_config)
            if expanded_config is None:
                raise LLMServiceError("LLM returned an empty response after output-budget recovery")
            effective_config = expanded_config

    def stream(self, prompt: RAGPrompt, config: GenerationConfig) -> Iterator[str]:
        effective_config = config
        try:
            while True:
                received_text = False
                completed = False
                finish_reason = ""
                with self._request(prompt, effective_config, stream=True) as response:
                    for raw_line in response:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            completed = True
                            break
                        try:
                            payload = json.loads(data)
                            choice = payload["choices"][0]
                            delta = choice.get("delta", {})
                            text = self._message_text(delta.get("content"))
                            finish_reason = str(choice.get("finish_reason") or finish_reason)
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                            raise LLMServiceError("LLM stream returned invalid JSON") from exc
                        if text:
                            received_text = True
                            yield text
                if received_text and completed:
                    return
                if not received_text and completed and finish_reason.lower() == "length":
                    expanded_config = self._expanded_config(effective_config)
                    if expanded_config is not None:
                        effective_config = expanded_config
                        continue
                    raise LLMServiceError("LLM returned an empty streamed answer after output-budget recovery")
                if completed:
                    raise LLMServiceError("LLM returned an empty streamed answer")
                raise LLMServiceError("LLM stream ended before completion")
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
