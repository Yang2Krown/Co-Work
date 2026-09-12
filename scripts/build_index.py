"""Build or incrementally update the configured vector index."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.config import load_config
from src.backend.embeddings import EmbeddingService
from src.backend.indexing import IncrementalIndex
from src.backend.loaders import ingest_documents
from src.backend.vectorstores import create_vector_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Documents to index")
    parser.add_argument("--config", type=Path, default=Path("config/backend.yaml"))
    args = parser.parse_args()

    config = load_config(args.config)
    batch = ingest_documents(args.paths)
    documents = [item.document for item in batch.items if item.document is not None]
    embedding_service = EmbeddingService(
        model_name=config.embedding.model_name,
        batch_size=config.embedding.batch_size,
        normalize_embeddings=config.embedding.normalize_embeddings,
    )
    vector_store = create_vector_store(
        config.vector_store.type,
        config.vector_store.persist_directory,
        config.vector_store.collection_name,
    )
    index = IncrementalIndex(
        vector_store=vector_store,
        embedding_service=embedding_service,
        chunking_strategy=config.chunking.strategy,
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap,
        vector_top_k=config.retrieval.vector_top_k,
    )
    update = index.index_documents(documents)
    print(
        json.dumps(
            {
                "ingestion": batch.model_dump(),
                "index_update": update.model_dump(),
                "embedding_stats": (
                    embedding_service.last_stats.__dict__
                    if embedding_service.last_stats is not None
                    else None
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not batch.failed_files else 1


if __name__ == "__main__":
    raise SystemExit(main())

