from uuid import UUID

import structlog
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage

from app.assistant.agent import agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import VerifiedAnswer, VerifiedCitation
from app.retrieval.retriever import DocumentRetriever

FAILURE_MESSAGE = (
    "I couldn't produce an answer I could verify against the filings. "
    "Please try rephrasing or narrowing the question."
)

log = structlog.get_logger()


async def run_turn(
    retriever: DocumentRetriever,
    *,
    user_id: UUID,
    thread_id: UUID,
    question: str,
    history: list[ModelMessage],
) -> VerifiedAnswer:
    """One chat turn: the agent retrieves and answers, grounding checks run inside it.

    Fails closed: if the model cannot produce a grounded answer, the analyst gets a fixed
    message, never the unverified text.
    """
    deps = DocumentAgentDeps(user_id=user_id, thread_id=thread_id, retriever=retriever)
    try:
        result = await agent.run(question, message_history=history, deps=deps)
    except UnexpectedModelBehavior as error:
        log.warning("grounding_failed", thread_id=str(thread_id), error=str(error))
        return VerifiedAnswer(text=FAILURE_MESSAGE)

    answer = result.output
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
    log.info(
        "turn_complete",
        thread_id=str(thread_id),
        passages_retrieved=len(deps.retrieved),
        citations=len(citations),
        insufficient_evidence=answer.insufficient_evidence,
    )
    return VerifiedAnswer(text=answer.answer, citations=citations)
