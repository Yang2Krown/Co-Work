# Retrieval experiment

## Scope

M4 exposes and compares three retrieval modes:

1. `vector`: configurable Top-K vector retrieval;
2. `hybrid`: vector retrieval + independent BM25 + hand-written RRF;
3. `hybrid_rerank`: hybrid candidates + configurable bge reranker.

The RRF implementation is maintained in `src/backend/retrieval/rrf.py` and is
not delegated to a framework.

## Evaluation input

Provide a JSONL file with one hand-verified real evaluation item per line. Use
chunk IDs when evaluating one fixed chunking configuration:

```json
{"question": "What is the main method?", "relevant_chunk_ids": ["doc-id:recursive:0"]}
```

`relevant_chunk_ids` must refer to real chunks produced by the indexed corpus.
For a QA set shared across chunking strategies or embedding models, prefer
stable document/page labels:

```json
{"question": "What is the main method?", "relevant_document_ids": ["<sha256-of-real-file>"], "relevant_page_numbers": [2]}
```

At least one of `relevant_chunk_ids` and `relevant_document_ids` is required;
page numbers, when supplied, are matched against retrieved metadata.

## Reproducible command

```bash
.venv/bin/python scripts/evaluate_retrieval.py path/to/paper.pdf --evaluation path/to/retrieval.jsonl --output /tmp/retrieval-results.json
```

The script computes Hit@5 and MRR independently for all three modes and writes
the observed values as JSON. It loads the configured embedding model only when
the script is explicitly run.

## Current record

以下数据均来自真实实验运行。

- 数据集：5 篇 Transformer 论文 PDF
- QA：20 条人工核验问题
- Python：3.11.16；实验日期：2026-09-13
- Chunking：`structure`，size 512，overlap 64
- Embedding：`bge-large-zh` (`BAAI/bge-large-zh-v1.5`)
- Vector store：`InMemoryVectorStore`；Top-K：5
- Reranker：`bge-reranker-base` (`BAAI/bge-reranker-base`)

| mode | Hit@5 | MRR | avg query (ms) | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| vector | 0.7500 | 0.5725 | 31.58 | 31.68 | 34.86 |
| hybrid | 0.8000 | 0.6475 | 34.13 | 33.20 | 41.28 |
| hybrid_rerank | 0.8500 | 0.7142 | 987.40 | 487.04 | 1091.77 |

`hybrid_rerank` 首次查询为 10465.94 ms，后续 warm 查询平均为 488.53 ms；
首次耗时包含 reranker 的真实模型加载。三种模式均完整执行 20 条 QA，未删除
失败 query。本轮没有单独实现 Recall@K，因此没有伪造 Recall 数字；Hit@5
使用至少一个 gold document/page 命中的定义，MRR 使用第一个命中的排名倒数。

结论：本数据集上 `hybrid_rerank` 的 Hit@5 和 MRR 最好，`vector` 最快，
`hybrid` 只增加少量查询延迟并提高指标。若系统能接受约 488 ms 的 warm
rerank 查询延迟，reranker 值得用于精度优先场景；低延迟场景可选择 hybrid。

For PDF parser comparison, run
`.venv/bin/python scripts/compare_pdf_loaders.py path/to/paper.pdf` and retain
the measured success, page count, character count, and latency per engine. For
embedding comparison, run
`.venv/bin/python scripts/compare_embedding_models.py path/to/paper.pdf --evaluation path/to/qa.jsonl`.
Neither script downloads or commits results unless explicitly invoked with an
output path.
