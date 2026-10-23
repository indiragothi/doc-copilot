import math

import pytest

from app.config import settings
from ingest.embeddings import fit_dimensions


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
