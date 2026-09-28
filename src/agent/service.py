"""Hand-written JSON ReAct orchestration for the Co-Work Agent."""

from __future__ import annotations

import json
from contextvars import ContextVar
from collections import Counter
from time import perf_counter
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple
from uuid import uuid4

from .config import AgentConfig, load_agent_config
from .memory import InMemorySessionStore, SessionStore
from .observability import AgentMetrics
from .prompts import build_agent_prompt
from .react_loop import (
    AgentModel,
    GenerationConfig,
    ParsedAction,
    model_text_and_usage,
    parse_model_action,
)
from .router import IntentRouter, RouteDecision
from .schemas import (
    AgentEvent,
    AgentRequest,
    AgentRunResult,
    AgentTraceStep,
    CitationRef,
    ToolCall,
    ToolResult,
    to_jsonable,
)
from .tools import ToolRegistry, build_default_tool_registry


_EVENT_SEQUENCE: ContextVar[int] = ContextVar("agent_event_sequence", default=0)


def _safe_error(exc: BaseException) -> str:
    return (type(exc).__name__ + ": " + (str(exc).strip() or "no detail"))[:500]


def _merge_token_usage(
    accumulated: Optional[Dict[str, Any]],
    current: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Accumulate numeric provider usage without inventing missing values."""

    if not current:
        return accumulated
    merged = dict(accumulated or {})
    for key, value in current.items():
        if key == "model_calls":
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            previous = merged.get(key, 0)
            if isinstance(previous, (int, float)) and not isinstance(previous, bool):
                merged[key] = previous + value
            else:
                merged[key] = value
        elif key not in merged:
            merged[key] = value
    current_calls = current.get("model_calls", 1)
    if not isinstance(current_calls, (int, float)) or isinstance(current_calls, bool):
        current_calls = 1
    previous_calls = merged.get("model_calls", 0)
    merged["model_calls"] = (
        int(previous_calls) if isinstance(previous_calls, (int, float)) else 0
    ) + max(1, int(current_calls))
    return merged


class _ActionGenerationError(ValueError):
    """Model/parser failure that retains usage from repair attempts."""

    def __init__(self, message: str, token_usage: Optional[Dict[str, Any]]) -> None:
        super().__init__(message)
        self.token_usage = token_usage


class AgentService:
    """Coordinate routing, tools, memory, and a provider-neutral model."""

    def __init__(
        self,
        llm_client: Optional[AgentModel] = None,
        registry: Optional[ToolRegistry] = None,
        memory_store: Optional[SessionStore] = None,
        config: Optional[AgentConfig] = None,
        router: Optional[IntentRouter] = None,
        generation_config: Optional[GenerationConfig] = None,
        summary_callback: Optional[Any] = None,
        health_check: Optional[Callable[[], Mapping[str, Any]]] = None,
        metrics: Optional[AgentMetrics] = None,
    ) -> None:
        self.llm_client = llm_client
        self.config = config or load_agent_config()
        self.registry = registry or build_default_tool_registry(max_workers=self.config.max_workers)
        self.memory_store = memory_store or InMemorySessionStore()
        self.router = router or IntentRouter()
        self.generation_config = generation_config or GenerationConfig()
        self.summary_callback = summary_callback
        self.health_check = health_check
        self.metrics = metrics or AgentMetrics()

    def health(self) -> Dict[str, Any]:
        """Return local readiness information without probing external services."""

        result: Dict[str, Any] = {
            "status": "ok",
            "service": "agent",
            "tools": self.registry.names(),
            "dependencies": {
                "llm": "not_checked",
                "vector_store": "not_checked",
            },
            "metrics": self.metrics.snapshot(),
        }
        if self.health_check is None:
            return result
        try:
            dependencies = self.health_check()
            if isinstance(dependencies, Mapping):
                result["dependencies"].update(
                    {str(key): to_jsonable(value) for key, value in dependencies.items()}
                )
                unhealthy = False
                for value in dependencies.values():
                    if isinstance(value, bool) and not value:
                        unhealthy = True
                    elif isinstance(value, str) and value.lower() in {
                        "degraded",
                        "failed",
                        "error",
                        "unavailable",
                        "not_configured",
                    }:
                        unhealthy = True
                    elif isinstance(value, Mapping):
                        status = str(value.get("status", "")).lower()
                        if status in {"degraded", "failed", "error", "unavailable", "not_configured"}:
                            unhealthy = True
                if unhealthy:
                    result["status"] = "degraded"
            else:
                result["status"] = "degraded"
                result["dependencies"]["health_check"] = "invalid result"
        except Exception as exc:  # noqa: BLE001 - health must remain observable.
            result["status"] = "degraded"
            result["dependencies"]["health_check"] = _safe_error(exc)
        result["metrics"] = self.metrics.snapshot()
        return result

    @staticmethod
    def _request(value: Any) -> AgentRequest:
        if isinstance(value, AgentRequest):
            return value
        if isinstance(value, Mapping):
            return AgentRequest.model_validate(value)
        raise TypeError("request must be an AgentRequest or mapping")

    def _event(
        self,
        event: str,
        run_id: str,
        session_id: str,
        step_index: Optional[int] = None,
        tool_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AgentEvent:
        sequence = _EVENT_SEQUENCE.get() + 1
        _EVENT_SEQUENCE.set(sequence)
        return AgentEvent(
            event=event,
            run_id=run_id,
            session_id=session_id,
            step_index=step_index,
            tool_name=tool_name,
            sequence=sequence,
            payload=to_jsonable(payload or {}),
        )

    @staticmethod
    def _citation_key(citation: CitationRef) -> Tuple[str, Optional[int], Optional[str]]:
        return citation.file_name, citation.page_number, citation.chunk_id

    def _merge_citations(
        self,
        result: ToolResult,
        collected: List[CitationRef],
    ) -> ToolResult:
        """Copy backend citation identity and assign only local display IDs."""

        existing = {self._citation_key(item): item for item in collected}
        rebased: List[CitationRef] = []
        for citation in result.citations:
            key = self._citation_key(citation)
            current = existing.get(key)
            if current is None:
                current = CitationRef(
                    citation_id=len(collected) + 1,
                    file_name=citation.file_name,
                    page_number=citation.page_number,
                    chunk_id=citation.chunk_id,
                )
                collected.append(current)
                existing[key] = current
            rebased.append(current)
        return result.model_copy(update={"citations": rebased})

    @staticmethod
    def _action_key(call: ToolCall) -> str:
        return call.name + ":" + json.dumps(
            to_jsonable(call.arguments), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @staticmethod
    def _direct_answer(tool_result: ToolResult) -> str:
        if not tool_result.ok:
            return "工具执行失败：" + (tool_result.error or "未知错误")
        data = tool_result.data
        if isinstance(data, Mapping):
            if tool_result.tool_name == "knowledge_retrieval" and isinstance(
                data.get("answer"), str
            ):
                return data["answer"]
            if tool_result.tool_name == "calculator" and "result" in data:
                return "计算结果：" + str(data["result"])
            if tool_result.tool_name == "current_time" and "current_time" in data:
                return "当前时间：" + str(data["current_time"])
            if tool_result.tool_name == "keyword_extract":
                keywords = data.get("keywords", [])
                return "关键词：" + ", ".join(
                    str(item.get("keyword", "")) for item in keywords if isinstance(item, Mapping)
                )
        return json.dumps(to_jsonable(data), ensure_ascii=False)

    @staticmethod
    def _tool_token_usage(result: ToolResult) -> Optional[Dict[str, Any]]:
        if result.token_usage:
            return dict(result.token_usage)
        if isinstance(result.data, Mapping):
            usage = result.data.get("token_usage")
            if isinstance(usage, Mapping):
                return dict(usage)
        return None

    def _final_result(
        self,
        run_id: str,
        request: AgentRequest,
        answer: str,
        citations: List[CitationRef],
        trace: List[AgentTraceStep],
        iterations: int,
        status: str = "completed",
        token_usage: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> AgentRunResult:
        return AgentRunResult(
            run_id=run_id,
            session_id=request.session_id,
            answer=answer,
            citations=list(citations),
            trace=list(trace),
            iterations=iterations,
            status=status,  # type: ignore[arg-type]
            token_usage=token_usage,
            error=error,
        )

    def _run_direct(
        self,
        run_id: str,
        request: AgentRequest,
        route: RouteDecision,
        trace: List[AgentTraceStep],
        citations: List[CitationRef],
        state: Dict[str, Any],
    ) -> Iterator[AgentEvent]:
        assert route.tool_name is not None
        call = ToolCall(name=route.tool_name, arguments=route.arguments)
        step_started = perf_counter()
        yield self._event(
            "thought",
            run_id,
            request.session_id,
            step_index=0,
            payload={"thought": "deterministic route: " + route.reason, "mode": "direct"},
        )
        yield self._event(
            "tool_started",
            run_id,
            request.session_id,
            step_index=0,
            tool_name=call.name,
            payload={"call_id": call.call_id, "arguments": call.arguments},
        )
        spec = self.registry.get(call.name)
        if spec is not None and spec.may_call_llm:
            yield self._event(
                "llm_started",
                run_id,
                request.session_id,
                step_index=0,
                tool_name=call.name,
                payload={"phase": "tool_internal", "call_id": call.call_id},
            )
        result = self.registry.execute(
            call,
            timeout_seconds=self.config.tool_timeout_seconds,
            retries=self.config.tool_retry_count,
        )
        result = self._merge_citations(result, citations)
        self.metrics.record_tool(result)
        tool_usage = self._tool_token_usage(result)
        normalized_tool_usage = _merge_token_usage(None, tool_usage)
        run_token_usage = _merge_token_usage(state.get("token_usage"), tool_usage)
        if spec is not None and spec.may_call_llm:
            yield self._event(
                "llm_finished",
                run_id,
                request.session_id,
                step_index=0,
                tool_name=call.name,
                payload={"phase": "tool_internal", "call_id": call.call_id, "ok": result.ok, "token_usage": tool_usage},
            )
        yield self._event(
            "tool_finished",
            run_id,
            request.session_id,
            step_index=0,
            tool_name=call.name,
            payload={"result": result.model_dump(mode="json")},
        )
        trace.append(
            AgentTraceStep(
                step_index=0,
                thought="deterministic route: " + route.reason,
                calls=[call],
                observations=[result],
                latency_ms=(perf_counter() - step_started) * 1000,
                status="completed" if result.ok else "failed",
                token_usage=normalized_tool_usage,
            )
        )
        answer = self._direct_answer(result)
        state["result"] = self._final_result(
            run_id,
            request,
            answer,
            citations,
            trace,
            iterations=1,
            status="completed" if result.ok else "failed",
            token_usage=run_token_usage,
            error=result.error if not result.ok else None,
        )
        yield self._event(
            "final",
            run_id,
            request.session_id,
            step_index=0,
            payload={"answer": answer, "citations": [item.model_dump(mode="json") for item in citations]},
        )

    def _generate_action(
        self,
        request: AgentRequest,
        memory_text: str,
        trace: List[AgentTraceStep],
    ) -> Tuple[ParsedAction, Optional[Dict[str, Any]]]:
        if self.llm_client is None:
            raise RuntimeError("LLM client is not configured for ReAct routing")
        repair_instruction: Optional[str] = None
        last_error: Optional[BaseException] = None
        token_usage: Optional[Dict[str, Any]] = None
        for attempt in range(self.config.repair_attempts + 1):
            prompt = build_agent_prompt(
                request.message,
                memory_text,
                self.registry.describe(),
                trace,
                request_metadata=request.metadata,
                repair_instruction=repair_instruction,
            )
            try:
                output = self.llm_client.generate(prompt, self.generation_config)
                text, usage = model_text_and_usage(output)
                token_usage = _merge_token_usage(token_usage, usage)
                return parse_model_action(text), token_usage
            except Exception as exc:  # noqa: BLE001 - model and parser failures are structured.
                last_error = exc
                if attempt >= self.config.repair_attempts:
                    break
                repair_instruction = (
                    "The previous output was invalid. Return one valid JSON object only. "
                    "Parser error: " + _safe_error(exc)
                )
        raise _ActionGenerationError(
            "could not parse model action: " + _safe_error(last_error or ValueError("unknown")),
            token_usage,
        )

    def _run_react(
        self,
        run_id: str,
        request: AgentRequest,
        memory: Any,
        trace: List[AgentTraceStep],
        citations: List[CitationRef],
        state: Dict[str, Any],
    ) -> Iterator[AgentEvent]:
        repeated = Counter()
        token_usage: Optional[Dict[str, Any]] = state.get("token_usage")
        for iteration in range(self.config.max_iterations):
            step_started = perf_counter()
            llm_started = perf_counter()
            yield self._event(
                "llm_started",
                run_id,
                request.session_id,
                step_index=iteration,
                payload={"phase": "react_planning", "model": getattr(self.llm_client, "model_name", None)},
            )
            try:
                action, usage = self._generate_action(request, memory.prompt_text(), trace)
                token_usage = _merge_token_usage(token_usage, usage)
            except Exception as exc:  # noqa: BLE001 - provider/parser failures become a result.
                error = _safe_error(exc)
                token_usage = _merge_token_usage(
                    token_usage,
                    getattr(exc, "token_usage", None),
                )
                yield self._event(
                    "llm_finished",
                    run_id,
                    request.session_id,
                    step_index=iteration,
                    payload={"phase": "react_planning", "ok": False, "latency_ms": (perf_counter() - llm_started) * 1000},
                )
                yield self._event(
                    "error",
                    run_id,
                    request.session_id,
                    step_index=iteration,
                    payload={"error": error, "kind": "model"},
                )
                state["result"] = self._final_result(
                    run_id,
                    request,
                    "模型暂时无法生成有效的 Agent 动作，请稍后重试。",
                    citations,
                    trace,
                    iteration + 1,
                    status="failed",
                    token_usage=token_usage,
                    error=error,
                )
                return

            yield self._event(
                "llm_finished",
                run_id,
                request.session_id,
                step_index=iteration,
                payload={
                    "phase": "react_planning",
                    "ok": True,
                    "latency_ms": (perf_counter() - llm_started) * 1000,
                    "token_usage": usage,
                },
            )

            step_token_usage = usage

            if action.thought:
                yield self._event(
                    "thought",
                    run_id,
                    request.session_id,
                    step_index=iteration,
                    payload={"thought": action.thought},
                )
            if action.kind == "final":
                available = {citation.citation_id: citation for citation in citations}
                requested = action.citation_ids or list(available)
                selected = [available[index] for index in requested if index in available]
                trace.append(
                    AgentTraceStep(
                        step_index=iteration,
                        thought=action.thought,
                        latency_ms=(perf_counter() - step_started) * 1000,
                        status="completed",
                        token_usage=usage,
                    )
                )
                state["result"] = self._final_result(
                    run_id,
                    request,
                    action.answer,
                    selected,
                    trace,
                    iteration + 1,
                    status="completed",
                    token_usage=token_usage,
                )
                yield self._event(
                    "final",
                    run_id,
                    request.session_id,
                    step_index=iteration,
                    payload={
                        "answer": action.answer,
                        "citations": [item.model_dump(mode="json") for item in selected],
                    },
                )
                return

            calls = list(action.calls)
            extra_calls = calls[self.config.max_tool_calls_per_step :]
            calls = calls[: self.config.max_tool_calls_per_step]
            observations: List[ToolResult] = []
            repeated_hit = False
            for call in calls:
                key = self._action_key(call)
                repeated[key] += 1
                if repeated[key] > self.config.max_repeated_actions:
                    repeated_hit = True
                    observations.append(
                        ToolResult(
                            tool_name=call.name,
                            call_id=call.call_id,
                            ok=False,
                            error="repeated action limit reached",
                        )
                    )
            if repeated_hit:
                trace.append(
                    AgentTraceStep(
                        step_index=iteration,
                        thought=action.thought,
                        calls=calls,
                        observations=observations,
                        latency_ms=(perf_counter() - step_started) * 1000,
                        status="repeated",
                        token_usage=usage,
                    )
                )
                state["result"] = self._final_result(
                    run_id,
                    request,
                    "检测到重复工具动作，已停止本次推理以避免死循环。",
                    citations,
                    trace,
                    iteration + 1,
                    status="failed",
                    token_usage=token_usage,
                    error="repeated action limit reached",
                )
                yield self._event(
                    "error",
                    run_id,
                    request.session_id,
                    step_index=iteration,
                    payload={"error": "repeated action limit reached", "kind": "loop_guard"},
                )
                return

            if extra_calls:
                observations.extend(
                    ToolResult(
                        tool_name=call.name,
                        call_id=call.call_id,
                        ok=False,
                        error="tool call limit exceeded for one step",
                    )
                    for call in extra_calls
                )
            for call in calls:
                yield self._event(
                    "tool_started",
                    run_id,
                    request.session_id,
                    step_index=iteration,
                    tool_name=call.name,
                    payload={"call_id": call.call_id, "arguments": call.arguments},
                )
                spec = self.registry.get(call.name)
                if spec is not None and spec.may_call_llm:
                    yield self._event(
                        "llm_started",
                        run_id,
                        request.session_id,
                        step_index=iteration,
                        tool_name=call.name,
                        payload={"phase": "tool_internal", "call_id": call.call_id},
                    )
            executed = self.registry.execute_many_stream(
                calls,
                timeout_seconds=self.config.tool_timeout_seconds,
                retries=self.config.tool_retry_count,
                max_workers=self.config.max_workers,
            )
            completed_by_call_id: Dict[str, ToolResult] = {}
            for result in executed:
                merged = self._merge_citations(result, citations)
                if merged.call_id:
                    completed_by_call_id[merged.call_id] = merged
                else:
                    observations.append(merged)
                self.metrics.record_tool(merged)
                tool_usage = self._tool_token_usage(merged)
                token_usage = _merge_token_usage(token_usage, tool_usage)
                step_token_usage = _merge_token_usage(step_token_usage, tool_usage)
                spec = self.registry.get(merged.tool_name)
                if spec is not None and spec.may_call_llm:
                    yield self._event(
                        "llm_finished",
                        run_id,
                        request.session_id,
                        step_index=iteration,
                        tool_name=merged.tool_name,
                        payload={"phase": "tool_internal", "call_id": merged.call_id, "ok": merged.ok, "token_usage": tool_usage},
                    )
                yield self._event(
                    "tool_finished",
                    run_id,
                    request.session_id,
                    step_index=iteration,
                    tool_name=merged.tool_name,
                    payload={"result": merged.model_dump(mode="json")},
                )
            # Completion events are emitted as soon as each worker returns, but
            # persisted trace observations deliberately retain model call order.
            observations = [
                completed_by_call_id[call.call_id]
                for call in calls
                if call.call_id in completed_by_call_id
            ] + observations
            status = "completed"
            if any(item.error and "timed out" in item.error for item in observations):
                status = "timeout"
            elif any(not item.ok for item in observations):
                status = "failed"
            trace.append(
                AgentTraceStep(
                    step_index=iteration,
                    thought=action.thought,
                    calls=calls + extra_calls,
                    observations=observations,
                    latency_ms=(perf_counter() - step_started) * 1000,
                    status=status,  # type: ignore[arg-type]
                    token_usage=step_token_usage,
                )
            )
        error = "maximum ReAct iterations reached"
        state["result"] = self._final_result(
            run_id,
            request,
            "已达到最大推理步数，暂未完成该请求。请缩小问题范围后重试。",
            citations,
            trace,
            self.config.max_iterations,
            status="max_iterations",
            token_usage=token_usage,
            error=error,
        )
        yield self._event(
            "error",
            run_id,
            request.session_id,
            step_index=self.config.max_iterations,
            payload={"error": error, "kind": "max_iterations"},
        )

    def stream(self, request: AgentRequest) -> Iterator[AgentEvent]:
        """Yield transport-neutral Agent events in execution order."""

        request = self._request(request)
        _EVENT_SEQUENCE.set(0)
        run_started_at = perf_counter()
        run_id = str(uuid4())
        trace: List[AgentTraceStep] = []
        citations: List[CitationRef] = []
        state: Dict[str, Any] = {"result": None, "token_usage": None}
        with self.memory_store.locked(request.session_id) as memory:
            memory.add("user", request.message)
            if self.summary_callback is not None and hasattr(
                self.summary_callback, "last_token_usage"
            ):
                setattr(self.summary_callback, "last_token_usage", None)
            memory.compact(
                max_tokens=self.config.max_memory_tokens,
                trigger_messages=self.config.summary_trigger_messages,
                keep_messages=self.config.summary_keep_messages,
                summarizer=self.summary_callback,
            )
            state["token_usage"] = _merge_token_usage(
                None,
                getattr(self.summary_callback, "last_token_usage", None),
            )
            yield self._event(
                "run_started",
                run_id,
                request.session_id,
                payload={"tools": self.registry.names()},
            )
            try:
                route = self.router.decide(request)
                yield self._event(
                    "route_selected",
                    run_id,
                    request.session_id,
                    payload={
                        "mode": route.mode,
                        "reason": route.reason,
                        "uses_llm": route.mode != "direct",
                        "tool_name": route.tool_name,
                    },
                )
                if route.mode == "direct":
                    yield from self._run_direct(
                        run_id, request, route, trace, citations, state
                    )
                else:
                    yield from self._run_react(
                        run_id, request, memory, trace, citations, state
                    )
            except Exception as exc:  # noqa: BLE001 - final safety boundary.
                error = _safe_error(exc)
                yield self._event(
                    "error",
                    run_id,
                    request.session_id,
                    payload={"error": error, "kind": "agent"},
                )
                state["result"] = self._final_result(
                    run_id,
                    request,
                    "Agent 执行失败，请稍后重试。",
                    citations,
                    trace,
                    len(trace),
                    status="failed",
                    token_usage=state.get("token_usage"),
                    error=error,
                )
            result = state.get("result")
            if not isinstance(result, AgentRunResult):
                result = self._final_result(
                    run_id,
                    request,
                    "Agent 未产生有效结果。",
                    citations,
                    trace,
                    len(trace),
                    status="failed",
                    token_usage=state.get("token_usage"),
                    error="missing Agent result",
                )
            memory.add("assistant", result.answer)
            self.metrics.record_run(
                result,
                latency_ms=(perf_counter() - run_started_at) * 1000,
            )
            yield self._event(
                "run_finished",
                run_id,
                request.session_id,
                payload={"result": result.model_dump(mode="json")},
            )

    def run(self, request: AgentRequest) -> AgentRunResult:
        """Run an Agent turn and return the final structured result."""

        final: Optional[AgentRunResult] = None
        for event in self.stream(request):
            if event.event == "run_finished":
                raw = event.payload.get("result")
                if isinstance(raw, Mapping):
                    final = AgentRunResult.model_validate(raw)
        if final is None:
            raise RuntimeError("Agent stream ended without run_finished")
        return final


__all__ = ["AgentService"]
