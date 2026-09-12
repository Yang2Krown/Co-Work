import logging
from typing import Iterator, List

from src.backend.exceptions import LLMServiceError
from src.backend.rag import (
    ContextBuilder,
    GenerationConfig,
    LLMResponse,
    RAGPrompt,
    RAGService,
    SemanticCache,
    StructuredJSONFormatter,
)
from src.backend.schemas import RAGResponse, RetrievalResult


def _result(score: float = 0.9) -> RetrievalResult:
    return RetrievalResult(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="retrieved evidence",
        file_name="paper.pdf",
        page_number=5,
        vector_score=score,
        rank=1,
    )


class StubRetriever:
    def __init__(self, results: List[RetrievalResult]) -> None:
        self.results = results
        self.calls = 0

    def retrieve(self, query: str, mode: str, top_k: int) -> List[RetrievalResult]:
        self.calls += 1
        return self.results


class StubLLM:
    model_name = "test-model"

    def __init__(self, text: str = "answer [1]") -> None:
        self.text = text
        self.calls = 0
        self.prompts: List[RAGPrompt] = []

    def generate(self, prompt: RAGPrompt, config: GenerationConfig) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        return LLMResponse(self.text, {"total_tokens": 3})

    def stream(self, prompt: RAGPrompt, config: GenerationConfig) -> Iterator[str]:
        yield self.text


class FailingLLM(StubLLM):
    def generate(self, prompt: RAGPrompt, config: GenerationConfig) -> LLMResponse:
        raise LLMServiceError("provider unavailable")

    def stream(self, prompt: RAGPrompt, config: GenerationConfig) -> Iterator[str]:
        raise LLMServiceError("provider unavailable")
        yield "never reached"


def _embedding(_: str) -> List[float]:
    return [1.0, 0.0]


def test_semantic_cache_checks_similarity_version_and_generation_config() -> None:
    cache = SemanticCache(_embedding, similarity_threshold=0.9)
    response = RAGResponse(answer="cached", latency_ms=1)
    config = GenerationConfig(temperature=0.2)
    cache.put("original question", response, "kb-v1", config)

    assert cache.get("similar question", "kb-v1", config) == response
    assert cache.get("similar question", "kb-v2", config) is None
    assert cache.get("similar question", "kb-v1", GenerationConfig(temperature=0.5)) is None


def test_rag_service_uses_semantic_cache_without_retrieving_again() -> None:
    retriever = StubRetriever([_result()])
    llm = StubLLM()
    service = RAGService(
        retriever,
        llm,
        cache=SemanticCache(_embedding, similarity_threshold=0.9),
        context_builder=ContextBuilder(max_chars=500),
    )

    first = service.answer("question one")
    second = service.answer("question two")

    assert first.answer == second.answer
    assert retriever.calls == 1
    assert llm.calls == 1


def test_no_results_sets_fallback_and_uses_explicit_evidence_prompt() -> None:
    llm = StubLLM()
    service = RAGService(StubRetriever([]), llm, allow_llm_fallback=True)

    response = service.answer("unanswered question")

    assert response.fallback_used is True
    assert response.citations == []
    assert "当前知识库中未找到充分依据" in llm.prompts[0].system


def test_no_results_without_llm_fallback_returns_friendly_response() -> None:
    llm = StubLLM()
    service = RAGService(StubRetriever([]), llm, allow_llm_fallback=False)

    response = service.answer("unanswered question")

    assert response.fallback_used is True
    assert "当前知识库中未找到相关文档" in response.answer
    assert llm.calls == 0


def test_low_relevance_notice_keeps_candidates() -> None:
    llm = StubLLM()
    service = RAGService(
        StubRetriever([_result(score=0.05)]),
        llm,
        low_relevance_threshold=0.2,
    )

    response = service.answer("weak question")

    assert response.retrieved_chunks[0].chunk_id == "chunk-1"
    assert "Evidence Quality Notice" in llm.prompts[0].user


def test_llm_failure_returns_structured_error_and_logs_request(caplog) -> None:
    logger = logging.getLogger("backend.rag.test_m6")
    service = RAGService(StubRetriever([_result()]), FailingLLM(), logger=logger)
    caplog.set_level(logging.INFO, logger=logger.name)

    response = service.answer("question", request_id="request-1")

    assert response.answer == "生成服务暂时不可用，请稍后重试。"
    assert response.error == "LLMServiceError: provider unavailable"
    assert response.fallback_used is False
    events = [record.rag_event for record in caplog.records if hasattr(record, "rag_event")]
    assert len(events) == 1
    assert events[0]["request_id"] == "request-1"
    assert events[0]["retrieved_chunks"][0]["chunk_id"] == "chunk-1"
    assert events[0]["llm_model"] == "test-model"
    assert "OPENAI_API_KEY" not in str(events[0])


def test_stream_failure_yields_friendly_message() -> None:
    service = RAGService(StubRetriever([_result()]), FailingLLM())

    chunks = list(service.stream_answer("question"))

    assert chunks == ["生成服务暂时不可用，请稍后重试。"]


def test_structured_formatter_serializes_rag_event() -> None:
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "rag_request", (), None)
    record.rag_event = {"request_id": "request-1", "answer": "safe"}

    formatted = formatter.format(record)

    assert '"request_id": "request-1"' in formatted
    assert '"answer": "safe"' in formatted
