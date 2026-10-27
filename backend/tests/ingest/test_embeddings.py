import asyncio
import math
from types import SimpleNamespace

import pytest

from app.config import settings
from app.retrieval import embeddings as query_embeddings
from app.retrieval.embeddings import fit_dimensions
from ingest import embeddings as ingest_embeddings


def test_exact_size_vector_is_returned_unchanged():
    vector = [0.1] * settings.embedding_dimensions

    assert fit_dimensions(vector) == vector


def test_longer_vector_is_truncated_and_renormalized():
    vector = [1.0] * (settings.embedding_dimensions * 4)

    fitted = fit_dimensions(vector)

    assert len(fitted) == settings.embedding_dimensions
    assert math.isclose(math.sqrt(sum(v * v for v in fitted)), 1.0)


def test_shorter_vector_is_rejected():
    with pytest.raises(ValueError, match="dimensions"):
        fit_dimensions([0.1] * (settings.embedding_dimensions - 1))


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        data = [
            SimpleNamespace(index=i, embedding=[0.1] * settings.embedding_dimensions)
            for i, _ in enumerate(kwargs["input"])
        ]
        return SimpleNamespace(data=data)


def test_chunks_are_embedded_as_passages(monkeypatch):
    fake = FakeEmbeddings()
    monkeypatch.setattr(ingest_embeddings, "_client", SimpleNamespace(embeddings=fake))

    vectors = ingest_embeddings.embed_texts(["a", "b"])

    assert len(vectors) == 2
    assert fake.calls[0]["extra_body"] == {"input_type": "passage"}


def test_queries_are_embedded_as_queries(monkeypatch):
    fake = FakeEmbeddings()

    async def create(**kwargs):
        return fake.create(**{**kwargs, "input": [kwargs["input"]]})

    monkeypatch.setattr(
        query_embeddings,
        "_client",
        SimpleNamespace(embeddings=SimpleNamespace(create=create)),
    )

    vector = asyncio.run(query_embeddings.embed_query("supplier risk"))

    assert len(vector) == settings.embedding_dimensions
    assert fake.calls[0]["extra_body"] == {"input_type": "query"}
