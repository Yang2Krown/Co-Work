from typing import Iterator, List

from src.backend.exceptions import LLMServiceError
from src.backend.rag import GenerationConfig, LLMResponse, RAGService
from src.backend.rag.llm_client import OpenAICompatibleClient
from src.backend.rag.prompt import RAGPrompt
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

    def __init__(self) -> None:
        self.last_token_usage = None

    def stream(self, prompt, config: GenerationConfig) -> Iterator[str]:
        self.last_token_usage = {
            "prompt_tokens": 11,
            "completion_tokens": 5,
            "total_tokens": 16,
        }
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
    assert events[5].metadata["token_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 5,
        "total_tokens": 16,
    }
    assert events[-1].metadata["token_usage"] == events[5].metadata["token_usage"]
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


def test_openai_stream_collects_provider_usage_frame(monkeypatch) -> None:
    client = OpenAICompatibleClient(
        model_name="deepseek-chat",
        api_base="https://api.deepseek.com",
        api_key_env="",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":null}]}\n'
            yield b'data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":3,"total_tokens":10}}\n'
            yield b"data: [DONE]\n"

    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: Response())

    assert list(client.stream(RAGPrompt(system="system", user="user"), GenerationConfig())) == ["answer"]
    assert client.last_token_usage == {
        "prompt_tokens": 7,
        "completion_tokens": 3,
        "total_tokens": 10,
    }
