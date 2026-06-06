from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowPosition:
    x: float
    y: float


@dataclass
class WorkflowNode:
    id: str
    type: str
    position: WorkflowPosition | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowEdge:
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None


@dataclass
class WorkflowConfig:
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
