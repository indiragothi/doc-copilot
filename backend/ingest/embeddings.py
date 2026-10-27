"""Chunk embeddings through NVIDIA's OpenAI-compatible API."""

from openai import OpenAI

from app.config import settings
from app.retrieval.embeddings import fit_dimensions

# The SDK retries 429s and 5xx responses with exponential backoff.
_client = OpenAI(
    api_key=settings.nvidia_api_key,
    base_url=settings.nvidia_base_url,
    max_retries=6,
)


def embed_texts(texts: list[str]) -> list[list[float]]:
    # Chunks are "passages"; search queries use input_type "query" (app/retrieval/embeddings.py).
    response = _client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
        encoding_format="float",
        extra_body={"input_type": "passage"},
    )
    vectors = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
    return [fit_dimensions(vector) for vector in vectors]
