"""Execution tracing — trace_id + span_id for audit & observability."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Span:
    span_id: str
    node_id: str
    node_type: str
    node_name: str
    started_at: str = ""
    finished_at: str = ""
    status: str = "RUNNING"
    input_summary: str = ""
    output_summary: str = ""
    error: str = ""

    def start(self) -> None:
        self.started_at = _now()

    def finish(self, status: str = "SUCCESS", output: dict[str, Any] | None = None) -> None:
        self.finished_at = _now()
        self.status = status
        if output:
            self.output_summary = str(output)[:200]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spanId": self.span_id,
            "nodeId": self.node_id,
            "nodeType": self.node_type,
            "nodeName": self.node_name,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "status": self.status,
            "inputSummary": self.input_summary,
            "outputSummary": self.output_summary,
            "error": self.error,
        }


@dataclass
class Trace:
    trace_id: str
    workflow_id: int
    workflow_name: str
    engine_type: str
    created_at: str = field(default_factory=_now)
    spans: list[Span] = field(default_factory=list)

    def new_span(self, node_id: str, node_type: str, node_name: str = "") -> Span:
        span = Span(
            span_id=uuid.uuid4().hex[:12],
            node_id=node_id,
            node_type=node_type,
            node_name=node_name,
        )
        span.start()
        self.spans.append(span)
        return span

    def to_dict(self) -> dict[str, Any]:
        return {
            "traceId": self.trace_id,
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "engineType": self.engine_type,
            "createdAt": self.created_at,
            "spans": [s.to_dict() for s in self.spans],
        }


def create_trace(workflow_id: int, workflow_name: str, engine_type: str) -> Trace:
    return Trace(
        trace_id=uuid.uuid4().hex[:16],
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        engine_type=engine_type,
    )
