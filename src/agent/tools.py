"""Agent tool contracts and the eight offline-safe default tools."""

from __future__ import annotations

import ast
import math
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from .schemas import CitationRef, ToolCall, ToolResult, to_jsonable


ToolHandler = Callable[[Dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolSpec:
    """Metadata and executable boundary for one registered tool."""

    name: str
    description: str
    handler: ToolHandler
    input_schema: Mapping[str, Any]
    parallel_safe: bool = True
    retryable: bool = True


def _error_text(exc: BaseException) -> str:
    detail = str(exc).strip() or "no detail"
    return (type(exc).__name__ + ": " + detail)[:500]


def _failure(
    tool_name: str,
    error: str,
    data: Any = None,
    token_usage: Optional[Mapping[str, Any]] = None,
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        ok=False,
        data=data,
        error=error,
        token_usage=dict(token_usage) if token_usage is not None else None,
    )


def _success(
    tool_name: str,
    data: Any,
    citations: Optional[List[CitationRef]] = None,
    token_usage: Optional[Mapping[str, Any]] = None,
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        ok=True,
        data=to_jsonable(data),
        citations=citations or [],
        token_usage=dict(token_usage) if token_usage is not None else None,
    )


class ToolRegistry:
    """Thread-safe registry with bounded execution and structured recovery."""

    def __init__(self, max_workers: int = 4) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than zero")
        self.max_workers = max_workers
        self._specs: Dict[str, ToolSpec] = {}
        self._lock = threading.RLock()

    def register(self, spec: ToolSpec) -> None:
        if not spec.name.strip():
            raise ValueError("tool name must not be blank")
        if not callable(spec.handler):
            raise TypeError("tool handler must be callable")
        with self._lock:
            if spec.name in self._specs:
                raise ValueError("tool already registered: " + spec.name)
            self._specs[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        with self._lock:
            return self._specs.get(name)

    def names(self) -> List[str]:
        with self._lock:
            return sorted(self._specs)

    def describe(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "input_schema": to_jsonable(spec.input_schema),
                    "parallel_safe": spec.parallel_safe,
                }
                for spec in sorted(self._specs.values(), key=lambda item: item.name)
            ]

    @staticmethod
    def _coerce_result(
        call: ToolCall,
        result: Any,
        elapsed_ms: float,
    ) -> ToolResult:
        if isinstance(result, ToolResult):
            return result.model_copy(
                update={
                    "tool_name": result.tool_name or call.name,
                    "call_id": call.call_id,
                    "latency_ms": max(0.0, elapsed_ms),
                }
            )
        return ToolResult(
            tool_name=call.name,
            call_id=call.call_id,
            ok=True,
            data=to_jsonable(result),
            latency_ms=max(0.0, elapsed_ms),
        )

    def execute(
        self,
        call: ToolCall,
        timeout_seconds: float = 15.0,
        retries: int = 0,
    ) -> ToolResult:
        """Execute one call without allowing handler failures to escape."""

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if retries < 0:
            raise ValueError("retries must not be negative")
        spec = self.get(call.name)
        if spec is None:
            return ToolResult(
                tool_name=call.name,
                call_id=call.call_id,
                ok=False,
                error="unknown tool: " + call.name,
            )
        attempts = retries + 1 if spec.retryable else 1
        last_error = "tool failed"
        started = perf_counter()
        for attempt in range(attempts):
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(spec.handler, dict(call.arguments))
            try:
                raw = future.result(timeout=timeout_seconds)
                elapsed_ms = (perf_counter() - started) * 1000
                return self._coerce_result(call, raw, elapsed_ms)
            except FutureTimeoutError:
                future.cancel()
                last_error = "tool timed out after {:.3f}s".format(timeout_seconds)
                if attempt + 1 == attempts:
                    return ToolResult(
                        tool_name=call.name,
                        call_id=call.call_id,
                        ok=False,
                        error=last_error,
                        latency_ms=(perf_counter() - started) * 1000,
                    )
            except Exception as exc:  # noqa: BLE001 - tool failures are observations.
                last_error = _error_text(exc)
                if attempt + 1 == attempts:
                    return ToolResult(
                        tool_name=call.name,
                        call_id=call.call_id,
                        ok=False,
                        error=last_error,
                        latency_ms=(perf_counter() - started) * 1000,
                    )
            finally:
                # Do not wait for a timed-out handler.  It is already isolated
                # from the request result and cannot mutate Agent state.
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except TypeError:  # pragma: no cover - Python 3.8 fallback.
                    executor.shutdown(wait=False)
        return ToolResult(
            tool_name=call.name,
            call_id=call.call_id,
            ok=False,
            error=last_error,
            latency_ms=(perf_counter() - started) * 1000,
        )

    def execute_many(
        self,
        calls: Sequence[ToolCall],
        timeout_seconds: float = 15.0,
        retries: int = 0,
        max_workers: Optional[int] = None,
    ) -> List[ToolResult]:
        """Execute independent calls concurrently while preserving call order."""

        if len(calls) <= 1:
            return [self.execute(calls[0], timeout_seconds, retries)] if calls else []
        specs = [self.get(call.name) for call in calls]
        can_parallel = all(spec is not None and spec.parallel_safe for spec in specs)
        if not can_parallel:
            return [self.execute(call, timeout_seconds, retries) for call in calls]
        worker_count = max_workers or self.max_workers
        worker_count = max(1, min(worker_count, len(calls)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(self.execute, call, timeout_seconds, retries)
                for call in calls
            ]
            return [future.result() for future in futures]


class PaperRecord(BaseModel):
    """A minimal paper record used by deterministic paper tools."""

    model_config = ConfigDict(extra="allow")

    paper_id: str = Field(min_length=1)
    file_name: str = ""
    title: str = ""
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    abstract: str = ""
    doi: Optional[str] = None
    method: str = ""
    datasets: List[str] = Field(default_factory=list)
    results: str = ""
    text: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InMemoryPaperCatalog:
    """Optional paper source for offline demos and later database adapters."""

    def __init__(self, papers: Optional[Iterable[PaperRecord]] = None) -> None:
        self._papers: Dict[str, PaperRecord] = {}
        for paper in papers or []:
            self.add(paper)

    def add(self, paper: PaperRecord) -> None:
        self._papers[paper.paper_id] = paper

    def get(self, paper_id: str) -> Optional[PaperRecord]:
        return self._papers.get(paper_id)

    def ids(self) -> List[str]:
        return sorted(self._papers)


def _lookup_paper(catalog: Any, paper_id: str) -> Optional[PaperRecord]:
    if catalog is None:
        return None
    raw = catalog.get(paper_id) if hasattr(catalog, "get") else None
    if raw is None:
        return None
    if isinstance(raw, PaperRecord):
        return raw
    if isinstance(raw, Mapping):
        values = dict(raw)
        values["paper_id"] = paper_id
        return PaperRecord(**values)
    values = {
        key: getattr(raw, key)
        for key in PaperRecord.model_fields
        if hasattr(raw, key)
    }
    values.setdefault("paper_id", paper_id)
    return PaperRecord(**values)


def _paper_public(paper: PaperRecord) -> Dict[str, Any]:
    data = paper.model_dump(mode="json")
    data.pop("text", None)
    metadata = data.get("metadata")
    if isinstance(metadata, Mapping):
        metadata = dict(metadata)
        metadata.pop("pages", None)
        data["metadata"] = metadata
    return data


def _extractive_paper_summary(
    paper: Optional[PaperRecord],
    text: str,
    fallback_reason: Optional[str] = None,
) -> Dict[str, Any]:
    source_text = text
    if not source_text.strip() and paper is not None:
        source_text = "\n".join(
            part for part in (paper.abstract, paper.method, paper.results) if part
        )
    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n", source_text)
        if part.strip()
    ]
    title = paper.title if paper is not None else ""
    method = paper.method if paper is not None else ""
    results = paper.results if paper is not None else ""
    if not method and len(paragraphs) > 1:
        method = paragraphs[1][:1000]
    if not results and len(paragraphs) > 2:
        results = paragraphs[2][:1000]
    summary: Dict[str, Any] = {
        "title": title,
        "background": paragraphs[0][:1000] if paragraphs else "",
        "method": method,
        "results": results,
        "conclusion": paragraphs[-1][:1000] if paragraphs else "",
        "source": "extractive_fallback",
    }
    if fallback_reason:
        summary["fallback_reason"] = fallback_reason
    return summary


def _citation_refs(raw_citations: Any) -> List[CitationRef]:
    refs: List[CitationRef] = []
    for item in raw_citations or []:
        if isinstance(item, CitationRef):
            refs.append(item)
            continue
        if isinstance(item, Mapping):
            source = item
        else:
            source = {
                "citation_id": getattr(item, "citation_id", None),
                "file_name": getattr(item, "file_name", None),
                "page_number": getattr(item, "page_number", None),
                "chunk_id": getattr(item, "chunk_id", None),
            }
        if not source.get("citation_id") or not source.get("file_name"):
            continue
        try:
            refs.append(
                CitationRef(
                    citation_id=int(source["citation_id"]),
                    file_name=str(source["file_name"]),
                    page_number=source.get("page_number"),
                    chunk_id=source.get("chunk_id"),
                )
            )
        except (TypeError, ValueError):
            continue
    return refs


_KEYWORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}")
_KEYWORD_STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "into",
    "using",
    "paper",
    "the",
    "and",
    "for",
    "的",
    "了",
    "是",
    "在",
    "和",
    "与",
    "对",
    "研究",
}


