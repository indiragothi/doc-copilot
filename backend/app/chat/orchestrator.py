import time
from uuid import UUID

import structlog
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage

from app.assistant.agent import agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer, VerifiedAnswer, VerifiedCitation
from app.assistant.progress import ProgressReporter
from app.grounding.judge import judge_answer
from app.retrieval.retriever import DocumentRetriever

FAILURE_MESSAGE = (
    "I couldn't produce an answer I could verify against the filings. "
    "Please try rephrasing or narrowing the question."
)

log = structlog.get_logger()


async def check_claims(answer: GroundedAnswer, deps: DocumentAgentDeps) -> None:
    """Have the judge model look for claims the citations do not support, and log what it finds.

    Advisory for now: the answer is never changed or held back, and a judge failure (quota,
    bad output) only gets logged, so the judge cannot break a turn the validator accepted.
    """
    if answer.insufficient_evidence or not answer.citations:
        return
    started = time.perf_counter()
    with deps.progress.step("Checking claims") as report:
        try:
            result = await judge_answer(answer, deps.retrieved)
        except (ModelHTTPError, UnexpectedModelBehavior) as error:
            log.warning("judge_failed", thread_id=str(deps.thread_id), error=str(error))
            report("Claim check unavailable")
            return
        report("Claims checked against the cited passages")
    unsupported = result.output.unsupported
    (log.warning if unsupported else log.info)(
        "judge_result",
        thread_id=str(deps.thread_id),
        seconds=round(time.perf_counter() - started, 2),
        input_tokens=result.usage.input_tokens,
        unsupported=len(unsupported),
        claims=[claim.model_dump() for claim in unsupported],
    )


async def run_turn(
    retriever: DocumentRetriever,
    *,
    user_id: UUID,
    thread_id: UUID,
    question: str,
    history: list[ModelMessage],
    progress: ProgressReporter | None = None,
) -> VerifiedAnswer:
    """One chat turn: the agent retrieves and answers, grounding checks run inside it.

    Fails closed: if the model cannot produce a grounded answer, the analyst gets a fixed
    message, never the unverified text.
    """
    deps = DocumentAgentDeps(user_id=user_id, thread_id=thread_id, retriever=retriever)
    if progress:
        deps.progress = progress
    started = time.perf_counter()
    try:
        result = await agent.run(question, message_history=history, deps=deps)
    except UnexpectedModelBehavior as error:
        log.warning(
            "grounding_failed",
            thread_id=str(thread_id),
            seconds=round(time.perf_counter() - started, 2),
            error=str(error),
        )
        return VerifiedAnswer(text=FAILURE_MESSAGE)

    answer = result.output
    await check_claims(answer, deps)
    citations = [
        VerifiedCitation(
            marker=citation.marker,
            chunk_id=citation.chunk_id,
            quote=citation.quote,
            excerpt=passage.content,
            ticker=passage.ticker,
            form_type=passage.form_type,
            fiscal_year=passage.fiscal_year,
            filing_date=passage.filing_date,
            section=passage.section,
            page=passage.page,
        )
        for citation in sorted(answer.citations, key=lambda c: c.marker)
        for passage in [deps.retrieved[citation.chunk_id]]
    ]
    usage = result.usage
    log.info(
        "turn_complete",
        thread_id=str(thread_id),
        seconds=round(time.perf_counter() - started, 2),
        model_requests=usage.requests,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        token_details=usage.details,
        passages_retrieved=len(deps.retrieved),
        citations=len(citations),
        insufficient_evidence=answer.insufficient_evidence,
    )
    return VerifiedAnswer(text=answer.answer, citations=citations)
