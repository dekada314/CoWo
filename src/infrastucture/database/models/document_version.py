import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastucture.database.models.base import Base


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    __table_args__ = (
        Index(
            "uq_document_versions_document_version",
            "document_id",
            "version_number",
            unique=True,
        ),
        Index("ix_document_versions_content_hash", "content_hash"),
    )
