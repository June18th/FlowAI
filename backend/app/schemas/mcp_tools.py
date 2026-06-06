from __future__ import annotations

from pydantic import BaseModel, Field


class McpToolConfigRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    toolType: str | None = "custom"
    toolName: str = Field(..., min_length=1)
    transport: str | None = "stdio"
    command: str = Field(..., min_length=1)
    args: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: int | None = 1


class McpToolConfigResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    toolType: str | None = "custom"
    toolName: str
    transport: str | None = "stdio"
    command: str
    args: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: int | None = 1
    preset: int | None = 0
    createdAt: str | None = None
    updatedAt: str | None = None


class AgentPlanWebSearchMcpRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    apiKey: str = Field(..., min_length=1)


class McpToolTestRequest(BaseModel):
    query: str | None = None
