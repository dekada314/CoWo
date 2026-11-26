"""align ORM schema

Revision ID: 9b7d2a1c6e40
Revises: 4f1b86450631
Create Date: 2026-11-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9b7d2a1c6e40"
down_revision: str | Sequence[str] | None = "4f1b86450631"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAGE_RENAMES = (
    ("uploaded", "UPLOADED"),
    ("extraction", "EXTRACTION"),
    ("chunking", "CHUNKING"),
    ("embedding", "EMBEDDING"),
    ("indexing", "INDEXING"),
    ("graph_extraction", "GRAPH_EXTRACTION"),
    ("graph_indexing", "GRAPH_INDEXING"),
)


def upgrade() -> None:
    op.execute("UPDATE users SET is_active = true WHERE is_active IS NULL")
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.true(),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    op.add_column(
        "documents",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.drop_column("documents", "processing_stage")
    op.drop_column("documents", "s3_file_key")

    for old_value, new_value in _STAGE_RENAMES:
        op.execute(
            f"ALTER TYPE processing_stage RENAME VALUE '{old_value}' TO '{new_value}'"
        )


def downgrade() -> None:
    for old_value, new_value in reversed(_STAGE_RENAMES):
        op.execute(
            f"ALTER TYPE processing_stage RENAME VALUE '{new_value}' TO '{old_value}'"
        )

    processing_stage = postgresql.ENUM(
        *(old for old, _ in _STAGE_RENAMES),
        name="processing_stage",
        create_type=False,
    )
    op.add_column(
        "documents",
        sa.Column(
            "processing_stage",
            processing_stage,
            server_default="uploaded",
            nullable=False,
        ),
    )
    op.alter_column("documents", "processing_stage", server_default=None)
    op.add_column(
        "documents",
        sa.Column(
            "s3_file_key",
            sa.String(),
            server_default="",
            nullable=False,
        ),
    )
    op.alter_column("documents", "s3_file_key", server_default=None)
    op.drop_column("documents", "is_deleted")

    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
