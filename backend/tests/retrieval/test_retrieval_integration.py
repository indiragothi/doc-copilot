"""Real queries against the ingested Apple corpus. Each case spends one embedding request."""

import asyncio

import pytest

from app.database.engine import create_engine
from app.retrieval.models import SearchFilters
from app.retrieval.retriever import DocumentRetriever

pytestmark = pytest.mark.integration

# Client-brief questions the Apple-only corpus can answer, with words the top passages must show.
CASES = [
    (
        "How did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change?",
        ["iphone", "services"],
    ),
    (
        "What do the filings say about supplier concentration or dependence on third-party manufacturing?",
        ["outsourcing", "manufactur"],
    ),
    (
        "What are the most important geographic revenue exposures?",
        ["greater china"],
    ),
]


async def search(question: str):
    engine = create_engine()
    try:
        return await DocumentRetriever(engine).search(
            question, filters=SearchFilters(ticker="AAPL")
        )
    finally:
        await engine.dispose()


@pytest.mark.parametrize(("question", "expected_words"), CASES)
def test_brief_question_returns_relevant_apple_passages(question, expected_words):
    # psycopg's async mode can't use Windows' default Proactor event loop.
    passages = asyncio.run(search(question), loop_factory=asyncio.SelectorEventLoop)

    assert passages
    assert all(p.ticker == "AAPL" for p in passages)
    text = " ".join(p.content.lower() for p in passages)
    for word in expected_words:
        assert word in text
