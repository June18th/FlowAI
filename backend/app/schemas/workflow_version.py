from typing import Any

from pydantic import BaseModel


class WorkflowVersionResponse(BaseModel):
    id: int
    workflowId: int
    versionNumber: int
    name: str
    flowData: Any = None
    engineType: str | None = None
    createdAt: str | None = None


class WorkflowVersionDiffResponse(BaseModel):
    version1Id: int
    version1Number: int
    version2Id: int
    version2Number: int
    nameChanged: bool = False
    engineTypeChanged: bool = False
    nodesAdded: list[str] = []
    nodesRemoved: list[str] = []
    nodesModified: list[str] = []
    edgesAdded: int = 0
    edgesRemoved: int = 0


class WorkflowVersionRollbackResponse(BaseModel):
    workflowId: int
    rolledFromVersion: int
    rolledToVersion: int
    newVersionNumber: int
