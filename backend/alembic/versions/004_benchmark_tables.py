"""benchmark — dataset, case, run tables

Revision ID: 004
Revises: 003
Create Date: 2026-06-06
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # benchmark_dataset
    op.create_table(
        "benchmark_dataset",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("workflow_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # benchmark_case
    op.create_table(
        "benchmark_case",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.BigInteger(), nullable=False),
        sa.Column("input_data", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text()),
        sa.Column("scoring_method", sa.String(20), server_default="contains"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_benchmark_case_dataset", "benchmark_case", ["dataset_id"])

    # benchmark_run
    op.create_table(
        "benchmark_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.BigInteger(), nullable=False),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("total_cases", sa.Integer(), server_default="0"),
        sa.Column("passed_cases", sa.Integer(), server_default="0"),
        sa.Column("failed_cases", sa.Integer(), server_default="0"),
        sa.Column("avg_score", sa.Numeric(5, 2)),
        sa.Column("results", mysql.JSON()),
        sa.Column("status", sa.String(20), server_default="RUNNING"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.current_timestamp()),
        sa.Column("completed_at", sa.TIMESTAMP()),
        sa.Column("deleted", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_benchmark_run_dataset", "benchmark_run", ["dataset_id"])
    op.create_index("idx_benchmark_run_workflow", "benchmark_run", ["workflow_id"])


def downgrade() -> None:
    op.drop_table("benchmark_run")
    op.drop_table("benchmark_case")
    op.drop_table("benchmark_dataset")
