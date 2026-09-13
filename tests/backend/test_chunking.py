from pathlib import Path

import pytest

from scripts.evaluate_chunking import evaluate
from src.backend.chunking import (
    chunk_document,
    fixed_size_chunks,
    paragraph_chunks,
    recursive_chunks,
    semantic_chunks,
)
from src.backend.schemas import Document


def _document(text: str) -> Document:
    return Document(
        document_id="doc-m2",
        file_name="paper.pdf",
        file_type="pdf",
        text=text,
        metadata={"source_path": "data/raw/paper.pdf", "title": "M2 paper"},
    )


def _paged_document() -> Document:
    page_one = "第一页面包含背景信息。"
    page_two = "第二页面包含实验结果。"
    return Document(
        document_id="doc-pages",
        file_name="paged.pdf",
        file_type="pdf",
        text="\n\f\n".join([page_one, page_two]),
        metadata={
            "source_path": "data/raw/paged.pdf",
            "pages": [
                {"page_number": 1, "text": page_one},
                {"page_number": 2, "text": page_two},
            ],
        },
    )


def test_fixed_chunk_sizes_and_overlap_are_configurable() -> None:
    document = _document("0123456789" * 130)

    for size in (256, 512, 1024):
        chunks = fixed_size_chunks(document, chunk_size=size, chunk_overlap=32)
        assert chunks
        assert all(len(chunk.text) <= size for chunk in chunks)
        assert chunks[0].metadata["strategy"] == "fixed"

    chunks = fixed_size_chunks(document, chunk_size=256, chunk_overlap=64)
    assert chunks[0].text[-64:] == chunks[1].text[:64]


def test_recursive_chunking_prefers_text_boundaries() -> None:
    document = _document("第一段内容。\n\n第二段内容。\n\n第三段内容。")

    chunks = recursive_chunks(document, chunk_size=12, chunk_overlap=0)

    assert [chunk.text for chunk in chunks] == [
        "第一段内容。\n\n",
        "第二段内容。\n\n",
        "第三段内容。",
    ]


def test_semantic_and_structure_strategies_preserve_units() -> None:
    document = _document("第一句。第二句！\n\n新的段落。")

    sentence_chunks = semantic_chunks(document, chunk_size=8, chunk_overlap=0)
    paragraph_result = paragraph_chunks(document, chunk_size=10, chunk_overlap=0)

    assert all(chunk.text[-1] in "。！\n" for chunk in sentence_chunks)
    assert len(paragraph_result) == 2
    assert paragraph_result[0].metadata["strategy"] == "structure"


def test_chunks_preserve_document_and_page_traceability() -> None:
    document = _paged_document()

    chunks = fixed_size_chunks(document, chunk_size=18, chunk_overlap=0)

    assert chunks
    assert all(chunk.document_id == document.document_id for chunk in chunks)
    assert all(chunk.file_name == "paged.pdf" for chunk in chunks)
    crossing = [chunk for chunk in chunks if chunk.metadata["page_numbers"] == [1, 2]]
    assert crossing
    assert crossing[0].page_number == 1
    assert crossing[0].metadata["source_path"] == "data/raw/paged.pdf"


def test_chunk_service_dispatch_and_validation() -> None:
    document = _document("some text")

    assert chunk_document(document, strategy="fixed", chunk_size=4, chunk_overlap=0)
    assert chunk_document(document, strategy="structure", chunk_size=4, chunk_overlap=0)
    with pytest.raises(ValueError, match="chunk_overlap"):
        fixed_size_chunks(document, chunk_size=4, chunk_overlap=4)
    with pytest.raises(ValueError, match="Unknown chunking strategy"):
        chunk_document(document, strategy="unknown")


def test_empty_document_returns_no_chunks() -> None:
    assert fixed_size_chunks(_document("")) == []
    assert recursive_chunks(_document("")) == []
    assert semantic_chunks(_document("")) == []


def test_chunking_experiment_reports_observed_statistics(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("第一句。第二句。", encoding="utf-8")

    report = evaluate([path], ["fixed", "semantic"], [4], 0)

    assert report["errors"] == []
    assert len(report["records"]) == 2
    assert {record["strategy"] for record in report["records"]} == {
        "fixed",
        "semantic",
    }
    assert all(record["chunk_count"] > 0 for record in report["records"])
