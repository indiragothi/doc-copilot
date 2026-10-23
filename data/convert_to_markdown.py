from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from docling.document_converter import DocumentConverter

# Docling is a backend dev dependency, so run this through the backend project:
#   uv run --project backend data/convert_to_markdown.py
# Besides the .md (human-readable, stored in source_documents), each filing's DoclingDocument
# is saved as JSON: the chunker needs the real table structure, which Markdown flattens.
# Re-running skips filings that already have both files; set OVERWRITE to redo them.
DATA_DIR = Path(__file__).resolve().parent
INPUT_DIR = DATA_DIR / "downloads"
OUTPUT_DIR = DATA_DIR / "markdown"
DOCLING_DIR = DATA_DIR / "docling"
OVERWRITE = False


def convert_filing(
    converter: DocumentConverter, source: Path, markdown: Path, docling_json: Path
) -> None:
    document = converter.convert(source).document
    markdown.parent.mkdir(parents=True, exist_ok=True)
    docling_json.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(document.export_to_markdown(), encoding="utf-8")
    document.save_as_json(docling_json)


def main() -> int:
    manifest = json.loads((INPUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    converter = DocumentConverter()
    failures = []

    for i, filing in enumerate(manifest["filings"], start=1):
        source = INPUT_DIR / filing["local_path"]
        markdown = OUTPUT_DIR / Path(filing["local_path"]).with_suffix(".md")
        docling_json = DOCLING_DIR / Path(filing["local_path"]).with_suffix(".json")
        filing["local_path"] = str(Path(filing["local_path"]).with_suffix(".md"))
        label = f"[{i}/{len(manifest['filings'])}] {filing['local_path']}"

        if markdown.exists() and docling_json.exists() and not OVERWRITE:
            print(f"{label} already converted, skipping")
            continue

        print(f"{label} converting...", flush=True)
        started = time.monotonic()
        try:
            convert_filing(converter, source, markdown, docling_json)
        except Exception as exc:  # noqa: BLE001 - one bad filing shouldn't stop the other 24
            failures.append(filing["local_path"])
            print(f"  FAILED: {exc}")
            continue
        print(f"  done in {time.monotonic() - started:.0f}s")

    # Same shape as downloads/manifest.json, but local_path points at the .md files.
    manifest["format"] = "markdown"
    manifest["converted_count"] = len(manifest["filings"]) - len(failures)
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if failures:
        print(f"\n{len(failures)} failed: {', '.join(failures)}")
        return 1
    print(f"\nConverted {manifest['converted_count']} filings to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
