import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.infrastucture.database.models.base import Base
from src.infrastucture.database.models.enums import ProcessingStage

if TYPE_CHECKING:
    from src.infrastucture.database.models.user import User


class Document(Base):
    __tablename__ = "documents"

    s3_file_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    doc_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    doc_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    processing_stage: Mapped[ProcessingStage] = mapped_column(
        Enum(
            ProcessingStage,
            name="processing_stage",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=ProcessingStage.UPLOADED,
    )

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    uploaded_by_user: Mapped[User | None] = relationship(
        back_populates="documents",
    )
