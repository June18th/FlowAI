"""workflow versioning — immutable version snapshots

Revision ID: 003
Revises: 002
Create Date: 2026-06-06
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_version",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("flow_data", mysql.JSON(), nullable=False),
        sa.Column("engine_type", sa.String(50), server_default="dag"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "version_number", name="uk_workflow_version_wf_ver"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_workflow_version_wf_id", "workflow_version", ["workflow_id"])
    op.create_index("idx_workflow_version_wf_ver", "workflow_version", ["workflow_id", "version_number"])


def downgrade() -> None:
    op.drop_table("workflow_version")
