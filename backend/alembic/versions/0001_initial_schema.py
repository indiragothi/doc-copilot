"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )


def created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    op.execute("create extension if not exists vector")

    op.create_table(
        "users",
        # Same value as Supabase auth.users.id, so there is no server default.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        created_at(),
    )

    op.create_table(
        "source_documents",
        uuid_pk(),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("cik", sa.String(), nullable=False),
        sa.Column("form_type", sa.String(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("accession_number", sa.String(), nullable=False, unique=True),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        created_at(),
    )

    op.create_table(
        "document_chunks",
        uuid_pk(),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("section", sa.String()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        created_at(),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index(
        "ix_document_chunks_embedding",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "chat_threads",
        uuid_pk(),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String()),
        created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_threads_user_id", "chat_threads", ["user_id"])

    op.create_table(
        "chat_messages",
        uuid_pk(),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("parts", postgresql.JSONB()),
        created_at(),
        sa.CheckConstraint("role in ('user', 'assistant')", name="role_valid"),
    )
    op.create_index(
        "ix_chat_messages_thread_id_created_at",
        "chat_messages",
        ["thread_id", "created_at"],
    )

    op.create_table(
        "message_citations",
        uuid_pk(),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        created_at(),
    )
    op.create_index(
        "ix_message_citations_message_id", "message_citations", ["message_id"]
    )

    enable_row_level_security()


def downgrade() -> None:
    # The `vector` extension is left in place; other objects may depend on it.
    for table in (
        "message_citations",
        "chat_messages",
        "chat_threads",
        "document_chunks",
        "source_documents",
        "users",
    ):
        op.drop_table(table)


def enable_row_level_security() -> None:
    """Users see only their own chats.

    The backend's direct Postgres connection and the service-role key bypass RLS;
    these policies protect requests made with a user's JWT (anon key + Supabase client).
    """
    for table in (
        "users",
        "chat_threads",
        "chat_messages",
        "message_citations",
        "source_documents",
        "document_chunks",
    ):
        op.execute(f"alter table {table} enable row level security")

    op.execute(
        "create policy users_select_own on users for select to authenticated "
        "using (id = auth.uid())"
    )
    op.execute(
        "create policy chat_threads_own on chat_threads for all to authenticated "
        "using (user_id = auth.uid()) with check (user_id = auth.uid())"
    )

    owned_thread = "select id from chat_threads where user_id = auth.uid()"
    op.execute(
        "create policy chat_messages_own on chat_messages for all to authenticated "
        f"using (thread_id in ({owned_thread})) "
        f"with check (thread_id in ({owned_thread}))"
    )

    owned_message = (
        "select m.id from chat_messages m "
        "join chat_threads t on t.id = m.thread_id where t.user_id = auth.uid()"
    )
    op.execute(
        "create policy message_citations_own on message_citations for select to authenticated "
        f"using (message_id in ({owned_message}))"
    )

    # The corpus is shared: any signed-in user can read it, only the backend writes it.
    for table in ("source_documents", "document_chunks"):
        op.execute(
            f"create policy {table}_read on {table} for select to authenticated using (true)"
        )
