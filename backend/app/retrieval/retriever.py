import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

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
        top_k: int = 8,
        candidate_k: int = 50,
        filters: SearchFilters | None = None,
        neighbor_window: int = 1,
    ) -> list[SourcePassage]:
        filters = filters or SearchFilters()
        embedding = await self._embed(query)
        semantic, keyword = await asyncio.gather(
            self._semantic(embedding, candidate_k, filters),
            self._keyword(query, candidate_k, filters),
        )
        fused = reciprocal_rank_fusion([semantic, keyword])[:top_k]
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
