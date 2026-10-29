from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.assistant.outputs import GroundedAnswer
from app.config import settings
from app.retrieval.models import SourcePassage

INSTRUCTIONS = (Path(__file__).parent / "judge_instructions.md").read_text(
    encoding="utf-8"
)
# The cited chunk, not just the quote, is shown: a claim may rest on the chunk's other lines,
# and judging against the quote alone would flag claims that are in fact supported.
MAX_PASSAGE_CHARS = 2000


class UnsupportedClaim(BaseModel):
    marker: int
    claim: str
    reason: str


class Verdict(BaseModel):
    unsupported: list[UnsupportedClaim] = []


judge = Agent(
    GoogleModel(
        settings.judge_model,
        provider=GoogleProvider(api_key=settings.gemini_api_key),
    ),
    output_type=Verdict,
    instructions=INSTRUCTIONS,
)


def _prompt(answer: GroundedAnswer, passages: dict[UUID, SourcePassage]) -> str:
    cited = []
    for citation in sorted(answer.citations, key=lambda c: c.marker):
        passage = passages[citation.chunk_id]
        cited.append(
            f"[{citation.marker}] {passage.ticker} {passage.form_type} "
            f"FY{passage.fiscal_year}, {passage.section}\n"
            f"Quote: {citation.quote}\n"
            f"Passage: {passage.content[:MAX_PASSAGE_CHARS]}"
        )
    return f"Answer:\n{answer.answer}\n\nCited passages:\n\n" + "\n\n".join(cited)


async def judge_answer(
    answer: GroundedAnswer, passages: dict[UUID, SourcePassage]
) -> AgentRunResult[Verdict]:
    """Ask the judge model which claims in a validated answer its citations do not support."""
    return await judge.run(_prompt(answer, passages))
