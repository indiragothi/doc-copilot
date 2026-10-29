import asyncio
from datetime import date
from uuid import uuid4

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.assistant.outputs import Citation, GroundedAnswer
from app.grounding.judge import MAX_PASSAGE_CHARS, judge, judge_answer
from app.retrieval.models import SourcePassage

CONTENT = (
    "Services net sales were $96.2 billion in 2025. Mac net sales were $33.7 billion."
)


def make_passage(content: str = CONTENT) -> SourcePassage:
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
        content=content,
    )


def make_answer(passage: SourcePassage) -> GroundedAnswer:
    return GroundedAnswer(
        answer="Services grew to $96.2 billion [1].",
        citations=[
            Citation(
                marker=1,
                chunk_id=passage.chunk_id,
                quote="Services net sales were $96.2 billion",
            )
        ],
    )


def judged(passage: SourcePassage, verdict: dict, seen: list | None = None):
    def respond(messages, info):
        if seen is not None:
            seen.append(str(messages))
        return ModelResponse(parts=[ToolCallPart("final_result", verdict)])

    async def go():
        with judge.override(model=FunctionModel(respond)):
            return await judge_answer(make_answer(passage), {passage.chunk_id: passage})

    return asyncio.run(go())


def test_judge_sees_the_answer_the_quote_and_the_whole_cited_passage():
    passage = make_passage()
    seen: list[str] = []

    judged(passage, {"unsupported": []}, seen)

    [prompt] = seen
    assert "Services grew to $96.2 billion [1]." in prompt
    assert "Quote: Services net sales were $96.2 billion" in prompt
    # The rest of the chunk, beyond the quote, is shown too.
    assert "Mac net sales were $33.7 billion" in prompt
    assert "AAPL 10-K FY2025, Item 7." in prompt


def test_long_passages_are_cut_before_they_reach_the_judge():
    passage = make_passage("x" * MAX_PASSAGE_CHARS + "TAIL")
    seen: list[str] = []

    judged(passage, {"unsupported": []}, seen)

    assert "TAIL" not in seen[0]


def test_unsupported_claims_come_back_with_marker_and_reason():
    passage = make_passage()
    claim = {
        "marker": 1,
        "claim": "Services grew to $96.2 billion",
        "reason": "The passage gives the level, not growth.",
    }

    result = judged(passage, {"unsupported": [claim]})

    assert [c.model_dump() for c in result.output.unsupported] == [claim]


def test_no_unsupported_claims_is_an_empty_list():
    result = judged(make_passage(), {"unsupported": []})

    assert result.output.unsupported == []
