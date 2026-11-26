import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class ChatSessionORM(Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_chat_sessions_user", "user_id"),
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )
