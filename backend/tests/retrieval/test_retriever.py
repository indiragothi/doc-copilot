import asyncio
from contextlib import asynccontextmanager
from datetime import date
from uuid import uuid4

from app.retrieval import queries
from app.retrieval.models import SearchFilters, SourcePassage
from app.retrieval.retriever import DocumentRetriever


class FakeEngine:
    @asynccontextmanager
    async def connect(self):
        yield object()


def passage(chunk_id) -> SourcePassage:
    return SourcePassage(
        chunk_id=chunk_id,
        document_id=uuid4(),
        chunk_index=3,
        ticker="AAPL",
        form_type="10-K",
        fiscal_year=2025,
        filing_date=date(2025, 10, 31),
        section="Item 7.",
        page=None,
        content=f"chunk {chunk_id}",
    )


def patch_queries(monkeypatch, semantic, keyword, calls=None):
    async def semantic_search(connection, embedding, limit, filters):
        if calls is not None:
            calls.append(("semantic", embedding, limit, filters))
        return semantic

    async def keyword_search(connection, query, limit, filters):
        if calls is not None:
            calls.append(("keyword", query, limit, filters))
        return keyword

    async def fetch_passages(connection, chunk_ids):
        return {chunk_id: passage(chunk_id) for chunk_id in chunk_ids}

    async def fetch_neighbors(connection, passages, window):
        return {
            p.chunk_id: {"context_before": ["before"], "context_after": ["after"]}
            for p in passages
        }

    monkeypatch.setattr(queries, "semantic_search", semantic_search)
    monkeypatch.setattr(queries, "keyword_search", keyword_search)
    monkeypatch.setattr(queries, "fetch_passages", fetch_passages)
    monkeypatch.setattr(queries, "fetch_neighbors", fetch_neighbors)


async def fake_embed(text: str) -> list[float]:
    return [0.5, 0.5]


def retriever() -> DocumentRetriever:
    return DocumentRetriever(FakeEngine(), embed=fake_embed)


def test_search_fuses_both_rankings_and_attaches_context(monkeypatch):
    a, b, c = uuid4(), uuid4(), uuid4()
    patch_queries(monkeypatch, semantic=[a, b], keyword=[c, b])

    results = asyncio.run(retriever().search("revenue", top_k=2))

    assert [r.chunk_id for r in results] == [b, a]
    assert results[0].score > results[1].score
    assert results[0].context_before == ["before"]
    assert results[0].context_after == ["after"]


def test_search_passes_query_candidate_k_and_filters_to_both_searches(monkeypatch):
    calls = []
    patch_queries(monkeypatch, semantic=[], keyword=[], calls=calls)
    filters = SearchFilters(ticker="AAPL")

    asyncio.run(retriever().search("supplier risk", candidate_k=7, filters=filters))

    assert sorted(calls) == sorted(
        [
            ("semantic", [0.5, 0.5], 7, filters),
            ("keyword", "supplier risk", 7, filters),
        ]
    )


def test_empty_keyword_results_fall_back_to_vector_order(monkeypatch):
    a, b = uuid4(), uuid4()
    patch_queries(monkeypatch, semantic=[a, b], keyword=[])

    results = asyncio.run(retriever().search("the of"))

    assert [r.chunk_id for r in results] == [a, b]


def test_no_hits_returns_empty_list(monkeypatch):
    patch_queries(monkeypatch, semantic=[], keyword=[])

    assert asyncio.run(retriever().search("nothing")) == []


def test_unset_limits_come_from_settings(monkeypatch):
    from app.config import settings

    calls = []
    patch_queries(
        monkeypatch, semantic=[uuid4() for _ in range(5)], keyword=[], calls=calls
    )
    monkeypatch.setattr(settings, "retrieval_top_k", 2)
    monkeypatch.setattr(settings, "retrieval_candidate_k", 9)

    results = asyncio.run(retriever().search("revenue"))

    assert len(results) == 2
    assert {call[2] for call in calls} == {9}


def test_explicit_limits_override_settings(monkeypatch):
    from app.config import settings

    patch_queries(monkeypatch, semantic=[uuid4() for _ in range(5)], keyword=[])
    monkeypatch.setattr(settings, "retrieval_top_k", 2)

    assert len(asyncio.run(retriever().search("revenue", top_k=4))) == 4


def test_read_chunks_keeps_requested_order_and_skips_unknown_ids(monkeypatch):
    a, b, missing = uuid4(), uuid4(), uuid4()

    async def fetch_passages(connection, chunk_ids):
        return {
            chunk_id: passage(chunk_id) for chunk_id in chunk_ids if chunk_id != missing
        }

    monkeypatch.setattr(queries, "fetch_passages", fetch_passages)

    results = asyncio.run(retriever().read_chunks([b, missing, a]))

    assert [r.chunk_id for r in results] == [b, a]
