import asyncio
from uuid import uuid4

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from test_agent import FakeRetriever, final, make_passage

from app.assistant.agent import agent
from app.chat.orchestrator import FAILURE_MESSAGE, run_turn


def turn(model, passage):
    async def go():
        with agent.override(model=model):
            return await run_turn(
                FakeRetriever([passage]),
                user_id=uuid4(),
                thread_id=uuid4(),
                question="Services revenue?",
                history=[],
            )

    return asyncio.run(go())


def scripted(*steps):
    remaining = iter(steps)
    return FunctionModel(lambda messages, info: ModelResponse(parts=[next(remaining)]))


def test_grounded_answer_is_joined_with_its_source_passage():
    passage = make_passage()
    model = scripted(
        ToolCallPart("search_filings", {"query": "services"}),
        final(passage.chunk_id, "Services net sales were $96.2 billion"),
    )

    answer = turn(model, passage)

    [citation] = answer.citations
    assert answer.text == "Services grew to $96.2 billion [1]."
    assert citation.chunk_id == passage.chunk_id
    assert citation.excerpt == passage.content
    assert (citation.ticker, citation.fiscal_year) == ("AAPL", 2025)


def test_ungrounded_answer_fails_closed_with_the_fixed_message():
    passage = make_passage()
    bad = final(uuid4(), "Services net sales were $96.2 billion")
    model = scripted(ToolCallPart("search_filings", {"query": "services"}), bad, bad)

    answer = turn(model, passage)

    assert answer.text == FAILURE_MESSAGE
    assert answer.citations == []


def test_insufficient_evidence_answer_needs_no_citations():
    passage = make_passage()
    model = scripted(
        ToolCallPart("search_filings", {"query": "amazon aws", "ticker": "AMZN"}),
        ToolCallPart(
            "final_result",
            {
                "answer": "The filings do not cover Amazon.",
                "insufficient_evidence": True,
            },
        ),
    )

    answer = turn(model, passage)

    assert answer.text == "The filings do not cover Amazon."
    assert answer.citations == []
