"""Parsing and provider-neutral helpers for the hand-written ReAct loop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from .prompts import RAGPrompt
from .schemas import ToolCall

try:
    from src.backend.rag.llm_client import GenerationConfig
except Exception:  # pragma: no cover - only for partial dependency environments.

    @dataclass(frozen=True)
    class GenerationConfig:  # type: ignore[no-redef]
        temperature: float = 0.2
        top_p: float = 0.9
        top_k: Optional[int] = None
        max_output_tokens: int = 512


class AgentModel(Protocol):
    def generate(self, prompt: RAGPrompt, config: GenerationConfig) -> Any:
        ...


@dataclass(frozen=True)
class ParsedAction:
    kind: str
    thought: str = ""
    calls: List[ToolCall] = field(default_factory=list)
    answer: str = ""
    citation_ids: List[int] = field(default_factory=list)


def _json_candidate(text: str) -> str:
    value = text.strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    if value.startswith("{") and value.endswith("}"):
        return value
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        return value[start : end + 1]
    return value


def parse_model_action(text: str) -> ParsedAction:
    """Parse only the two public JSON action forms; reject ambiguous output."""

    if not isinstance(text, str) or not text.strip():
        raise ValueError("model returned empty output")
    try:
        payload = json.loads(_json_candidate(text))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("model output is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("model output must be a JSON object")
    kind = payload.get("type")
    if kind == "final":
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("final action requires a non-empty answer")
        raw_ids = payload.get("citation_ids", [])
        if not isinstance(raw_ids, list):
            raise ValueError("citation_ids must be a list")
        citation_ids: List[int] = []
        for value in raw_ids:
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("citation_ids must contain positive integers")
            citation_ids.append(value)
        return ParsedAction(
            kind="final",
            thought=str(payload.get("thought", "")),
            answer=answer.strip(),
            citation_ids=citation_ids,
        )
    if kind != "tool_call":
        raise ValueError("action type must be tool_call or final")
    raw_calls = payload.get("calls")
    if raw_calls is None and isinstance(payload.get("tool"), str):
        raw_calls = [
            {
                "name": payload["tool"],
                "arguments": payload.get("arguments", {}),
            }
        ]
    if not isinstance(raw_calls, list) or not raw_calls:
        raise ValueError("tool_call requires a non-empty calls list")
    calls: List[ToolCall] = []
    for raw_call in raw_calls:
        if not isinstance(raw_call, Mapping):
            raise ValueError("each tool call must be an object")
        name = raw_call.get("name")
        arguments = raw_call.get("arguments", {})
        if not isinstance(name, str) or not name.strip():
            raise ValueError("tool call name must be a non-empty string")
        if not isinstance(arguments, Mapping):
            raise ValueError("tool call arguments must be an object")
        call_data: Dict[str, Any] = {
            "name": name.strip(),
            "arguments": dict(arguments),
        }
        if raw_call.get("call_id") is not None:
            call_data["call_id"] = str(raw_call["call_id"])
        calls.append(ToolCall(**call_data))
    return ParsedAction(
        kind="tool_call",
        thought=str(payload.get("thought", "")).strip(),
        calls=calls,
    )


def model_text_and_usage(output: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Normalize backend ``LLMResponse`` and simple fake-model outputs."""

    if isinstance(output, str):
        return output, None
    if isinstance(output, Mapping):
        text = output.get("text", output.get("content"))
        if not isinstance(text, str):
            raise ValueError("model response did not contain text")
        usage = output.get("token_usage", output.get("usage"))
        if usage is not None and not isinstance(usage, Mapping):
            usage = None
        return text, dict(usage) if usage is not None else None
    text = getattr(output, "text", None)
    if not isinstance(text, str):
        raise ValueError("model response did not contain text")
    usage = getattr(output, "token_usage", None)
    if usage is not None and not isinstance(usage, Mapping):
        usage = None
    return text, dict(usage) if usage is not None else None


__all__ = [
    "AgentModel",
    "GenerationConfig",
    "ParsedAction",
    "model_text_and_usage",
    "parse_model_action",
]
