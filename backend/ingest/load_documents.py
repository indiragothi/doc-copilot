"""Load the converted filings in data/markdown/ into `source_documents`.

Run from backend/: uv run python -m ingest.load_documents
Safe to re-run: filings whose accession number is already stored are skipped.
"""

import json
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

from app.config import settings
from app.database.models import SourceDocument

MARKDOWN_DIR = Path(__file__).resolve().parents[2] / "data" / "markdown"


def build_row(filing: dict) -> dict:
    report_date = date.fromisoformat(filing["report_date"])
    return {
        "ticker": filing["ticker"],
        "cik": filing["cik"],
        "form_type": filing["form"],
        "filing_date": date.fromisoformat(filing["filing_date"]),
        "report_date": report_date,
        # Matches each company's own fiscal-year label (e.g. NVIDIA's year ending Jan 2025 is FY2025).
        "fiscal_year": report_date.year,
        "accession_number": filing["accession_number"],
        "source_url": filing["source_url"],
        "markdown_content": (MARKDOWN_DIR / filing["local_path"]).read_text(
            encoding="utf-8"
        ),
    }


def main() -> None:
    manifest = json.loads((MARKDOWN_DIR / "manifest.json").read_text(encoding="utf-8"))
    url = make_url(settings.database_url).set(drivername="postgresql+psycopg")
    engine = create_engine(url)

    inserted = 0
    with engine.begin() as connection:
        for filing in manifest["filings"]:
            new_id = connection.execute(
                insert(SourceDocument)
                .values(build_row(filing))
                .on_conflict_do_nothing(index_elements=["accession_number"])
                .returning(SourceDocument.id)
            ).scalar_one_or_none()
            inserted += new_id is not None
            status = "inserted" if new_id else "already present"
            print(f"{filing['ticker']} {filing['report_date']}: {status}")

    print(f"\n{inserted} inserted, {len(manifest['filings']) - inserted} skipped")


if __name__ == "__main__":
    main()
