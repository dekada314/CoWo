from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.document_version import (
        DocumentVersionORM,
    )
    from src.infrastructure.database.models.user import UserORM


class DocumentORM(Base):
    __tablename__ = "documents"

    uploaded_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    doc_name: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(255), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    versions: Mapped[list["DocumentVersionORM"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    uploader: Mapped["UserORM | None"] = relationship(
        back_populates="documents",
        lazy="raise",
    )
