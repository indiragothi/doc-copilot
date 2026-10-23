"""Embeddings through OpenRouter's OpenAI-compatible API."""

import math

from openai import OpenAI

from app.config import settings

# The SDK retries 429s and 5xx responses with exponential backoff.
_client = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
    max_retries=6,
)


def embed_texts(texts: list[str]) -> list[list[float]]:
    response = _client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
        encoding_format="float",
    )
    vectors = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
    return [fit_dimensions(vector) for vector in vectors]


def fit_dimensions(vector: list[float]) -> list[float]:
    """Return exactly `embedding_dimensions` numbers.

    These are Matryoshka models: keeping the first N values and rescaling to unit length
    is the supported way to shrink them, in case the API ignores the `dimensions` request.
    """
    size = settings.embedding_dimensions
    if len(vector) < size:
        raise ValueError(f"Embedding has {len(vector)} dimensions, expected {size}")
    if len(vector) == size:
        return vector
    head = vector[:size]
    norm = math.sqrt(sum(value * value for value in head))
    return [value / norm for value in head]
