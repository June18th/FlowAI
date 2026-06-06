"""Structured execution context — carries trace, state, and control params."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    """Immutable-context passed to every node executor during a workflow run."""

    # ── identity ──
    execution_id: int
    workflow_id: int
    workflow_name: str = ""
    engine_type: str = "dag"

    # ── tracing ──
    trace_id: str = ""
    span_id: str = ""

    # ── control ──
    node_timeout_ms: int = 600_000       # 10 min per node
    retry_count: int = 0
    max_retries: int = 3
    retry_delay_ms: int = 2000            # exponential backoff base

    # ── mutable state (updated by engine) ──
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_inputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    status: str = "RUNNING"
    error_message: str = ""

    # ── timestamps ──
    started_at: float = 0.0
    finished_at: float = 0.0

    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = uuid.uuid4().hex[:16]
        if self.started_at == 0.0:
            self.started_at = time.time()

    # ── factory ──

    @classmethod
    def create(cls, execution_id: int, workflow_id: int, workflow_name: str = "",
               engine_type: str = "dag", **kwargs) -> "ExecutionContext":
        return cls(
            execution_id=execution_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            engine_type=engine_type,
            **kwargs,
        )

    # ── runtime helpers ──

    def new_span_id(self) -> str:
        self.span_id = uuid.uuid4().hex[:12]
        return self.span_id

    def store_output(self, node_id: str, output: dict[str, Any]) -> None:
        self.node_outputs[node_id] = output

    def get_output(self, node_id: str) -> dict[str, Any]:
        return self.node_outputs.get(node_id, {})

    def store_input(self, node_id: str, input_data: dict[str, Any]) -> None:
        self.node_inputs[node_id] = input_data

    def should_retry(self, current_retry: int) -> bool:
        return current_retry < self.max_retries

    def backoff_delay(self, attempt: int) -> float:
        """Exponential backoff: 2s, 4s, 8s..."""
        return (self.retry_delay_ms * (2 ** (attempt - 1))) / 1000.0

    def is_timeout(self, node_start: float) -> bool:
        return (time.time() - node_start) * 1000 > self.node_timeout_ms

    def mark_success(self, duration_ms: int = 0) -> None:
        self.status = "SUCCESS"
        self.finished_at = time.time()

    def mark_failed(self, error: str) -> None:
        self.status = "FAILED"
        self.error_message = error
        self.finished_at = time.time()

    @property
    def duration_ms(self) -> int:
        if self.finished_at:
            return int((self.finished_at - self.started_at) * 1000)
        return int((time.time() - self.started_at) * 1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executionId": self.execution_id,
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "engineType": self.engine_type,
            "traceId": self.trace_id,
            "status": self.status,
            "errorMessage": self.error_message,
            "durationMs": self.duration_ms,
            "nodeOutputs": self.node_outputs,
            "retryCount": self.retry_count,
        }
