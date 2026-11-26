import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class KnowledgeCardORM(Base):
    __tablename__ = "knowledge_cards"
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), nullable=False
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    analysis: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (UniqueConstraint("job_id", name="uq_knowledge_cards_job"),)
