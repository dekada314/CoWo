"""Durable ingestion delivery, fenced leases and analyst cards."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b13f4ac09211"
down_revision = "9b7d2a1c6e40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("lease_token", sa.Uuid()))
    op.add_column(
        "ingestion_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True))
    )
    for name in ("next_attempt_at", "next_dispatch_at"):
        op.add_column(
            "ingestion_jobs",
            sa.Column(
                name,
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    op.create_index(
        "ix_ingestion_jobs_dispatch", "ingestion_jobs", ["status", "next_dispatch_at"]
    )
    op.create_table(
        "knowledge_cards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            sa.Uuid(),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("job_id", name="uq_knowledge_cards_job"),
    )
    op.create_index(
        "ix_knowledge_cards_document_version_id",
        "knowledge_cards",
        ["document_version_id"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_cards")
    op.drop_index("ix_ingestion_jobs_dispatch", table_name="ingestion_jobs")
    for name in (
        "next_dispatch_at",
        "next_attempt_at",
        "lease_expires_at",
        "lease_token",
    ):
        op.drop_column("ingestion_jobs", name)
