"""Agent prompts built on the backend's provider-neutral ``RAGPrompt``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional

from .schemas import AgentTraceStep, to_jsonable

try:  # The fallback keeps offline Agent tests importable in a partial environment.
    from src.backend.rag.prompt import RAGPrompt
except Exception:  # pragma: no cover - exercised only when backend deps are absent.

    @dataclass(frozen=True)
    class RAGPrompt:  # type: ignore[no-redef]
        system: str
        user: str

        @property
        def messages(self) -> List[dict]:
            return [
                {"role": "system", "content": self.system},
                {"role": "user", "content": self.user},
            ]


def build_agent_prompt(
    message: str,
    memory_text: str,
    tool_descriptions: Iterable[Any],
    trace: Iterable[AgentTraceStep],
    repair_instruction: Optional[str] = None,
    request_metadata: Optional[Mapping[str, Any]] = None,
) -> RAGPrompt:
    """Build a JSON-only prompt for one ReAct model turn."""

    tools_json = json.dumps(to_jsonable(list(tool_descriptions)), ensure_ascii=False, indent=2)
    trace_json = json.dumps(to_jsonable(list(trace)), ensure_ascii=False, indent=2)
    allowed_metadata = {
        key: value
        for key, value in (request_metadata or {}).items()
        if key in {"paper_id", "paper_a", "paper_b", "top_k", "max_results"}
    }
    system_parts = [
        "You are the Co-Work research Agent. Use tools when evidence or computation is needed.",
        "Think privately, then return exactly one JSON object and no Markdown.",
        "Allowed output type tool_call:",
        '{"type":"tool_call","thought":"short reason","calls":[{"name":"tool_name","arguments":{}}]}',
        "Allowed output type final:",
        '{"type":"final","answer":"answer text","citation_ids":[1,2]}',
        "You may request multiple independent calls in one tool_call.",
        "Never invent paper names, page numbers, citation IDs, or tool results.",
        "Use citation_ids only from citations returned by knowledge_retrieval.",
        "Use knowledge_retrieval for questions about the knowledge base, including listing or discovering uploaded papers.",
        "Use paper_metadata, paper_summary, or paper_compare only with a paper ID supplied in request metadata or an exact unique uploaded filename stated verbatim by the user. Never derive, shorten, or guess a paper identifier.",
        "If a tool fails, inspect its error, avoid repeating the same action, and recover with a compatible alternative tool when possible.",
        "Do not claim BM25, RRF, reranking, or a paper field was used unless the tool observation contains it.",
        "Available tools:\n" + tools_json,
    ]
    if repair_instruction:
        system_parts.append("Repair instruction:\n" + repair_instruction)
    user = "\n\n".join(
        [
            "Conversation context:\n" + (memory_text or "(none)"),
            "Request metadata:\n"
            + (json.dumps(to_jsonable(allowed_metadata), ensure_ascii=False) if allowed_metadata else "{}"),
            "Previous Agent trace:\n" + (trace_json or "[]"),
            "Current user message:\n" + message.strip(),
        ]
    )
    return RAGPrompt(system="\n\n".join(system_parts), user=user)


__all__ = ["RAGPrompt", "build_agent_prompt"]
