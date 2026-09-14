"""Small deterministic fast-path router before the general ReAct loop."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from .schemas import AgentRequest


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field(pattern=r"^(direct|react)$")
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class IntentRouter:
    """Route unambiguous intents before handing research questions to ReAct."""

    _time_terms = ("当前时间", "现在几点", "现在时间", "今天几号", "日期和时间", "what time")

    @staticmethod
    def _calculator_expression(message: str) -> Optional[str]:
        text = message.strip()
        text = re.sub(r"^(请|帮我|请帮我)?\s*(计算|算一下|算)\s*", "", text, flags=re.IGNORECASE)
        if not re.fullmatch(r"[0-9+\-*/%.()\s]+", text):
            return None
        if not re.search(r"\d", text):
            return None
        return text

    @staticmethod
    def _keyword_text(message: str) -> str:
        text = re.sub(r"关键词|关键字|提取", " ", message)
        text = re.sub(r"^(请|帮我|从|中|里|一下)\s*", "", text)
        return text.strip()

    @staticmethod
    def _metadata_text(request: AgentRequest, key: str) -> Optional[str]:
        value = request.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _has_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)

    def decide(self, request: AgentRequest) -> RouteDecision:
        message = request.message.strip()
        expression = self._calculator_expression(message)
        if expression is not None:
            return RouteDecision(
                mode="direct",
                tool_name="calculator",
                arguments={"expression": expression},
                reason="pure arithmetic expression",
            )
        lowered = message.casefold()
        if any(term in lowered for term in self._time_terms):
            return RouteDecision(
                mode="direct",
                tool_name="current_time",
                reason="time intent",
            )
        if "关键词" in message or "关键字" in message:
            text = self._keyword_text(message)
            if text:
                return RouteDecision(
                    mode="direct",
                    tool_name="keyword_extract",
                    arguments={"text": text},
                    reason="keyword extraction intent",
                )
        paper_id = self._metadata_text(request, "paper_id")
        paper_a = self._metadata_text(request, "paper_a")
        paper_b = self._metadata_text(request, "paper_b")
        if paper_a and paper_b and self._has_any(
            message,
            ("对比", "比较", "区别", "compare"),
        ):
            return RouteDecision(
                mode="direct",
                tool_name="paper_compare",
                arguments={"paper_a": paper_a, "paper_b": paper_b},
                reason="explicit paper comparison with paper IDs",
            )
        if paper_id and self._has_any(
            message,
            ("元信息", "作者", "年份", "摘要", "doi", "DOI"),
        ):
            tool_name = "paper_summary" if self._has_any(message, ("摘要", "总结", "概括")) else "paper_metadata"
            arguments = {"paper_id": paper_id}
            return RouteDecision(
                mode="direct",
                tool_name=tool_name,
                arguments=arguments,
                reason="explicit paper ID and intent metadata",
            )
        if self._has_any(
            lowered,
            (
                "查知识库",
                "查一下知识库",
                "查询知识库",
                "检索知识库",
                "知识库检索",
                "从知识库",
                "检索文档",
                "查询文档",
                "文档中检索",
                "从文档中查",
                "knowledge base",
                "knowledge retrieval",
                "retrieve",
            ),
        ):
            top_k = request.metadata.get("top_k", 5)
            if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 20:
                top_k = 5
            return RouteDecision(
                mode="direct",
                tool_name="knowledge_retrieval",
                arguments={"query": message, "top_k": top_k},
                reason="explicit knowledge-base retrieval intent",
            )
        if self._has_any(
            lowered,
            ("联网搜索", "网上搜索", "网络搜索", "web search", "search the web"),
        ):
            max_results = request.metadata.get("max_results", 5)
            if not isinstance(max_results, int) or isinstance(max_results, bool) or not 1 <= max_results <= 10:
                max_results = 5
            return RouteDecision(
                mode="direct",
                tool_name="web_search",
                arguments={"query": message, "max_results": max_results},
                reason="explicit web-search intent",
            )
        return RouteDecision(mode="react", reason="requires general Agent reasoning")


__all__ = ["IntentRouter", "RouteDecision"]
