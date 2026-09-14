"""Thread-safe in-memory conversation sessions with bounded context."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from math import ceil
from typing import Callable, Dict, Iterator, List, Optional, Protocol, Tuple


def estimate_tokens(text: str) -> int:
    """Return a deliberately conservative, model-independent token estimate."""

    if not text:
        return 0
    return max(1, int(ceil(len(text) / 4.0)))


@dataclass(frozen=True)
class MemoryMessage:
    role: str
    content: str
    name: Optional[str] = None

    def as_dict(self) -> Dict[str, str]:
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result


class ConversationMemory:
    """One session's ordered messages and optional compression summary."""

    def __init__(self, session_id: str) -> None:
        if not session_id.strip():
            raise ValueError("session_id must not be blank")
        self.session_id = session_id
        self._messages: List[MemoryMessage] = []
        self._summary: Optional[str] = None
        self._lock = threading.RLock()

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def summary(self) -> Optional[str]:
        with self._lock:
            return self._summary

    def add(self, role: str, content: str, name: Optional[str] = None) -> None:
        if not role.strip():
            raise ValueError("role must not be blank")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must not be blank")
        with self._lock:
            self._messages.append(MemoryMessage(role.strip(), content.strip(), name))

    def snapshot(self) -> List[MemoryMessage]:
        with self._lock:
            return list(self._messages)

    def token_count(self) -> int:
        with self._lock:
            summary_tokens = estimate_tokens(self._summary or "")
            return summary_tokens + sum(estimate_tokens(item.content) for item in self._messages)

    def compact(
        self,
        max_tokens: int,
        trigger_messages: int,
        keep_messages: int,
        summarizer: Optional[Callable[[str], str]] = None,
    ) -> bool:
        """Compress older messages when count or estimated tokens exceed limits."""

        if max_tokens <= 0 or trigger_messages <= 0 or keep_messages <= 0:
            raise ValueError("memory compaction limits must be greater than zero")
        with self._lock:
            if not self._messages:
                return False
            if len(self._messages) < trigger_messages and self.token_count() <= max_tokens:
                return False
            split_at = max(0, len(self._messages) - keep_messages)
            if split_at == 0 and self.token_count() > max_tokens and len(self._messages) > 1:
                # Even a short conversation can contain one very large turn;
                # keep its newest message and summarize the older part.
                split_at = len(self._messages) - 1
            older = self._messages[:split_at]
            if not older:
                if self.token_count() <= max_tokens:
                    return False
                self._messages = self._bounded_messages(max_tokens)
                return True
            transcript = "\n".join(
                "{}: {}".format(item.role, item.content) for item in older
            )
            if summarizer is not None:
                try:
                    compressed = summarizer(transcript).strip()
                except Exception:  # noqa: BLE001 - summary failure must not lose the turn.
                    compressed = ""
            else:
                compressed = ""
            if not compressed:
                compressed = transcript[:4000]
            self._summary = (
                (self._summary + "\n" if self._summary else "") + compressed
            ).strip()
            self._messages = self._messages[split_at:]
            self._messages = self._bounded_messages(max_tokens)
            # Keep the summary bounded as well.  This is an estimate, not a
            # provider tokenizer, but prevents repeated turns from growing
            # without limit when no summarizer is injected.
            recent_tokens = sum(estimate_tokens(item.content) for item in self._messages)
            summary_budget = max(0, (max_tokens - recent_tokens) * 4)
            if summary_budget == 0:
                self._summary = None
            elif len(self._summary) > summary_budget:
                self._summary = self._summary[-summary_budget:]
            return True

    def _bounded_messages(self, max_tokens: int) -> List[MemoryMessage]:
        """Keep the newest content within the rough token budget."""

        budget_chars = max(1, max_tokens * 4)
        retained: List[MemoryMessage] = []
        for item in reversed(self._messages):
            if budget_chars <= 0:
                break
            content = item.content
            if len(content) > budget_chars:
                content = content[-budget_chars:]
            retained.insert(0, MemoryMessage(item.role, content, item.name))
            budget_chars -= len(content)
        return retained

    def prompt_text(self) -> str:
        with self._lock:
            parts: List[str] = []
            if self._summary:
                parts.append("Conversation summary:\n" + self._summary)
            if self._messages:
                parts.append(
                    "Recent messages:\n"
                    + "\n".join(
                        "{}: {}".format(item.role, item.content)
                        for item in self._messages
                    )
                )
            return "\n\n".join(parts) or "(No previous conversation.)"


class SessionStore(Protocol):
    def get(self, session_id: str) -> ConversationMemory:
        ...

    def clear(self, session_id: str) -> None:
        ...

    def locked(self, session_id: str) -> Iterator[ConversationMemory]:
        ...


class InMemorySessionStore:
    """A process-local store with a distinct lock for each session."""

    def __init__(self) -> None:
        self._sessions: Dict[str, ConversationMemory] = {}
        self._lock = threading.RLock()

    def get(self, session_id: str) -> ConversationMemory:
        if not session_id.strip():
            raise ValueError("session_id must not be blank")
        with self._lock:
            memory = self._sessions.get(session_id)
            if memory is None:
                memory = ConversationMemory(session_id)
                self._sessions[session_id] = memory
            return memory

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    @contextmanager
    def locked(self, session_id: str) -> Iterator[ConversationMemory]:
        memory = self.get(session_id)
        with memory.lock:
            yield memory

    def session_ids(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(self._sessions.keys())


__all__ = [
    "ConversationMemory",
    "InMemorySessionStore",
    "MemoryMessage",
    "SessionStore",
    "estimate_tokens",
]
