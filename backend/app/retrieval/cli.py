"""Try retrieval from the terminal. Each run embeds the query (one embedding request).

Run from backend/:
  uv run python -m app.retrieval.cli "How did Apple's revenue mix change?" --ticker AAPL
"""

import argparse
import asyncio

from app.database.engine import create_engine
from app.retrieval.models import SearchFilters
from app.retrieval.retriever import DocumentRetriever


async def run(query: str, filters: SearchFilters, top_k: int) -> None:
    engine = create_engine()
    try:
        passages = await DocumentRetriever(engine).search(
            query, top_k=top_k, filters=filters
        )
    finally:
        await engine.dispose()
    for rank, passage in enumerate(passages, start=1):
        print(
            f"{rank}. {passage.ticker} {passage.form_type} FY{passage.fiscal_year} "
            f"| {passage.section} | chunk {passage.chunk_index} | score {passage.score:.4f}"
        )
        print(f"   {passage.content[:200]!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--ticker")
    parser.add_argument("--year", type=int)
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()
    filters = SearchFilters(ticker=args.ticker, fiscal_year=args.year)
    # psycopg's async mode can't use Windows' default Proactor event loop.
    asyncio.run(
        run(args.query, filters, args.top_k), loop_factory=asyncio.SelectorEventLoop
    )


if __name__ == "__main__":
    main()
