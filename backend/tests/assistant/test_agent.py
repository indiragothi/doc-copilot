import asyncio
from datetime import date
from uuid import UUID, uuid4

import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.assistant.agent import MAX_SEARCHES_PER_TURN, agent
from app.assistant.deps import DocumentAgentDeps
from app.retrieval.models import SourcePassage

CONTENT = "Services net sales were $96.2 billion in 2025, up 13% from 2024."


class FakeRetriever:
    def __init__(self, passages: list[SourcePassage]) -> None:
        self.passages = passages
        self.filters = None
        self.top_ks = []

    async def search(self, query, *, filters, neighbor_window, top_k=None):
        self.filters = filters
        self.top_ks.append(top_k)
        return [p for p in self.passages if filters.ticker in (None, p.ticker)]

    async def read_chunks(self, chunk_ids):
        return [p for p in self.passages if p.chunk_id in chunk_ids]

    async def read_chunk(self, chunk_id, *, neighbor_window=0):
        return next((p for p in self.passages if p.chunk_id == chunk_id), None)


def make_passage() -> SourcePassage:
    return SourcePassage(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        ticker="AAPL",
        form_type="10-K",
        fiscal_year=2025,
        filing_date=date(2025, 10, 31),
        section="Item 7.",
        page=None,
        content=CONTENT,
    )


def make_deps(passage: SourcePassage) -> DocumentAgentDeps:
    return DocumentAgentDeps(
        user_id=uuid4(), thread_id=uuid4(), retriever=FakeRetriever([passage])
    )


def final(chunk_id: UUID, quote: str) -> ToolCallPart:
    return ToolCallPart(
        "final_result",
        {
            "answer": "Services grew to $96.2 billion [1].",
            "citations": [{"marker": 1, "chunk_id": str(chunk_id), "quote": quote}],
        },
    )


def scripted(*steps: ToolCallPart) -> FunctionModel:
    """A model that plays back one tool call per request."""
    remaining = iter(steps)
    return FunctionModel(lambda messages, info: ModelResponse(parts=[next(remaining)]))


def run(model: FunctionModel, deps: DocumentAgentDeps):
    async def go():
        with agent.override(model=model):
            return await agent.run("How did Services revenue change?", deps=deps)

    return asyncio.run(go())


def test_grounded_answer_passes_through():
    passage = make_passage()
    deps = make_deps(passage)
    model = scripted(
        ToolCallPart(
            "search_filings", {"query": "services revenue", "tickers": ["aapl"]}
        ),
        final(passage.chunk_id, "Services net sales were $96.2 billion"),
    )

    result = run(model, deps)

    assert result.output.citations[0].chunk_id == passage.chunk_id
    assert deps.retrieved == {passage.chunk_id: passage}
    assert deps.retriever.filters.ticker == "AAPL"


def test_citing_a_chunk_that_was_never_retrieved_is_retried_then_fails():
    passage = make_passage()
    bad = final(uuid4(), "Services net sales were $96.2 billion")
    model = scripted(
        ToolCallPart("search_filings", {"query": "services"}), bad, bad, bad
    )

    with pytest.raises(UnexpectedModelBehavior):
        run(model, make_deps(passage))


def test_corrected_answer_after_a_violation_is_accepted():
    passage = make_passage()
    model = scripted(
        ToolCallPart("search_filings", {"query": "services"}),
        final(passage.chunk_id, "Services net sales were $120 billion"),
        final(passage.chunk_id, "Services net sales were $96.2 billion"),
    )

    result = run(model, make_deps(passage))

    assert result.output.citations[0].quote.startswith("Services net sales were $96.2")


def test_read_chunk_makes_a_chunk_citable():
    passage = make_passage()
    model = scripted(
        ToolCallPart("read_chunk", {"chunk_id": str(passage.chunk_id)}),
        final(passage.chunk_id, "up 13% from 2024"),
    )

    result = run(model, make_deps(passage))

    assert result.output.citations[0].chunk_id == passage.chunk_id


def test_read_chunks_fetches_several_chunks_in_one_call():
    passage = make_passage()
    deps = make_deps(passage)
    model = scripted(
        ToolCallPart("read_chunks", {"chunk_ids": [str(passage.chunk_id)]}),
        final(passage.chunk_id, "up 13% from 2024"),
    )

    result = run(model, deps)

    assert deps.retrieved == {passage.chunk_id: passage}
    assert result.output.citations[0].chunk_id == passage.chunk_id


def test_read_chunks_with_only_unknown_ids_is_retried_then_fails():
    passage = make_passage()
    unknown = ToolCallPart("read_chunks", {"chunk_ids": [str(uuid4())]})
    model = scripted(unknown, unknown, unknown, unknown)

    with pytest.raises(UnexpectedModelBehavior):
        run(model, make_deps(passage))


def test_search_across_companies_takes_a_few_passages_from_each_and_notes_the_missing():
    passage = make_passage()
    deps = make_deps(passage)
    model = scripted(
        ToolCallPart(
            "search_filings", {"query": "services revenue", "tickers": ["aapl", "msft"]}
        ),
        final(passage.chunk_id, "Services net sales were $96.2 billion"),
    )

    run(model, deps)

    assert deps.retriever.top_ks == [4, 4]
    assert deps.retrieved == {passage.chunk_id: passage}


def test_searches_past_the_limit_get_a_note_instead_of_results():
    passage = make_passage()
    deps = make_deps(passage)
    search = ToolCallPart("search_filings", {"query": "services revenue"})
    model = scripted(
        *[search] * (MAX_SEARCHES_PER_TURN + 1),
        final(passage.chunk_id, "Services net sales were $96.2 billion"),
    )

    run(model, deps)

    assert len(deps.retriever.top_ks) == MAX_SEARCHES_PER_TURN
