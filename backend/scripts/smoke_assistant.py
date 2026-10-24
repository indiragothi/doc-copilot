"""Run one question through the full assistant turn and print the grounded answer.

The turn is the same code path as POST /chat/stream, minus auth and persistence.
Tool timings and token usage are printed as structlog events while it runs.
Run from backend/:
  uv run python -m scripts.smoke_assistant [query-key]
"""

import asyncio
import sys
from uuid import uuid4

from app.chat.orchestrator import FAILURE_MESSAGE, run_turn
from app.database.engine import create_engine
from app.retrieval.retriever import DocumentRetriever

QUERIES = {
    "apple-mix": (
        "Across Apple's 2021-2025 10-Ks, how did the revenue mix between iPhone, "
        "Services, Mac, iPad, and Wearables change, and which category contributed "
        "most to any mix shift?"
    ),
    "apple-suppliers": (
        "What do Apple's filings say about supplier concentration or dependence on "
        "third-party manufacturing, and did the wording become more or less urgent?"
    ),
    # Only Apple is ingested, so this must come back as "not enough evidence".
    "amazon-aws": (
        "For Amazon, compare AWS operating income and margin against North America "
        "and International from 2021-2025."
    ),
    "q10-refusal": (
        "Do the filings prove that generative AI improved margins for any of these "
        "companies?"
    ),
    "underspecified": "How did they do?",
}
DEFAULT_KEY = "apple-mix"


async def main(key: str) -> None:
    query = QUERIES[key]
    print(f"Query [{key}]: {query}\n")
    engine = create_engine()
    try:
        answer = await run_turn(
            DocumentRetriever(engine),
            user_id=uuid4(),
            thread_id=uuid4(),
            question=query,
            history=[],
        )
    finally:
        await engine.dispose()

    print("\n--- Answer ---")
    print(answer.text)
    print(f"\ngrounded: {answer.text != FAILURE_MESSAGE}")
    print(f"citations: {len(answer.citations)}")
    for citation in answer.citations:
        print(
            f"[{citation.marker}] {citation.ticker} {citation.form_type} "
            f"FY{citation.fiscal_year} | {citation.section} | page {citation.page}"
        )
        print(f"    quote: {citation.quote!r}")
        print(f"    excerpt: {citation.excerpt[:200]!r}")


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_KEY
    if key not in QUERIES:
        sys.exit(f"Unknown query key {key!r}. Choose one of: {', '.join(QUERIES)}")
    try:
        # psycopg's async mode can't use Windows' default Proactor event loop.
        asyncio.run(main(key), loop_factory=asyncio.SelectorEventLoop)
    except KeyboardInterrupt:
        sys.exit(130)
