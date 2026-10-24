import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings
from app.retrieval import queries
from app.retrieval.embeddings import embed_query
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import SearchFilters, SourcePassage


class DocumentRetriever:
    """Hybrid search: pgvector and full-text rankings fused with RRF in Python."""

    def __init__(
        self,
        engine: AsyncEngine,
        embed: Callable[[str], Awaitable[list[float]]] = embed_query,
    ) -> None:
        self._engine = engine
        self._embed = embed

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        candidate_k: int | None = None,
        filters: SearchFilters | None = None,
        neighbor_window: int | None = None,
    ) -> list[SourcePassage]:
        """Unset limits fall back to the `retrieval_*` settings."""
        if top_k is None:
            top_k = settings.retrieval_top_k
        if candidate_k is None:
            candidate_k = settings.retrieval_candidate_k
        if neighbor_window is None:
            neighbor_window = settings.retrieval_neighbor_radius
        filters = filters or SearchFilters()
        embedding = await self._embed(query)
        semantic, keyword = await asyncio.gather(
            self._semantic(embedding, candidate_k, filters),
            self._keyword(query, candidate_k, filters),
        )
        fused = reciprocal_rank_fusion([semantic, keyword], k=settings.retrieval_rrf_k)[
            :top_k
        ]
        if not fused:
            return []

        async with self._engine.connect() as connection:
            passages = await queries.fetch_passages(
                connection, [chunk_id for chunk_id, _ in fused]
            )
            context = await queries.fetch_neighbors(
                connection, list(passages.values()), neighbor_window
            )
        return [
            passages[chunk_id].model_copy(
                update={"score": score, **context.get(chunk_id, {})}
            )
            for chunk_id, score in fused
        ]

    async def read_chunks(self, chunk_ids: list[UUID]) -> list[SourcePassage]:
        """Several chunks in one query, in the order asked; unknown ids are skipped."""
        async with self._engine.connect() as connection:
            passages = await queries.fetch_passages(connection, chunk_ids)
        return [passages[chunk_id] for chunk_id in chunk_ids if chunk_id in passages]

    async def read_chunk(
        self, chunk_id: UUID, *, neighbor_window: int = 0
    ) -> SourcePassage | None:
        async with self._engine.connect() as connection:
            passages = await queries.fetch_passages(connection, [chunk_id])
            if chunk_id not in passages:
                return None
            context = await queries.fetch_neighbors(
                connection, [passages[chunk_id]], neighbor_window
            )
        return passages[chunk_id].model_copy(update=context.get(chunk_id, {}))

    async def _semantic(
        self, embedding: list[float], limit: int, filters: SearchFilters
    ) -> list[UUID]:
        async with self._engine.connect() as connection:
            return await queries.semantic_search(connection, embedding, limit, filters)

    async def _keyword(
        self, query: str, limit: int, filters: SearchFilters
    ) -> list[UUID]:
        async with self._engine.connect() as connection:
            return await queries.keyword_search(connection, query, limit, filters)
