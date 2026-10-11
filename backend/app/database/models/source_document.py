import uuid
from datetime import date, datetime

from sqlalchemy import Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, created_at_column, uuid_pk


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    ticker: Mapped[str]
    cik: Mapped[str]
    form_type: Mapped[str]
    filing_date: Mapped[date] = mapped_column(Date)
    report_date: Mapped[date] = mapped_column(Date)
    fiscal_year: Mapped[int]
    accession_number: Mapped[str] = mapped_column(unique=True)
    source_url: Mapped[str]
    # Normalized Markdown, kept so filings can be re-chunked without the original HTML.
    markdown_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
