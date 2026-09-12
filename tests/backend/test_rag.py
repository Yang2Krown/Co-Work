from typing import Iterator, List

from src.backend.rag import (
    ContextBuilder,
    GenerationConfig,
    LLMResponse,
    RAGPrompt,
    RAGService,
    build_citations,
    build_prompt,
)
from src.backend.schemas import RetrievalResult


def _result(
    chunk_id: str,
    text: str,
    rank: int,
    page_number: int | None = 1,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id="doc-1",
        text=text,
        file_name="paper.pdf",
        page_number=page_number,
        vector_score=0.9,
        rank=rank,
    )


def test_context_builder_sorts_deduplicates_and_preserves_source() -> None:
    results = [
        _result("chunk-2", "second evidence", rank=2, page_number=None),
        _result("chunk-1", "first evidence", rank=1),
        _result("chunk-duplicate", " FIRST   EVIDENCE ", rank=3),
    ]

    built = ContextBuilder(max_chars=600).build(results)

    assert [chunk.chunk_id for chunk in built.chunks] == ["chunk-1", "chunk-2"]
    assert built.text.index("first evidence") < built.text.index("second evidence")
    assert "[1] paper.pdf, p.1 (chunk_id=chunk-1)" in built.text
    assert "[2] paper.pdf, page unavailable (chunk_id=chunk-2)" in built.text


def test_context_builder_truncates_to_configured_limit() -> None:
    built = ContextBuilder(max_chars=100).build(
        [_result("chunk-1", "evidence " * 100, rank=1)]
    )

    assert len(built.text) <= 100
    assert built.text.endswith("…")
    assert len(built.chunks) == 1


def test_prompt_contains_required_grounding_sections() -> None:
    prompt = build_prompt("What is the result?", "[1] paper.pdf, p.1\nEvidence")

    combined = prompt.system + prompt.user
    for section in (
        "Retrieved Context",
        "User Question",
        "Output Format",
        "Citation Rules",
        "Insufficient Evidence Rules",
    ):
        assert section in combined
    assert "paper.pdf" in combined


def test_citations_only_copy_retrieved_traceability() -> None:
    citations = build_citations([_result("chunk-1", "evidence", rank=1, page_number=None)])

    assert citations[0].citation_id == 1
    assert citations[0].file_name == "paper.pdf"
    assert citations[0].page_number is None
    assert citations[0].chunk_id == "chunk-1"


class StubRetriever:
    def __init__(self, results: List[RetrievalResult]) -> None:
        self.results = results
        self.calls = []

    def retrieve(self, query: str, mode: str, top_k: int) -> List[RetrievalResult]:
        self.calls.append((query, mode, top_k))
        return self.results


class StubLLM:
    def __init__(self) -> None:
        self.generate_calls = []
        self.stream_calls = []

    def generate(self, prompt: RAGPrompt, config: GenerationConfig) -> LLMResponse:
        self.generate_calls.append((prompt, config))
        return LLMResponse("Grounded answer [1]", {"total_tokens": 12})

    def stream(self, prompt: RAGPrompt, config: GenerationConfig) -> Iterator[str]:
        self.stream_calls.append((prompt, config))
        yield from ("Grounded ", "answer")


def test_rag_service_returns_answer_chunks_citations_and_stream() -> None:
    retriever = StubRetriever([_result("chunk-1", "evidence", rank=1)])
    llm = StubLLM()
    generation_config = GenerationConfig(
        temperature=0.4,
        top_p=0.8,
        top_k=20,
        max_output_tokens=100,
    )
    service = RAGService(
        retriever,
        llm,
        generation_config=generation_config,
        retrieval_mode="hybrid_rerank",
        context_builder=ContextBuilder(max_chars=500),
    )

    response = service.answer("What is the result?", top_k=3)
    streamed = list(service.stream_answer("What is the result?", top_k=3))

    assert response.answer == "Grounded answer [1]"
    assert response.retrieved_chunks[0].chunk_id == "chunk-1"
    assert response.citations[0].chunk_id == "chunk-1"
    assert response.token_usage == {"total_tokens": 12}
    assert response.latency_ms >= 0
    assert streamed == ["Grounded ", "answer"]
    assert retriever.calls == [
        ("What is the result?", "hybrid_rerank", 3),
        ("What is the result?", "hybrid_rerank", 3),
    ]
    assert llm.generate_calls[0][1] == generation_config
    assert llm.stream_calls[0][1] == generation_config


def test_rag_service_prompts_explicit_insufficient_evidence() -> None:
    retriever = StubRetriever([])
    llm = StubLLM()
    service = RAGService(retriever, llm)

    response = service.answer("Unknown question")

    assert response.citations == []
    assert response.retrieved_chunks == []
    assert "当前知识库中未找到充分依据" in llm.generate_calls[0][0].system
