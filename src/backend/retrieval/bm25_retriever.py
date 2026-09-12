"""Independent BM25 keyword retrieval."""

import re
from typing import Callable, List, Sequence

from rank_bm25 import BM25Okapi

from ..exceptions import RetrievalError
from ..schemas import Chunk, RetrievalResult


Tokenizer = Callable[[str], List[str]]


def default_tokenizer(text: str) -> List[str]:
    """Tokenize English words and individual CJK characters for mixed corpora."""

    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower())


class BM25Retriever:
    """Build and query a BM25 index without depending on vector search."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        tokenizer: Tokenizer = default_tokenizer,
    ) -> None:
        self.tokenizer = tokenizer
        self.replace_chunks(chunks)

    def replace_chunks(self, chunks: Sequence[Chunk]) -> None:
        self.chunks = list(chunks)
        tokenized = [self.tokenizer(chunk.text) for chunk in self.chunks]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def retrieve(self, query: str, top_k: int = 20) -> List[RetrievalResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        if not query.strip() or not self.chunks or self._bm25 is None:
            return []
        query_tokens = self.tokenizer(query)
        if not query_tokens:
            return []
        try:
            scores = self._bm25.get_scores(query_tokens)
        except Exception as exc:
            raise RetrievalError("BM25 retrieval failed") from exc

        ranked = sorted(
            enumerate(scores),
            key=lambda item: (-float(item[1]), self.chunks[item[0]].chunk_id),
        )[:top_k]
        return [
            RetrievalResult(
                chunk_id=self.chunks[index].chunk_id,
                text=self.chunks[index].text,
                document_id=self.chunks[index].document_id,
                file_name=self.chunks[index].file_name,
                page_number=self.chunks[index].page_number,
                bm25_score=float(score),
                rank=rank,
            )
            for rank, (index, score) in enumerate(ranked, start=1)
        ]


__all__ = ["BM25Retriever", "default_tokenizer"]
