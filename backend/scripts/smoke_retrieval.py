"""Print the top retrieval hits for client-brief-style questions.

Each query makes one embedding request. Run from backend/:
  uv run python -m scripts.smoke_retrieval
"""

import asyncio

from app.retrieval.cli import run
from app.retrieval.models import SearchFilters

# Apple only: it is the one company ingested in this build.
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
