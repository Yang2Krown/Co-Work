# Backend architecture

## Responsibility boundary

成员 A 的后端负责：

- 多格式文档加载和失败项报告；
- 可配置分块、Embedding、Chroma/FAISS 向量存储和增量索引；
- vector、BM25、RRF、reranker 三档检索；
- Prompt、上下文截断、LLM client、Citation、streaming；
- 语义缓存、检索降级、LLM 错误保护和基础结构化请求日志。

后端不实现前端页面、Agent ReAct 主循环、工具路由、长期记忆、系统级 QA
评测或部署编排。

## Request flow

```text
document paths
    ↓
loaders → Document
    ↓
chunking → Chunk + source/page metadata
    ↓
EmbeddingService → vectors
    ↓
IncrementalIndex → Chroma / FAISS

question
    ↓
SemanticCache lookup (question embedding + KB version + generation config)
    ↓ miss
HybridRetriever
    ├─ VectorRetriever
    ├─ BM25Retriever
    ├─ hand-written RRF
    └─ configurable Reranker
    ↓
ContextBuilder → bounded, deduplicated, source-labelled context
    ↓
Prompt + OpenAI-compatible LLMClient
    ├─ answer → RAGResponse
    └─ stream → text fragments
    ↓
Citation + structured request log
```

## Stable module boundaries

| Boundary | Main interface | Persistence/network behavior |
| --- | --- | --- |
| Loader | `ingest_documents(paths)` | Reads local documents; no model call |
| Index | `IncrementalIndex.index_documents()` | Persists vector store and manifest |
| Retrieval | `HybridRetriever.retrieve()` | Returns `RetrievalResult` only |
| Context | `ContextBuilder.build()` | Bounds and traces chunks before generation |
| LLM | `LLMClient.generate/stream()` | Network call only when explicitly invoked |
| RAG | `RAGService.answer/stream_answer()` | Orchestrates retrieval, generation, citation and safeguards |

All cross-layer data uses the schemas in `src/backend/schemas/models.py`.

## Configuration and runtime safety

Adjustable values live in `config/backend.yaml`. The default test suite injects
small fake models and does not download weights or call an API. Real model checks
are opt-in through `scripts/smoke_test_retrieval.py`. API keys are read from the
environment and are never included in structured log fields.

FAISS defaults to one thread for compatibility with the local macOS
SentenceTransformers/PyTorch runtime; `vector_store.faiss_num_threads` can be
adjusted for a deployment that has validated a different setting.
