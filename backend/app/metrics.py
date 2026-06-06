from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from fastapi import FastAPI

# ── Business metrics ───────────────────────────────────────────────

executions_total = Counter(
    "flowagent_executions_total",
    "Total workflow executions completed",
    ["status", "engine_type"],
)

execution_duration_seconds = Histogram(
    "flowagent_execution_duration_seconds",
    "Workflow execution duration",
    ["engine_type"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600],
)

active_executions = Gauge(
    "flowagent_active_executions",
    "Workflow executions currently in progress",
)

orphaned_executions_gauge = Gauge(
    "flowagent_orphaned_executions",
    "Executions detected as orphaned (stale heartbeat)",
)

node_executions_total = Counter(
    "flowagent_node_executions_total",
    "Node execution outcomes",
    ["node_type", "status"],
)

node_execution_duration_seconds = Histogram(
    "flowagent_node_execution_duration_seconds",
    "Node execution duration",
    ["node_type"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120],
)

node_retries_total = Counter(
    "flowagent_node_retries_total",
    "Node-level retry count",
    ["node_type"],
)

resume_total = Counter(
    "flowagent_resume_total",
    "Checkpoint-based resume count",
    ["status"],
)


def record_execution_start(engine_type: str) -> None:
    active_executions.inc()


def record_execution_end(status: str, engine_type: str, duration_s: float) -> None:
    active_executions.dec()
    executions_total.labels(status=status, engine_type=engine_type).inc()
    execution_duration_seconds.labels(engine_type=engine_type).observe(duration_s)


def record_node_start(node_type: str) -> None:
    pass


def record_node_success(node_type: str, duration_s: float) -> None:
    node_executions_total.labels(node_type=node_type, status="SUCCESS").inc()
    node_execution_duration_seconds.labels(node_type=node_type).observe(duration_s)


def record_node_failure(node_type: str, duration_s: float) -> None:
    node_executions_total.labels(node_type=node_type, status="FAILED").inc()
    node_execution_duration_seconds.labels(node_type=node_type).observe(duration_s)


def record_node_retry(node_type: str) -> None:
    node_retries_total.labels(node_type=node_type).inc()


def record_resume(status: str) -> None:
    resume_total.labels(status=status).inc()


def record_orphaned_count(count: int) -> None:
    orphaned_executions_gauge.set(count)


def setup_instrumentator(app: FastAPI) -> Instrumentator:
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
    )
    instrumentator.add(
        metrics.request_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    ).add(
        metrics.response_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    ).add(
        metrics.latency(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    ).add(
        metrics.requests(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)
    return instrumentator
