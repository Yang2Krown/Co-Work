"""Small in-process Agent metrics used by the API and integration layer."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Dict, Mapping

from .schemas import AgentRunResult, ToolResult


class AgentMetrics:
    """Thread-safe counters; no metric is presented as a quality score."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runs = 0
        self._completed = 0
        self._failed = 0
        self._max_iterations = 0
        self._iterations = 0
        self._latency_ms = 0.0
        self._model_calls = 0
        self._token_usage: Dict[str, float] = defaultdict(float)
        self._rag_calls = 0
        self._rag_failures = 0
        self._rag_latency_ms = 0.0
        self._rag_chunks = 0
        self._tools: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "calls": 0.0,
                "successes": 0.0,
                "failures": 0.0,
                "latency_ms": 0.0,
                "token_usage": defaultdict(float),
            }
        )

    def record_tool(self, result: ToolResult) -> None:
        with self._lock:
            stats = self._tools[result.tool_name]
            stats["calls"] += 1
            stats["successes" if result.ok else "failures"] += 1
            stats["latency_ms"] += float(result.latency_ms)
            for key, value in (result.token_usage or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    stats["token_usage"][str(key)] += float(value)
            if result.tool_name == "knowledge_retrieval":
                self._rag_calls += 1
                if not result.ok:
                    self._rag_failures += 1
                data = result.data if isinstance(result.data, Mapping) else {}
                retrieval_latency = data.get("retrieval_latency_ms")
                if isinstance(retrieval_latency, (int, float)) and not isinstance(retrieval_latency, bool):
                    self._rag_latency_ms += max(0.0, float(retrieval_latency))
                else:
                    self._rag_latency_ms += max(0.0, float(result.latency_ms))
                retrieved_count = data.get("retrieved_count", 0)
                if isinstance(retrieved_count, int) and not isinstance(retrieved_count, bool):
                    self._rag_chunks += max(0, retrieved_count)

    def record_run(self, result: AgentRunResult, latency_ms: float) -> None:
        with self._lock:
            self._runs += 1
            if result.status == "completed":
                self._completed += 1
            elif result.status == "max_iterations":
                self._max_iterations += 1
            else:
                self._failed += 1
            self._iterations += result.iterations
            self._latency_ms += max(0.0, float(latency_ms))
            for key, value in (result.token_usage or {}).items():
                if key == "model_calls":
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        self._model_calls += max(0, int(value))
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self._token_usage[str(key)] += float(value)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            runs = self._runs
            tools: Dict[str, Dict[str, Any]] = {}
            for name, stats in sorted(self._tools.items()):
                calls = int(stats["calls"])
                tools[name] = {
                    "calls": calls,
                    "successes": int(stats["successes"]),
                    "failures": int(stats["failures"]),
                    "success_rate": (
                        stats["successes"] / calls if calls else None
                    ),
                    "total_latency_ms": stats["latency_ms"],
                    "avg_latency_ms": stats["latency_ms"] / calls if calls else 0.0,
                    "token_usage": dict(stats["token_usage"]),
                }
            return {
                "runs": runs,
                "completed_runs": self._completed,
                "failed_runs": self._failed,
                "max_iteration_runs": self._max_iterations,
                "total_iterations": self._iterations,
                "avg_iterations": self._iterations / runs if runs else 0.0,
                "total_latency_ms": self._latency_ms,
                "avg_latency_ms": self._latency_ms / runs if runs else 0.0,
                "model_calls": self._model_calls,
                "token_usage": dict(self._token_usage),
                "rag": {
                    "calls": self._rag_calls,
                    "failures": self._rag_failures,
                    "total_latency_ms": self._rag_latency_ms,
                    "avg_latency_ms": self._rag_latency_ms / self._rag_calls if self._rag_calls else 0.0,
                    "retrieved_chunks": self._rag_chunks,
                },
                "tools": tools,
            }


__all__ = ["AgentMetrics"]
