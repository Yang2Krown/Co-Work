# Backend integration contract

This document describes the Python interfaces exposed to the Agent and frontend
members. They can compose these interfaces without depending on Chroma, FAISS,
the HTTP transport, or private implementation details.

## Document ingestion

```python
from pathlib import Path
from src.backend.loaders import ingest_documents

result = ingest_documents([Path("paper.pdf"), Path("notes.md")])
```

The returned `IngestionResult` reports successful items, failed files and errors.
Use `IncrementalIndex.index_documents()` after loading to create or update the
configured vector index. Source paths, document IDs, chunk IDs and page metadata
remain traceable through the index.

## Retrieval

```python
results = hybrid_retriever.retrieve(
    query="问题",
    mode="hybrid_rerank",
    top_k=5,
)
```

Supported modes are:

- `vector`: vector retrieval only;
- `hybrid`: vector + independent BM25 + RRF;
- `hybrid_rerank`: hybrid candidates followed by the configured reranker.

Each item is a `RetrievalResult` containing its `chunk_id`, text, document/file
identity, optional page number and the scores available for that mode.

## RAG answer

```python
response = rag_service.answer("问题", top_k=5)
```

`response` is a `RAGResponse`:

```text
answer             str
citations          list[Citation]
retrieved_chunks   list[RetrievalResult]
latency_ms         float
token_usage        dict | null
fallback_used      bool
error              str | null
```

`Citation.citation_id` matches the `[n]` marker used by the context Prompt;
`file_name`, `page_number` and `chunk_id` are copied from retrieved data. A
missing page remains `null` and is never inferred.

## Streaming answer

```python
for fragment in rag_service.stream_answer("问题", top_k=5):
    consume(fragment)
```

The generator yields text fragments. The caller owns presentation concerns such
as a typewriter effect or SSE conversion. Provider failures yield a friendly
error message and are recorded by the backend logger.

## Construction and configuration

Use `config/backend.yaml` and `src.backend.config.load_config()` for adjustable
values. The OpenAI-compatible client is created without a network request:

```python
from src.backend.config import load_config
from src.backend.rag import GenerationConfig, RAGService, create_llm_client

config = load_config()
llm_client = create_llm_client(
    provider=config.rag.provider,
    model_name=config.rag.model_name,
    api_base=config.rag.api_base,
    api_key_env=config.rag.api_key_env,
    timeout_seconds=config.rag.timeout_seconds,
)
rag_service = RAGService(
    retriever=hybrid_retriever,
    llm_client=llm_client,
    generation_config=GenerationConfig(
        temperature=config.rag.temperature,
        top_p=config.rag.top_p,
        top_k=config.rag.top_k,
        max_output_tokens=config.rag.max_output_tokens,
    ),
    default_top_k=config.retrieval.final_top_k,
    retrieval_mode="hybrid_rerank",
    allow_llm_fallback=config.rag.allow_llm_fallback,
    low_relevance_threshold=config.rag.low_relevance_threshold,
)
```

Caching requires an embedding callback and an explicit knowledge-base version;
the version must change when the indexed corpus changes. Frontend and Agent code
should not pass API keys in requests or log payloads.
