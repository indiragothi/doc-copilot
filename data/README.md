# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- Downloaded payloads are gitignored because the corpus can get large.
- Fetch a sample corpus with `uv run data/download.py` 

- `markdown/` mirrors `downloads/` (same year folders and `manifest.json`) with each filing converted to Markdown by Docling. Also gitignored.
- Convert the corpus with `uv run --project backend data/convert_to_markdown.py` (Docling is a backend dev dependency). Re-runs skip files already converted.
- `docling/` holds each filing's `DoclingDocument` as JSON (same year folders). The ingestion chunker reads these, not the Markdown. Also gitignored, written by the same script.