def _extract_keywords(arguments: Dict[str, Any]) -> ToolResult:
    text = arguments.get("text", arguments.get("query", ""))
    top_n = arguments.get("top_n", 10)
    if not isinstance(text, str) or not text.strip():
        return _failure("keyword_extract", "text must be a non-empty string")
    if not isinstance(top_n, int) or isinstance(top_n, bool) or not 1 <= top_n <= 50:
        return _failure("keyword_extract", "top_n must be an integer between 1 and 50")
    counts = Counter(
        token.lower()
        for token in _KEYWORD_PATTERN.findall(text)
        if token.lower() not in _KEYWORD_STOPWORDS
    )
    keywords = [{"keyword": token, "count": count} for token, count in counts.most_common(top_n)]
    return _success("keyword_extract", {"keywords": keywords, "top_n": top_n})


def _safe_calculate(expression: str) -> float:
    if len(expression) > 256:
        raise ValueError("expression is too long")
    tree = ast.parse(expression, mode="eval")

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if not math.isfinite(float(node.value)):
                raise ValueError("non-finite numbers are not allowed")
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)
        ):
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent is too large")
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Div):
                result = left / right
            elif isinstance(node.op, ast.Mod):
                result = left % right
            else:
                result = left**right
            if not math.isfinite(result) or abs(result) > 1e100:
                raise ValueError("calculation result is outside safe bounds")
            return result
        raise ValueError("only numeric arithmetic is allowed")

    value = evaluate(tree)
    return int(value) if value.is_integer() else value


