from pathlib import Path
from uuid import UUID

from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.assistant.progress import tool_timer
from app.config import settings
from app.grounding.validator import validate_answer
from app.retrieval.models import SearchFilters, SourcePassage

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")
MAX_SURROUNDING_CHUNKS = 3
MAX_BATCH_CHUNKS = 10
# One corrective retry when validation fails; after that the turn fails closed.
OUTPUT_RETRIES = 1

agent = Agent(
    OpenAIChatModel(
        settings.llm_model,
        provider=OpenAIProvider(
            openai_client=AsyncOpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
            )
        ),
    ),
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    instructions=INSTRUCTIONS,
    retries={"tools": 2, "output": OUTPUT_RETRIES},
)


def _render(passage: SourcePassage, *, with_context: bool = False) -> dict:
    rendered = {
        "chunk_id": str(passage.chunk_id),
        "ticker": passage.ticker,
        "form_type": passage.form_type,
        "fiscal_year": passage.fiscal_year,
        "filing_date": passage.filing_date.isoformat(),
        "section": passage.section,
        "page": passage.page,
        "content": passage.content,
    }
    if with_context:
        # Plain text for understanding only; it has no chunk_id and cannot be cited.
        rendered["context_before"] = passage.context_before
        rendered["context_after"] = passage.context_after
    return rendered


def _remember(
    ctx: RunContext[DocumentAgentDeps], passages: list[SourcePassage]
) -> None:
    for passage in passages:
        ctx.deps.retrieved[passage.chunk_id] = passage


@agent.tool
async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    form_type: str | None = None,
) -> list[dict]:
    """Search the filings for passages relevant to the query.

    Optionally narrow by company ticker (e.g. "AAPL"), fiscal year or form type (e.g. "10-K").
    Returns an empty list when nothing matches.
    """
    filters = SearchFilters(
        ticker=ticker.upper() if ticker else None,
        fiscal_year=fiscal_year,
        form_type=form_type,
    )
    with tool_timer(
        "search_filings", query=query, filters=filters.model_dump()
    ) as done:
        passages = await ctx.deps.retriever.search(
            query, filters=filters, neighbor_window=0
        )
        done(results=len(passages))
    _remember(ctx, passages)
    return [_render(passage) for passage in passages]


@agent.tool
async def read_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_ids: list[UUID]
) -> list[dict]:
    """Read several passages in full by chunk_id, in one call. Prefer this to repeated read_chunk."""
    wanted = chunk_ids[:MAX_BATCH_CHUNKS]
    with tool_timer("read_chunks", requested=len(wanted)) as done:
        passages = await ctx.deps.retriever.read_chunks(wanted)
        done(results=len(passages))
    if not passages:
        raise ModelRetry(
            "None of those chunk ids exist. Use chunk_ids from search_filings."
        )
    _remember(ctx, passages)
    return [_render(passage) for passage in passages]


@agent.tool
async def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: UUID) -> dict:
    """Read one passage in full by its chunk_id."""
    with tool_timer("read_chunk") as done:
        passage = await ctx.deps.retriever.read_chunk(chunk_id)
        done(found=passage is not None)
    if passage is None:
        raise ModelRetry(
            f"No chunk with id {chunk_id}. Use a chunk_id from search_filings."
        )
    _remember(ctx, [passage])
    return _render(passage)


@agent.tool
async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_id: UUID, window: int = 1
) -> dict:
    """Read a passage together with the text of the chunks just before and after it."""
    with tool_timer("read_surrounding_chunks") as done:
        passage = await ctx.deps.retriever.read_chunk(
            chunk_id, neighbor_window=min(max(window, 1), MAX_SURROUNDING_CHUNKS)
        )
        done(found=passage is not None)
    if passage is None:
        raise ModelRetry(
            f"No chunk with id {chunk_id}. Use a chunk_id from search_filings."
        )
    _remember(ctx, [passage])
    return _render(passage, with_context=True)


@agent.output_validator
async def enforce_grounding(
    ctx: RunContext[DocumentAgentDeps], answer: GroundedAnswer
) -> GroundedAnswer:
    violations = validate_answer(answer, ctx.deps.retrieved)
    if violations:
        raise ModelRetry(
            "Your answer failed grounding checks. Fix every item and answer again:\n- "
            + "\n- ".join(violations)
        )
    return answer
