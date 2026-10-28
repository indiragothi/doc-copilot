import asyncio
from pathlib import Path
from uuid import UUID

from google.genai.types import HttpRetryOptions
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.assistant.progress import tool_timer
from app.config import settings
from app.grounding.validator import validate_answer
from app.retrieval.models import SearchFilters, SourcePassage

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")
MAX_SURROUNDING_CHUNKS = 3
MAX_BATCH_CHUNKS = 10
# Search results carry only the start of each passage: full text for eight passages on every
# search dominated the turn's tokens and latency. `read_chunks` returns the full text.
SEARCH_PASSAGE_CHARS = 500
# A search across several companies returns this many passages per company, so one call
# covers a comparison that would otherwise take a search per company.
PASSAGES_PER_COMPANY = 4
# The model sometimes re-searches the same thing with new wording until the quota is gone;
# past this many searches it is told to answer from what it has.
MAX_SEARCHES_PER_TURN = 6
# Corrective retries when validation fails; after that the turn fails closed. Free-tier models
# often miss by one citation, so a second chance saves most turns.
OUTPUT_RETRIES = 2

agent = Agent(
    # Gemini's OpenAI-compatible endpoint drops the thought signatures Gemini 3 needs for
    # multi-step tool calls, so the native Google client is used instead.
    GoogleModel(
        settings.llm_model,
        provider=GoogleProvider(
            api_key=settings.gemini_api_key,
            # The free tier answers 503 "high demand" in spikes; a retry usually gets through.
            # A 429 (quota) is not retried: the wait is minutes, so the analyst is told at once.
            retry_options=HttpRetryOptions(
                attempts=4, initial_delay=2, max_delay=10, http_status_codes=[503]
            ),
        ),
    ),
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    instructions=INSTRUCTIONS,
    retries={"tools": 2, "output": OUTPUT_RETRIES},
)


def _render(
    passage: SourcePassage, *, with_context: bool = False, max_chars: int | None = None
) -> dict:
    truncated = max_chars is not None and len(passage.content) > max_chars
    rendered = {
        "chunk_id": str(passage.chunk_id),
        "ticker": passage.ticker,
        "form_type": passage.form_type,
        "fiscal_year": passage.fiscal_year,
        "filing_date": passage.filing_date.isoformat(),
        "section": passage.section,
        "page": passage.page,
        "content": passage.content[:max_chars] if truncated else passage.content,
    }
    if truncated:
        rendered["truncated"] = (
            "Start of the passage only; use read_chunks for the full text."
        )
    if with_context:
        # Plain text for understanding only; it has no chunk_id and cannot be cited.
        rendered["context_before"] = passage.context_before
        rendered["context_after"] = passage.context_after
    return rendered


def _describe_search(query: str, filters: SearchFilters, tickers: list[str]) -> str:
    scope = [
        str(value)
        for value in (", ".join(tickers), filters.form_type, filters.fiscal_year)
        if value
    ]
    return " · ".join([*scope, f"“{query}”"])


def _describe_passages(passages: list[SourcePassage]) -> str:
    sections = sorted({p.section for p in passages if p.section})
    return ", ".join(sections) if sections else f"{len(passages)} passages"


def _remember(
    ctx: RunContext[DocumentAgentDeps], passages: list[SourcePassage]
) -> None:
    for passage in passages:
        ctx.deps.retrieved[passage.chunk_id] = passage


@agent.tool
async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    tickers: list[str] | None = None,
    fiscal_year: int | None = None,
    form_type: str | None = None,
) -> list[dict]:
    """Search the filings for passages relevant to the query.

    Optionally narrow by company tickers (e.g. ["AAPL"], or several to compare companies in
    one call), fiscal year or form type (e.g. "10-K"). Returns an empty list when nothing
    matches.
    """
    ctx.deps.searches += 1
    if ctx.deps.searches > MAX_SEARCHES_PER_TURN:
        return [
            {
                "note": "Search limit reached for this question. Answer now from the "
                "passages you already have, and say plainly what they do not cover."
            }
        ]
    wanted = list(dict.fromkeys(t.upper() for t in tickers or []))
    # Several companies: a few passages from each. One company or none: the usual top results.
    searches = [
        (
            SearchFilters(ticker=ticker, fiscal_year=fiscal_year, form_type=form_type),
            {"top_k": PASSAGES_PER_COMPANY} if len(wanted) > 1 else {},
        )
        for ticker in wanted or [None]
    ]
    with (
        ctx.deps.progress.step(
            "Searching filings",
            _describe_search(query, searches[0][0], wanted),
        ) as report,
        tool_timer(
            "search_filings",
            query=query,
            filters=searches[0][0].model_dump() | {"tickers": wanted},
        ) as done,
    ):
        found = await asyncio.gather(
            *(
                ctx.deps.retriever.search(
                    query, filters=filters, neighbor_window=0, **limits
                )
                for filters, limits in searches
            )
        )
        passages = [passage for group in found for passage in group]
        done(results=len(passages))
        report(f"Found {len(passages)} passages for “{query}”")
    if not passages:
        # Smaller models keep rephrasing and re-searching an empty result; say what it means.
        return [
            {
                "note": "No passages matched. If you filtered by ticker or fiscal_year, "
                "that filing is not in the corpus: stop searching and answer with "
                "insufficient_evidence, giving no citations."
            }
        ]
    _remember(ctx, passages)
    results = [_render(passage, max_chars=SEARCH_PASSAGE_CHARS) for passage in passages]
    missing = [t for t, group in zip(wanted, found, strict=False) if not group]
    if missing:
        results.append(
            {"note": f"No passages at all for {', '.join(missing)}: not in the corpus."}
        )
    return results


@agent.tool
async def read_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_ids: list[UUID]
) -> list[dict]:
    """Read several passages in full by chunk_id, in one call. Prefer this to repeated read_chunk."""
    wanted = chunk_ids[:MAX_BATCH_CHUNKS]
    with (
        ctx.deps.progress.step("Reading passages", f"{len(wanted)} passages") as report,
        tool_timer("read_chunks", requested=len(wanted)) as done,
    ):
        passages = await ctx.deps.retriever.read_chunks(wanted)
        done(results=len(passages))
        report(_describe_passages(passages))
    if not passages:
        raise ModelRetry(
            "None of those chunk ids exist. Use chunk_ids from search_filings."
        )
    _remember(ctx, passages)
    return [_render(passage) for passage in passages]


@agent.tool
async def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: UUID) -> dict:
    """Read one passage in full by its chunk_id."""
    with (
        ctx.deps.progress.step("Reading passage") as report,
        tool_timer("read_chunk") as done,
    ):
        passage = await ctx.deps.retriever.read_chunk(chunk_id)
        done(found=passage is not None)
        if passage:
            report(_describe_passages([passage]))
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
    with (
        ctx.deps.progress.step("Reading surrounding text") as report,
        tool_timer("read_surrounding_chunks") as done,
    ):
        passage = await ctx.deps.retriever.read_chunk(
            chunk_id, neighbor_window=min(max(window, 1), MAX_SURROUNDING_CHUNKS)
        )
        done(found=passage is not None)
        if passage:
            report(_describe_passages([passage]))
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
    with ctx.deps.progress.step("Verifying citations") as report:
        violations = validate_answer(answer, ctx.deps.retrieved)
        if violations:
            report("Some citations failed the check; asking for a corrected answer")
            raise ModelRetry(
                "Your answer failed grounding checks. Fix every item and answer again:\n- "
                + "\n- ".join(violations)
            )
        report(f"{len(answer.citations)} citations checked against the filings")
    return answer
