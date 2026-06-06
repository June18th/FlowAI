from __future__ import annotations

from pydantic import BaseModel, Field


class BenchmarkDatasetRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    workflowId: int | None = None


class BenchmarkDatasetResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    workflowId: int | None = None
    caseCount: int = 0
    createdAt: str | None = None
    updatedAt: str | None = None


class BenchmarkCaseRequest(BaseModel):
    inputData: str = Field(..., min_length=1)
    expectedOutput: str | None = None
    scoringMethod: str = "contains"


class BenchmarkCaseResponse(BaseModel):
    id: int
    datasetId: int
    inputData: str
    expectedOutput: str | None = None
    scoringMethod: str
    createdAt: str | None = None


class BenchmarkRunRequest(BaseModel):
    workflowId: int | None = None
    judgeConfigId: int | None = None


class BenchmarkRunResponse(BaseModel):
    id: int
    datasetId: int
    workflowId: int
    totalCases: int
    passedCases: int
    failedCases: int
    avgScore: float | None = None
    results: list[dict] = []
    status: str
    createdAt: str | None = None
    completedAt: str | None = None
