"""Chunk the converted filings, embed the chunks and store them in `document_chunks`.

Run from backend/:
  uv run python -m ingest.load_chunks --dry-run   chunk everything; no API calls, no writes
  uv run python -m ingest.load_chunks --test      embed and store ONE chunk, then check it
  uv run python -m ingest.load_chunks             full run (embeds every chunk)

A filing is skipped when its stored chunk count already matches; otherwise its chunks
are replaced in one transaction, so a crash never leaves a half-loaded filing.
"""

import argparse
import json
import statistics
from pathlib import Path
from uuid import UUID

from docling_core.types.doc import DoclingDocument
from sqlalchemy import Connection, create_engine, delete, func, insert, select, text
from sqlalchemy.engine import make_url

from app.config import settings
from app.database.models import DocumentChunk, SourceDocument
from ingest.chunking import FilingChunk, build_chunker, chunk_document
from ingest.embeddings import embed_texts

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BATCH_SIZE = 16

TEST_TICKER = "AAPL"
TEST_FISCAL_YEAR = 2025
TEST_PASSAGE = "Total net sales"


def chunk_filing(filing: dict, chunker) -> list[FilingChunk]:
    path = DATA_DIR / "docling" / Path(filing["local_path"]).with_suffix(".json")
    return chunk_document(DoclingDocument.load_from_json(path), chunker)


def chunk_row(
    document_id: UUID, filing: dict, chunk: FilingChunk, embedding: list[float]
) -> dict:
    return {
        "document_id": document_id,
        "chunk_index": chunk.chunk_index,
        "section": chunk.section,
        "content": chunk.content,
        "token_count": chunk.token_count,
        "embedding": embedding,
        "chunk_metadata": {
            "ticker": filing["ticker"],
            "form_type": filing["form"],
            "fiscal_year": int(filing["report_date"][:4]),
            "filing_date": filing["filing_date"],
        },
    }


def replace_chunks(connection: Connection, document_id: UUID, rows: list[dict]) -> None:
    connection.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    connection.execute(insert(DocumentChunk), rows)


def stored_chunk_count(connection: Connection, document_id: UUID) -> int:
    return connection.scalar(
        select(func.count()).where(DocumentChunk.document_id == document_id)
    )


def embed_chunks(chunks: list[FilingChunk]) -> list[list[float]]:
    vectors = []
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        vectors.extend(embed_texts([chunk.content for chunk in batch]))
        print(f"    embedded {len(vectors)}/{len(chunks)}", flush=True)
    return vectors


def dry_run(filings: list[dict]) -> None:
    chunker = build_chunker()
    all_tokens = []
    for filing in filings:
        chunks = chunk_filing(filing, chunker)
        tokens = [chunk.token_count for chunk in chunks]
        all_tokens += tokens
        unsectioned = sum(chunk.section is None for chunk in chunks)
        print(
            f"{filing['ticker']} {filing['report_date']}: {len(chunks)} chunks, "
            f"median {statistics.median(tokens):.0f} / max {max(tokens)} tokens, "
            f"{unsectioned} without a section"
        )
    batches = -(-len(all_tokens) // BATCH_SIZE)
    print(
        f"\n{len(all_tokens)} chunks, {sum(all_tokens)} tokens in total "
        f"-> {batches} embedding requests of up to {BATCH_SIZE}"
    )


def test_one_chunk(connection: Connection, filing: dict, document_id: UUID) -> None:
    chunks = chunk_filing(filing, build_chunker())
    chunk = next(c for c in chunks if TEST_PASSAGE in c.content)
    print(f"Chunk {chunk.chunk_index} of {len(chunks)} ({chunk.token_count} tokens):")
    print(f"  section: {chunk.section}\n  {chunk.content[:300]!r}")

    [embedding] = embed_texts([chunk.content])
    print(f"Embedding returned {len(embedding)} dimensions")
    replace_chunks(
        connection, document_id, [chunk_row(document_id, filing, chunk, embedding)]
    )

    stored = connection.execute(
        text(
            "select vector_dims(embedding), search_vector is not null, "
            "length(search_vector::text) from document_chunks where document_id = :id"
        ),
        {"id": document_id},
    ).one()
    print(f"Stored: vector_dims={stored[0]}, search_vector populated={stored[1]}")

    relevant, unrelated = embed_texts(
        ["What were Apple's total net sales in 2025?", "A recipe for chocolate cake"]
    )
    for label, query in (
        ("relevant question", relevant),
        ("unrelated text", unrelated),
    ):
        similarity = connection.scalar(
            text(
                "select 1 - (embedding <=> cast(:q as vector)) from document_chunks "
                "where document_id = :id"
            ),
            {"q": str(query), "id": document_id},
        )
        print(f"Cosine similarity to {label}: {similarity:.3f}")


def load_all(connection: Connection, filings: list[dict], ids: dict[str, UUID]) -> None:
    chunker = build_chunker()
    for filing in filings:
        label = f"{filing['ticker']} {filing['report_date']}"
        document_id = ids.get(filing["accession_number"])
        if document_id is None:
            print(f"{label}: not in source_documents, skipping")
            continue
        chunks = chunk_filing(filing, chunker)

        if stored_chunk_count(connection, document_id) == len(chunks):
            print(f"{label}: already loaded ({len(chunks)} chunks), skipping")
            continue

        print(f"{label}: embedding {len(chunks)} chunks")
        vectors = embed_chunks(chunks)
        rows = [
            chunk_row(document_id, filing, chunk, vector)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        replace_chunks(connection, document_id, rows)
        connection.commit()
        print(f"{label}: stored {len(rows)} chunks")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--test", action="store_true")
    args = parser.parse_args()

    manifest = json.loads((DATA_DIR / "markdown" / "manifest.json").read_text("utf-8"))
    filings = manifest["filings"]
    if args.dry_run:
        dry_run(filings)
        return

    url = make_url(settings.database_url).set(drivername="postgresql+psycopg")
    with create_engine(url).connect() as connection:
        ids = dict(
            connection.execute(
                select(SourceDocument.accession_number, SourceDocument.id)
            ).all()
        )
        if args.test:
            filing = next(
                f
                for f in filings
                if f["ticker"] == TEST_TICKER
                and int(f["report_date"][:4]) == TEST_FISCAL_YEAR
            )
            test_one_chunk(connection, filing, ids[filing["accession_number"]])
            connection.commit()
        else:
            load_all(connection, filings, ids)


if __name__ == "__main__":
    main()
