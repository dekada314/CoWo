import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import AgentRunStatus
from src.infrastructure.database.models.base import Base


class AgentRunORM(Base):
    __tablename__ = "agent_runs"

    thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    graph_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, name="agent_run_status"),
        default=AgentRunStatus.QUEUED,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_agent_runs_thread_created", "thread_id", "created_at"),
        Index("ix_agent_runs_status_created", "status", "created_at"),
        Index("ix_agent_runs_user", "user_id"),
    )
