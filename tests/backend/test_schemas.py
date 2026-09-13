from src.backend.schemas import Citation, Chunk, Document, RAGResponse, RetrievalResult


def test_core_backend_models_preserve_traceability() -> None:
    document = Document(
        document_id="doc-1",
        file_name="paper.pdf",
        file_type="pdf",
        text="A short paper.",
        metadata={"source_path": "data/raw/paper.pdf", "title": "A Paper"},
    )
    chunk = Chunk(
        chunk_id="doc-1-chunk-1",
        document_id=document.document_id,
        text="A short paper.",
        page_number=5,
        file_name=document.file_name,
        metadata={"source_path": "data/raw/paper.pdf"},
    )
    result = RetrievalResult(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        text=chunk.text,
        file_name=chunk.file_name,
        page_number=chunk.page_number,
        vector_score=0.91,
        rank=1,
    )
    response = RAGResponse(
        answer="Answer grounded in the paper.",
        citations=[
            Citation(
                citation_id=1,
                file_name=chunk.file_name,
                page_number=chunk.page_number,
                chunk_id=chunk.chunk_id,
            )
        ],
        retrieved_chunks=[result],
        latency_ms=12.5,
        token_usage={"total_tokens": 20},
    )

    assert response.retrieved_chunks[0].chunk_id == "doc-1-chunk-1"
    assert response.citations[0].file_name == "paper.pdf"
    assert response.citations[0].page_number == 5
    assert response.fallback_used is False
