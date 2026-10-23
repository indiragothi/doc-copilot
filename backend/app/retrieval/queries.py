"""SQL for hybrid retrieval: semantic and keyword search return ranked chunk ids only."""

import re
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database.models import DocumentChunk, SourceDocument
from app.retrieval.models import SearchFilters, SourcePassage


def build_tsquery(text: str) -> str:
    """OR together the words of a question.

    `websearch_to_tsquery` ANDs every term, which matches nothing for a natural-language
    question. Only word characters survive, so the result is always valid tsquery syntax.
    """
    words = dict.fromkeys(re.findall(r"[^\W_]+", text.lower()))
    return " | ".join(words)


def _apply_filters(statement: Select, filters: SearchFilters) -> Select:
    statement = statement.join(
        SourceDocument, SourceDocument.id == DocumentChunk.document_id
    )
    if filters.ticker:
        statement = statement.where(SourceDocument.ticker == filters.ticker)
    if filters.fiscal_year:
        statement = statement.where(SourceDocument.fiscal_year == filters.fiscal_year)
    if filters.form_type:
        statement = statement.where(SourceDocument.form_type == filters.form_type)
    return statement


def semantic_statement(
    embedding: list[float], limit: int, filters: SearchFilters
) -> Select:
    statement = select(DocumentChunk.id).order_by(
        DocumentChunk.embedding.cosine_distance(embedding), DocumentChunk.id
    )
    return _apply_filters(statement, filters).limit(limit)


def keyword_statement(tsquery: str, limit: int, filters: SearchFilters) -> Select:
    query = func.to_tsquery("english", tsquery)
    statement = (
        select(DocumentChunk.id)
        .where(DocumentChunk.search_vector.op("@@")(query))
        .order_by(
            func.ts_rank_cd(DocumentChunk.search_vector, query).desc(),
            DocumentChunk.id,
        )
    )
    return _apply_filters(statement, filters).limit(limit)


async def semantic_search(
    connection: AsyncConnection,
    embedding: list[float],
    limit: int,
    filters: SearchFilters,
) -> list[UUID]:
    result = await connection.execute(semantic_statement(embedding, limit, filters))
    return list(result.scalars())


async def keyword_search(
    connection: AsyncConnection, query: str, limit: int, filters: SearchFilters
) -> list[UUID]:
    tsquery = build_tsquery(query)
    if not tsquery:
        return []
    result = await connection.execute(keyword_statement(tsquery, limit, filters))
    return list(result.scalars())


async def fetch_passages(
    connection: AsyncConnection, chunk_ids: list[UUID]
) -> dict[UUID, SourcePassage]:
    statement = select(
        DocumentChunk.id,
        DocumentChunk.document_id,
        DocumentChunk.chunk_index,
        SourceDocument.ticker,
        SourceDocument.form_type,
        SourceDocument.fiscal_year,
        SourceDocument.filing_date,
        DocumentChunk.section,
        DocumentChunk.page,
        DocumentChunk.content,
    ).join(SourceDocument, SourceDocument.id == DocumentChunk.document_id)
    rows = (
        await connection.execute(statement.where(DocumentChunk.id.in_(chunk_ids)))
    ).all()
    return {
        row.id: SourcePassage(
            chunk_id=row.id,
            document_id=row.document_id,
            chunk_index=row.chunk_index,
            ticker=row.ticker,
            form_type=row.form_type,
            fiscal_year=row.fiscal_year,
            filing_date=row.filing_date,
            section=row.section,
            page=row.page,
            content=row.content,
        )
        for row in rows
    }


async def fetch_neighbors(
    connection: AsyncConnection, passages: list[SourcePassage], window: int
) -> dict[UUID, dict[str, list[str]]]:
    """Chunks within `window` positions of each passage, keyed by the passage's chunk id."""
    if window <= 0 or not passages:
        return {}
    statement = select(
        DocumentChunk.document_id, DocumentChunk.chunk_index, DocumentChunk.content
    ).where(
        or_(
            *(
                and_(
                    DocumentChunk.document_id == passage.document_id,
                    DocumentChunk.chunk_index.between(
                        passage.chunk_index - window, passage.chunk_index + window
                    ),
                    DocumentChunk.chunk_index != passage.chunk_index,
                )
                for passage in passages
            )
        )
    )
    rows = (await connection.execute(statement)).all()
    neighbors = {}
    for passage in passages:
        nearby = sorted(
            (
                row
                for row in rows
                if row.document_id == passage.document_id
                and abs(row.chunk_index - passage.chunk_index) <= window
            ),
            key=lambda row: row.chunk_index,
        )
        index = passage.chunk_index
        neighbors[passage.chunk_id] = {
            "context_before": [r.content for r in nearby if r.chunk_index < index],
            "context_after": [r.content for r in nearby if r.chunk_index > index],
        }
    return neighbors
