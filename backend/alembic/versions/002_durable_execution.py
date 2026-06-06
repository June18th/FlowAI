"""durable execution — checkpoint + heartbeat + worker_id

Revision ID: 002
Revises: 001
Create Date: 2026-06-06
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE execution_record
        ADD COLUMN engine_type VARCHAR(50) NULL AFTER deleted,
        ADD COLUMN execution_state JSON NULL AFTER engine_type,
        ADD COLUMN last_completed_node_id VARCHAR(100) NULL AFTER execution_state,
        ADD COLUMN worker_id VARCHAR(100) NULL AFTER last_completed_node_id,
        ADD COLUMN heartbeat_at TIMESTAMP NULL AFTER worker_id
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE execution_record
        DROP COLUMN engine_type,
        DROP COLUMN execution_state,
        DROP COLUMN last_completed_node_id,
        DROP COLUMN worker_id,
        DROP COLUMN heartbeat_at
    """)
