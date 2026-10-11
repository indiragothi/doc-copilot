import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, created_at_column, uuid_pk


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role in ('user', 'assistant')", name="role_valid"),
        Index("ix_chat_messages_thread_id_created_at", "thread_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_threads.id", ondelete="CASCADE")
    )
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    # AI SDK UI message parts, so history can be replayed to the frontend as stored.
    parts: Mapped[list[Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()
