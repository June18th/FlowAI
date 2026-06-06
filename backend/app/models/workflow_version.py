from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, TIMESTAMP, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkflowVersion(Base):
    __tablename__ = "workflow_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    flow_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    engine_type: Mapped[str] = mapped_column(String(50), default="dag")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())
