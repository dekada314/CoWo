import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.document import Document


class UserORM(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    is_active: Mapped[bool | None] = mapped_column(
        Boolean,
        default=True,
        nullable=True,
    )

    documents: Mapped[list["DocumentORM"]] = relationship(
        back_populates="uploaded_by_user",
        passive_deletes=True,
    )
