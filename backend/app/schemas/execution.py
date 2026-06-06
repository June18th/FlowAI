from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    workflowId: int
    inputData: str = Field(..., min_length=1)


class NodeResult(BaseModel):
    nodeId: str
    nodeName: str | None = None
    status: str
    input: Any = None
    output: Any = None
    duration: int | None = None
    error: str | None = None


class ExecutionResponse(BaseModel):
    executionId: int
    status: str  # SUCCESS / FAILED / RUNNING
    inputData: Any = None
    nodeResults: list[NodeResult] = []
    outputData: Any = None
    duration: int | None = None
    errorMessage: str | None = None


class ExecutionEvent(BaseModel):
    eventType: str
    nodeId: str | None = None
    nodeName: str | None = None
    status: str | None = None
    message: str | None = None
    data: Any = None
    timestamp: float | None = None


class ExecutionSnapshotResponse(BaseModel):
    id: int
    executionId: int
    flowId: int
    nodeId: str
    nodeType: str
    nodeName: str | None = None
    status: str
    inputData: dict | None = None
    outputData: dict | None = None
    errorMessage: str | None = None
    startedAt: str | None = None
    completedAt: str | None = None
    duration: int | None = None
    retryCount: int | None = 0
    executionOrder: int | None = 0
    createdAt: str | None = None


class ExecutionVariableResponse(BaseModel):
    id: int
    executionId: int
    variableName: str
    variableType: str | None = "STRING"
    variableValue: str | None = None
    isModified: int | None = 0
    createdAt: str | None = None
    updatedAt: str | None = None


class ResumeExecutionRequest(BaseModel):
    startNodeId: str | None = None
    useSnapshotVariables: bool = True
    modifiedVariables: dict[str, Any] | None = None
    skipSuccessNodes: bool = True
