"""Typed loading for the backend YAML configuration."""

from pathlib import Path
from typing import Any, Mapping, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .exceptions import ConfigurationError


class _ConfigModel(BaseModel):
    """Base model that rejects misspelled configuration keys."""

    model_config = ConfigDict(extra="forbid")


class DocumentConfig(_ConfigModel):
    pdf_engine: str = "pymupdf"


class ChunkingConfig(_ConfigModel):
    strategy: str = "recursive"
    chunk_size: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=64, ge=0)


class EmbeddingConfig(_ConfigModel):
    provider: str = "local"
    model_name: str = "bge-large-zh"
    batch_size: int = Field(default=32, gt=0)


class VectorStoreConfig(_ConfigModel):
    type: str = "chroma"


class RetrievalConfig(_ConfigModel):
    vector_top_k: int = Field(default=20, gt=0)
    final_top_k: int = Field(default=5, gt=0)
    enable_bm25: bool = True
    enable_rrf: bool = True
    rrf_k: int = Field(default=60, gt=0)
    enable_reranker: bool = True


class RagConfig(_ConfigModel):
    temperature: float = Field(default=0.2, ge=0)
    top_p: float = Field(default=0.9, gt=0, le=1)
    allow_llm_fallback: bool = True


class CacheConfig(_ConfigModel):
    enabled: bool = True
    similarity_threshold: float = Field(default=0.95, ge=0, le=1)


class BackendConfig(_ConfigModel):
    """Validated representation of ``config/backend.yaml``."""

    document: DocumentConfig = Field(default_factory=DocumentConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    rag: RagConfig = Field(default_factory=RagConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


def load_config(
    path: Optional[Union[str, Path]] = None,
) -> BackendConfig:
    """Load and validate a backend YAML configuration.

    When ``path`` is omitted, the repository-relative
    ``config/backend.yaml`` path is used. No model or external service is
    initialized while loading configuration.
    """

    config_path = Path(path) if path is not None else Path("config/backend.yaml")
    if not config_path.is_file():
        raise ConfigurationError(
            "Backend configuration file not found: " + str(config_path)
        )

    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
    except OSError as exc:
        raise ConfigurationError(
            "Unable to read backend configuration: " + str(config_path)
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            "Invalid YAML in backend configuration: " + str(config_path)
        ) from exc

    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, Mapping):
        raise ConfigurationError("Backend configuration must contain a YAML mapping")

    try:
        return BackendConfig.model_validate(dict(raw_config))
    except ValidationError as exc:
        raise ConfigurationError("Invalid backend configuration values") from exc


__all__ = [
    "BackendConfig",
    "CacheConfig",
    "ChunkingConfig",
    "DocumentConfig",
    "EmbeddingConfig",
    "RagConfig",
    "RetrievalConfig",
    "VectorStoreConfig",
    "load_config",
]
