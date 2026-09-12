# Retrieval experiment

## Scope

M4 exposes and compares three retrieval modes:

1. `vector`: configurable Top-K vector retrieval;
2. `hybrid`: vector retrieval + independent BM25 + hand-written RRF;
3. `hybrid_rerank`: hybrid candidates + configurable bge reranker.

The RRF implementation is maintained in `src/backend/retrieval/rrf.py` and is
not delegated to a framework.

## Evaluation input

Provide a JSONL file with one real evaluation item per line:

```json
{"question": "What is the main method?", "relevant_chunk_ids": ["doc-id:recursive:0"]}
```

`relevant_chunk_ids` must refer to real chunks produced by the indexed corpus.

## Reproducible command

```bash
.venv/bin/python scripts/evaluate_retrieval.py data/samples/paper.pdf --evaluation data/samples/retrieval.jsonl --output /tmp/retrieval-results.json
```

The script computes Hit@5 and MRR independently for all three modes and writes
the observed values as JSON. It loads the configured embedding model only when
the script is explicitly run.

## Current record

No real retrieval evaluation set is present in the repository, so no Hit@5 or
MRR values are recorded here. Running the command with a real corpus and QA set
is required before adding numeric results.
