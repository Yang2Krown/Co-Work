# Chunking experiment

## Scope

M2 compares four transparent, configurable strategies:

- `fixed`: fixed character windows with overlap;
- `recursive`: paragraph, line, sentence, whitespace, then character boundaries;
- `semantic`: sentence-aware packing;
- `structure`: paragraph-aware packing.

All strategies return the shared `Chunk` model and retain `document_id`,
`file_name`, `page_number`, `page_numbers`, source path, strategy, and character
offsets. PDF page metadata is used to identify every page touched by a chunk;
`page_number` is the first touched page and is `null` when no page is available.

## Reproducible command

Run from the repository root with real sample documents:

```bash
.venv/bin/python scripts/evaluate_chunking.py data/samples/*.pdf data/samples/*.docx data/samples/*.txt data/samples/*.md --output /tmp/chunking-results.json
```

The script measures chunk count and character-length statistics for chunk sizes
256, 512, and 1024 by default. To close the retrieval loop with a real QA set,
add `--evaluation path/to/qa.jsonl --embedding-model m3e-base`. The QA set must
contain `question` and either real `relevant_chunk_ids` or stable
`relevant_document_ids`, optionally restricted by `relevant_page_numbers`.
The script then builds an in-memory vector index for every strategy/size and
reports only measured vector Hit@5 and MRR. `m3e-base` and `bge-large-zh` can be
run separately for a model sensitivity check.

## Current record

以下数据均来自真实实验运行，不是预填或推测值。

- 数据集：5 篇 Transformer 论文 PDF
- QA：20 条人工核验问题
- Python：3.11.16
- Embedding：`m3e-base` (`moka-ai/m3e-base`)
- Vector store：`InMemoryVectorStore`
- Retrieval mode：`vector`
- Overlap：64；Top-K：5
- 实验日期：2026-09-13

| strategy | chunk size | chunks | avg length | Hit@5 | MRR | index build (ms) | avg query (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed | 256 | 2425 | 255.77 | 0.8000 | 0.4717 | 45750.07 | 29.06 |
| fixed | 512 | 1040 | 511.15 | 0.5500 | 0.4375 | 37671.99 | 14.27 |
| fixed | 1024 | 487 | 1018.89 | 0.7000 | 0.4767 | 33829.55 | 13.26 |
| recursive | 256 | 2902 | 224.22 | 0.7000 | 0.4392 | 53242.20 | 15.31 |
| recursive | 512 | 1118 | 479.95 | 0.7000 | 0.4017 | 52488.52 | 15.58 |
| recursive | 1024 | 505 | 984.85 | 0.7500 | 0.4492 | 46577.88 | 16.63 |
| structure | 256 | 2435 | 252.17 | 0.7500 | 0.5333 | 59199.71 | 35.33 |
| structure | 512 | 1079 | 488.70 | 0.7000 | 0.5433 | 56578.31 | 23.87 |
| structure | 1024 | 532 | 925.37 | 0.7500 | 0.5283 | 49266.52 | 17.06 |

本轮按单一指标看，`fixed/256` 的 Hit@5 最高（0.8000），
`structure/512` 的 MRR 最高（0.5433）。后续 retrieval 对比固定
`structure/512`，因为它在排序质量上最好，同时保留了可管理的 chunk 数量；
这不是对未测试配置的推断。`structure/256` 的索引构建和查询都更慢，体现了
“结构边界带来更好排序但成本更高”的权衡；整体结果也说明 strategy 与尺寸需
同时记录，不能只比较 strategy 名称。

指标定义：Hit@5 表示前 5 个结果中至少命中一个 gold document/page；MRR
是第一个命中结果排名的倒数的平均值。gold 使用
`relevant_document_ids` 与 `relevant_page_numbers`，没有跨策略使用 chunk ID。

## Academic PDF considerations and known limitations

- **Two-column papers:** parser reading order depends on the selected PDF engine;
  chunking cannot recover layout that the loader did not preserve.
- **Cross-page text:** page-aware metadata is retained, and a chunk crossing a
  page boundary records all touched pages. Sentence or paragraph boundaries may
  still span a page separator.
- **Tables:** table extraction quality is parser-dependent; table cells may be
  emitted in reading order or as plain text.
- **Mathematical formulas:** formulas are retained only as text returned by the
  PDF parser and may be incomplete or reordered.
- **Headings and section boundaries:** paragraph and recursive strategies use
  textual line/paragraph boundaries; they do not perform full document-layout
  analysis.
