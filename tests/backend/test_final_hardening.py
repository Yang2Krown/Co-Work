from typing import Iterator, List

from src.backend.exceptions import LLMServiceError
from src.backend.rag import GenerationConfig, LLMResponse, RAGService
from src.backend.schemas import RetrievalResult


def _result(**scores: float) -> RetrievalResult:
    return RetrievalResult(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="retrieved evidence",
        file_name="paper.pdf",
        page_number=5,
        rank=1,
        **scores,
    )


class StubRetriever:
    def __init__(self, results: List[RetrievalResult]) -> None:
        self.results = results

    def retrieve(self, query: str, mode: str, top_k: int) -> List[RetrievalResult]:
        return self.results


class StubLLM:
    model_name = "test-model"

    def stream(self, prompt, config: GenerationConfig) -> Iterator[str]:
        yield "answer"

    def generate(self, prompt, config: GenerationConfig) -> LLMResponse:
        return LLMResponse("answer")


class FailingLLM(StubLLM):
    def stream(self, prompt, config: GenerationConfig) -> Iterator[str]:
        raise LLMServiceError("provider unavailable")
        yield "never reached"


def _service(result: RetrievalResult) -> RAGService:
    return RAGService(
        StubRetriever([result]),
        StubLLM(),
        low_relevance_threshold=0.2,
    )


def test_low_relevance_uses_vector_score_below_threshold() -> None:
    assert _service(_result(vector_score=0.19))._is_low_relevance([_result(vector_score=0.19)])


def test_low_relevance_does_not_flag_vector_score_above_threshold() -> None:
    assert not _service(_result(vector_score=0.21))._is_low_relevance([_result(vector_score=0.21)])


def test_low_relevance_ignores_rrf_score_without_vector_score() -> None:
    assert not _service(_result(rrf_score=0.001))._is_low_relevance([_result(rrf_score=0.001)])


def test_low_relevance_ignores_rerank_score_without_vector_score() -> None:
    assert not _service(_result(rerank_score=-1.0))._is_low_relevance([_result(rerank_score=-1.0)])


def test_low_relevance_ignores_missing_scores() -> None:
    assert not _service(_result())._is_low_relevance([_result()])


def test_structured_stream_starts_with_grounded_metadata_and_ends() -> None:
    events = list(_service(_result(vector_score=0.9)).stream_answer_events("question", request_id="req-1"))

    assert [event.event for event in events] == [
        "retrieval_started", "metadata", "retrieval_finished", "llm_started",
        "token", "llm_finished", "end",
    ]
    assert events[1].request_id == "req-1"
    assert events[1].citations[0].page_number == 5
    assert events[1].citations[0].chunk_id == "chunk-1"
    assert events[1].retrieved_chunks[0].chunk_id == "chunk-1"
    assert events[4].text == "answer"
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))


def test_structured_stream_reports_provider_error() -> None:
    service = RAGService(StubRetriever([_result(vector_score=0.9)]), FailingLLM())

    events = list(service.stream_answer_events("question", request_id="req-2"))

    assert [event.event for event in events] == [
        "retrieval_started", "metadata", "retrieval_finished", "llm_started",
        "error", "llm_finished", "end",
    ]
    assert events[1].citations[0].page_number == 5
    assert events[4].text == "生成服务暂时不可用，请稍后重试。"
    assert events[4].error == "LLMServiceError: provider unavailable"
