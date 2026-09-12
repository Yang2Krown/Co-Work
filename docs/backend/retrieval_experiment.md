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

No real retrieval evaluation set is present in the repository, so no Hit@5 or
MRR values are recorded here. Running the command with a real corpus and QA set
is required before adding numeric results. The same corpus and QA file should
be evaluated for all three modes, with the configured reranker enabled for
`hybrid_rerank`; record model names, configuration, query count, Hit@5, and MRR
alongside the generated JSON.

For PDF parser comparison, run
`.venv/bin/python scripts/compare_pdf_loaders.py path/to/paper.pdf` and retain
the measured success, page count, character count, and latency per engine. For
embedding comparison, run
`.venv/bin/python scripts/compare_embedding_models.py path/to/paper.pdf --evaluation path/to/qa.jsonl`.
Neither script downloads or commits results unless explicitly invoked with an
output path.
