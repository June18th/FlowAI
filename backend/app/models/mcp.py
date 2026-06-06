from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, TIMESTAMP, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class McpToolConfig(Base):
    __tablename__ = "mcp_tool_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    tool_type: Mapped[str] = mapped_column(String(50), default="custom")
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    transport: Mapped[str] = mapped_column(String(30), default="stdio")
    command: Mapped[str] = mapped_column(String(500), nullable=False)
    args: Mapped[dict | None] = mapped_column(JSON)
    env: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    preset: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted: Mapped[int] = mapped_column(Integer, default=0)
