from datetime import date
from uuid import UUID

from pydantic import BaseModel


class Citation(BaseModel):
    """Points an `[n]` marker in the answer at a retrieved chunk."""

    marker: int
    chunk_id: UUID
    # Verbatim text from the chunk that supports the claim.
    quote: str


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[Citation] = []
    # The only way to answer without citations: say the corpus can't support it.
    insufficient_evidence: bool = False


class VerifiedCitation(BaseModel):
    """A validated citation joined with its source passage, as shown to and stored for the analyst."""

    marker: int
    chunk_id: UUID
    quote: str
    excerpt: str
    ticker: str
    form_type: str
    fiscal_year: int
    filing_date: date
    section: str | None
    page: int | None


class VerifiedAnswer(BaseModel):
    text: str
    citations: list[VerifiedCitation] = []
