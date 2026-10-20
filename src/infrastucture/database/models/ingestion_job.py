import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastucture.database.models.base import Base
from src.infrastucture.database.models.enums import JobStatus, ProcessingStage


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    stage: Mapped[ProcessingStage | None] = mapped_column(
        Enum(ProcessingStage, name="processing_stage"), nullable=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(100), nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_ingestion_jobs_status_created", "status", "created_at"),
        Index(
            "ix_ingestion_jobs_version_created",
            "document_version_id",
            "created_at",
        ),
        Index("ix_ingestion_jobs_document_version", "document_version_id"),
    )