def _calculator(arguments: Dict[str, Any]) -> ToolResult:
    expression = arguments.get("expression", arguments.get("query", ""))
    if not isinstance(expression, str) or not expression.strip():
        return _failure("calculator", "expression must be a non-empty string")
    try:
        result = _safe_calculate(expression.strip())
    except Exception as exc:  # noqa: BLE001 - unsafe expressions are observations.
        return _failure("calculator", _error_text(exc))
    return _success("calculator", {"expression": expression.strip(), "result": result})


def build_default_tool_registry(
    rag_service: Any = None,
    paper_catalog: Any = None,
    search_fn: Optional[Callable[..., Any]] = None,
    summary_fn: Optional[Callable[..., Any]] = None,
    clock: Optional[Callable[[], Any]] = None,
    max_workers: int = 4,
) -> ToolRegistry:
    """Build exactly eight tools without initiating model or network work."""

    registry = ToolRegistry(max_workers=max_workers)

    def knowledge_retrieval(arguments: Dict[str, Any]) -> ToolResult:
        query = arguments.get("query", arguments.get("question", ""))
        top_k = arguments.get("top_k", 5)
        if not isinstance(query, str) or not query.strip():
            return _failure("knowledge_retrieval", "query must be a non-empty string")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 20:
            return _failure("knowledge_retrieval", "top_k must be an integer between 1 and 20")
        if rag_service is None:
            return _failure(
                "knowledge_retrieval",
                "知识库未配置：未注入 RAGService",
                {"enabled": False},
            )
        try:
            response = rag_service.answer(query.strip(), top_k=top_k)
            citations = _citation_refs(getattr(response, "citations", []))
            retrieved_chunks = getattr(response, "retrieved_chunks", [])
            retrieval_latency = getattr(response, "retrieval_latency_ms", None)
            latency_source = "backend_retrieval_latency"
            if not isinstance(retrieval_latency, (int, float)) or isinstance(retrieval_latency, bool):
                retrieval_latency = getattr(response, "latency_ms", None)
                latency_source = "backend_response_latency"
            data = {
                "answer": getattr(response, "answer", ""),
                "retrieved_chunks": to_jsonable(retrieved_chunks),
                "retrieved_count": len(retrieved_chunks) if hasattr(retrieved_chunks, "__len__") else 0,
                "retrieval_mode": getattr(rag_service, "retrieval_mode", None),
                "retrieval_latency_ms": retrieval_latency,
                "latency_source": latency_source,
                "token_usage": to_jsonable(getattr(response, "token_usage", None)),
                "fallback_used": bool(getattr(response, "fallback_used", False)),
                "error": getattr(response, "error", None),
            }
            token_usage = getattr(response, "token_usage", None)
            response_error = getattr(response, "error", None)
            if response_error:
                return ToolResult(
                    tool_name="knowledge_retrieval",
                    ok=False,
                    data=data,
                    error=str(response_error)[:500],
                    citations=citations,
                    token_usage=token_usage if isinstance(token_usage, Mapping) else None,
                )
            return _success(
                "knowledge_retrieval",
                data,
                citations,
                token_usage=token_usage if isinstance(token_usage, Mapping) else None,
            )
        except Exception as exc:  # noqa: BLE001 - backend failures stay in the trace.
            return _failure("knowledge_retrieval", _error_text(exc))

    def paper_metadata(arguments: Dict[str, Any]) -> ToolResult:
        paper_id = arguments.get("paper_id", "")
        if not isinstance(paper_id, str) or not paper_id.strip():
            return _failure("paper_metadata", "paper_id must be a non-empty string")
        paper = _lookup_paper(paper_catalog, paper_id.strip())
        if paper is None:
            return _failure("paper_metadata", "paper not found: " + paper_id.strip())
        return _success("paper_metadata", _paper_public(paper))

    def paper_compare(arguments: Dict[str, Any]) -> ToolResult:
        left_id = arguments.get("paper_a", arguments.get("left_paper_id", ""))
        right_id = arguments.get("paper_b", arguments.get("right_paper_id", ""))
        if not isinstance(left_id, str) or not isinstance(right_id, str) or not left_id.strip() or not right_id.strip():
            return _failure("paper_compare", "paper_a and paper_b are required")
        if left_id.strip() == right_id.strip():
            return _failure("paper_compare", "paper_a and paper_b must be different")
        left = _lookup_paper(paper_catalog, left_id.strip())
        right = _lookup_paper(paper_catalog, right_id.strip())
        missing = [paper_id for paper_id, paper in ((left_id, left), (right_id, right)) if paper is None]
        if missing:
            return _failure("paper_compare", "paper not found: " + ", ".join(missing))
        assert left is not None and right is not None
        fields = ("title", "year", "authors", "method", "datasets", "results", "abstract")
        return _success(
            "paper_compare",
            {
                "paper_a": {field: getattr(left, field) for field in fields},
                "paper_b": {field: getattr(right, field) for field in fields},
                "differences": {
                    field: getattr(left, field) != getattr(right, field) for field in fields
                },
            },
        )

    def paper_summary(arguments: Dict[str, Any]) -> ToolResult:
        paper_id = arguments.get("paper_id")
        text = arguments.get("text")
        paper = _lookup_paper(paper_catalog, paper_id) if isinstance(paper_id, str) else None
        if paper is None and (not isinstance(text, str) or not text.strip()):
            return _failure("paper_summary", "paper_id or non-empty text is required")
        source: Any = paper if paper is not None else {"text": str(text).strip()}
        summary_error: Optional[str] = None
        if summary_fn is not None:
            try:
                generated = summary_fn(source)
            except Exception as exc:  # noqa: BLE001 - injected adapters are isolated.
                summary_error = _error_text(exc)
            else:
                generated_data = to_jsonable(generated)
                generated_usage = (
                    generated_data.get("token_usage")
                    if isinstance(generated_data, Mapping)
                    else None
                )
                return _success(
                    "paper_summary",
                    generated_data,
                    token_usage=generated_usage if isinstance(generated_usage, Mapping) else None,
                )
        source_text = paper.text if paper is not None else str(text)
        return _success(
            "paper_summary",
            _extractive_paper_summary(paper, source_text, summary_error),
        )

    def current_time(arguments: Dict[str, Any]) -> ToolResult:
        del arguments
        try:
            now = clock() if clock is not None else datetime.now(timezone.utc).astimezone()
            value = now.isoformat() if isinstance(now, datetime) else str(now)
        except Exception as exc:  # noqa: BLE001 - injected clocks are isolated.
            return _failure("current_time", _error_text(exc))
        return _success("current_time", {"current_time": value})

    def web_search(arguments: Dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        if not isinstance(query, str) or not query.strip():
            return _failure("web_search", "query must be a non-empty string")
        if not isinstance(max_results, int) or isinstance(max_results, bool) or not 1 <= max_results <= 10:
            return _failure("web_search", "max_results must be an integer between 1 and 10")
        if search_fn is None:
            return _failure(
                "web_search",
                "web search is disabled; inject search_fn explicitly to enable it",
                {"enabled": False, "query": query.strip(), "results": []},
            )
        try:
            results = search_fn(query.strip(), max_results)
        except Exception as exc:  # noqa: BLE001 - injected network adapters are isolated.
            return _failure("web_search", _error_text(exc))
        return _success(
            "web_search",
            {"enabled": True, "query": query.strip(), "results": to_jsonable(results)},
        )

    registry.register(
        ToolSpec(
            name="knowledge_retrieval",
            description="Search the configured knowledge base and return grounded answer, chunks, and real citations.",
            handler=knowledge_retrieval,
            input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}},
        )
    )
    registry.register(
        ToolSpec(
            name="paper_metadata",
            description="Read metadata for a paper from the injected paper catalog.",
            handler=paper_metadata,
            input_schema={"type": "object", "required": ["paper_id"], "properties": {"paper_id": {"type": "string"}}},
        )
    )
    registry.register(
        ToolSpec(
            name="paper_compare",
            description="Compare two papers from the injected paper catalog.",
            handler=paper_compare,
            input_schema={"type": "object", "required": ["paper_a", "paper_b"], "properties": {"paper_a": {"type": "string"}, "paper_b": {"type": "string"}}},
        )
    )
    registry.register(
        ToolSpec(
            name="keyword_extract",
            description="Extract deterministic, frequency-ranked keywords from text.",
            handler=_extract_keywords,
            input_schema={"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}, "top_n": {"type": "integer"}}},
        )
    )
    registry.register(
        ToolSpec(
            name="paper_summary",
            description="Return a structured extractive paper summary or an injected summary result.",
            handler=paper_summary,
            input_schema={"type": "object", "properties": {"paper_id": {"type": "string"}, "text": {"type": "string"}}},
        )
    )
    registry.register(
        ToolSpec(
            name="current_time",
            description="Return the current local time from the injected clock or system clock.",
            handler=current_time,
            input_schema={"type": "object", "properties": {}},
        )
    )
    registry.register(
        ToolSpec(
            name="calculator",
            description="Evaluate a bounded arithmetic expression without names, calls, or file access.",
            handler=_calculator,
            input_schema={"type": "object", "required": ["expression"], "properties": {"expression": {"type": "string"}}},
        )
    )
    registry.register(
        ToolSpec(
            name="web_search",
            description="Search the web only when an explicit search_fn adapter has been injected.",
            handler=web_search,
            input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}},
            retryable=False,
        )
    )
    return registry


__all__ = [
    "InMemoryPaperCatalog",
    "PaperRecord",
    "ToolHandler",
    "ToolRegistry",
    "ToolSpec",
    "build_default_tool_registry",
]
