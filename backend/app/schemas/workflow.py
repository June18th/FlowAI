from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    flowData: str = Field(..., min_length=1)
    engineType: str | None = "dag"


class WorkflowResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    flowData: str | None = None
    engineType: str | None = "dag"
    createdAt: str | None = None
    updatedAt: str | None = None


class NodeDefinitionResponse(BaseModel):
    id: int
    nodeType: str
    displayName: str
    category: str
    icon: str | None = None
    inputSchema: Any = None
    outputSchema: Any = None
    configSchema: Any = None
