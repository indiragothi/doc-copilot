"""Query embeddings through NVIDIA's OpenAI-compatible API."""

import math

from openai import AsyncOpenAI

from app.config import settings

_client = AsyncOpenAI(
    api_key=settings.nvidia_api_key,
    base_url=settings.nvidia_base_url,
    max_retries=6,
)


async def embed_query(text: str) -> list[float]:
    # The model is asymmetric: queries and chunks are embedded with different input types.
    response = await _client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
        encoding_format="float",
        extra_body={"input_type": "query"},
    )
    return fit_dimensions(response.data[0].embedding)


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
