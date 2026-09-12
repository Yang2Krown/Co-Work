import numpy as np

import pytest

from src.backend.embeddings import EmbeddingService
from src.backend.exceptions import EmbeddingError


class FakeEmbeddingModel:
    def encode(self, texts, **kwargs):
        return np.asarray(
            [[float(len(text)), float(index + 1)] for index, text in enumerate(texts)],
            dtype=np.float32,
        )


def test_embedding_service_supports_model_aliases_without_download() -> None:
    service = EmbeddingService(
        model_name="m3e-base",
        batch_size=2,
        model=FakeEmbeddingModel(),
    )

    vectors = service.embed_documents(["one", "two"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 2
    assert service.resolved_model_name == "moka-ai/m3e-base"
    assert service.last_stats is not None
    assert service.last_stats.item_count == 2
    assert service.last_stats.dimension == 2
    assert service.last_stats.items_per_second > 0


def test_embedding_service_validates_inputs() -> None:
    service = EmbeddingService(model=FakeEmbeddingModel())

    with pytest.raises(EmbeddingError, match="non-empty"):
        service.embed_query("")
    with pytest.raises(EmbeddingError, match="strings"):
        service.embed_documents(["ok", 1])

