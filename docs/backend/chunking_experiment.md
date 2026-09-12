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

No real academic-document corpus or gold QA set was supplied, so this file
intentionally contains no fabricated measurements. Run the command above with
the supplied corpus and append the generated JSON observations here.

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
