import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastucture.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastucture.database.models.document import Document


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

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

    documents: Mapped[list["Document"]] = relationship(
        back_populates="uploaded_by_user",
        passive_deletes=True,
    )
