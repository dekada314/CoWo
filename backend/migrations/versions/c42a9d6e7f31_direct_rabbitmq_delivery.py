"""Remove polling-outbox fields after switching to direct RabbitMQ delivery."""

import sqlalchemy as sa
from alembic import op

revision = "c42a9d6e7f31"
down_revision = "b13f4ac09211"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_ingestion_jobs_dispatch", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "next_dispatch_at")
    op.drop_column("ingestion_jobs", "next_attempt_at")


def downgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "next_dispatch_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_ingestion_jobs_dispatch",
        "ingestion_jobs",
        ["status", "next_dispatch_at"],
    )
