"""Print the top retrieval hits for client-brief-style questions.

Each query makes one embedding request. Run from backend/:
  uv run python -m scripts.smoke_retrieval
"""

import asyncio

from app.retrieval.cli import run
from app.retrieval.models import SearchFilters

SMOKE_QUERIES: list[tuple[str, SearchFilters]] = [
    (
        "How did Apple's revenue mix between iPhone, Services, Mac, iPad and Wearables change?",
        SearchFilters(ticker="AAPL", form_type="10-K"),
    ),
    (
        "Supplier concentration and dependence on third-party manufacturing",
        SearchFilters(ticker="AAPL", form_type="10-K"),
    ),
    (
        "Geographic revenue exposure by segment",
        SearchFilters(ticker="AAPL", form_type="10-K", fiscal_year=2025),
    ),
    (
        "Azure and cloud revenue growth",
        SearchFilters(ticker="MSFT", form_type="10-K"),
    ),
    (
        "Data center revenue and customer concentration",
        SearchFilters(ticker="NVDA", form_type="10-K"),
    ),
    (
        "AWS segment operating income",
        SearchFilters(ticker="AMZN", form_type="10-K"),
    ),
    (
        "Google Cloud revenue and operating income",
        SearchFilters(ticker="GOOGL", form_type="10-K"),
    ),
    ("Which companies describe export control risks for AI chips?", SearchFilters()),
]
TOP_K = 5


async def main() -> None:
    for query, filters in SMOKE_QUERIES:
        print("\n" + "=" * 80)
        print(f"Query: {query}")
        print(f"Filters: {filters.model_dump_json()}")
        await run(query, filters, TOP_K)


if __name__ == "__main__":
    # psycopg's async mode can't use Windows' default Proactor event loop.
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
