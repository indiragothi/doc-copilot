"""embedding column 1536 -> 1024 for nvidia/nemotron-3.5-embed-8b

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _set_embedding_dimensions(dimensions: int) -> None:
    # Existing vectors can't be cast between sizes; this only works while the table is empty.
    op.drop_index("ix_document_chunks_embedding", table_name="document_chunks")
    op.execute(
        f"alter table document_chunks alter column embedding type vector({dimensions})"
    )
    op.create_index(
        "ix_document_chunks_embedding",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def upgrade() -> None:
    _set_embedding_dimensions(1024)


def downgrade() -> None:
    _set_embedding_dimensions(1536)
