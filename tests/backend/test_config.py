from pathlib import Path

import pytest

from src.backend.config import load_config
from src.backend.exceptions import ConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_load_backend_config() -> None:
    config = load_config(PROJECT_ROOT / "config" / "backend.yaml")

    assert config.chunking.chunk_size == 512
    assert config.chunking.chunk_overlap == 64
    assert config.embedding.model_name == "bge-large-zh"
    assert config.retrieval.enable_rrf is True
    assert config.retrieval.bm25_top_k == 20
    assert config.retrieval.reranker_model_name == "bge-reranker-base"
    assert config.rag.provider == "openai_compatible"
    assert config.rag.max_context_chars == 6000
    assert config.rag.top_k is None
    assert config.rag.low_relevance_threshold == 0.2
    assert config.rag.low_relevance_score_source == "vector"
    assert config.rag.temperature == 0.2
    assert config.cache.max_entries == 256


def test_invalid_backend_config_raises_configuration_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("retrieval:\n  final_top_k: 0\n", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_config(config_path)
