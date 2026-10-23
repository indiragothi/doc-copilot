from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SearchFilters(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str | None = None
    fiscal_year: int | None = None
    form_type: str | None = None


class SourcePassage(BaseModel):
    """A retrieved chunk with its filing metadata; the unit citations point at."""

    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    ticker: str
    form_type: str
    fiscal_year: int
    filing_date: date
    section: str | None
    page: int | None
    content: str
    score: float = 0.0
    # Adjacent chunks of the same filing, in document order. Context only, never ranked.
    context_before: list[str] = []
    context_after: list[str] = []
