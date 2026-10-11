import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, created_at_column


class User(Base):
    __tablename__ = "users"

    # Same value as Supabase auth.users.id, so there is no server default.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = created_at_column()
