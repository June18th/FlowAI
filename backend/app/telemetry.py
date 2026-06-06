from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, SpanContext, set_span_in_context

from app.config import settings

_initialized = False
_active_span: ContextVar[SpanContext | None] = ContextVar("active_span", default=None)


def setup_telemetry(app) -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    if not settings.otel_enabled:
        return

    resource = Resource.create({
        SERVICE_NAME: settings.otel_service_name,
        "deployment.environment": settings.otel_environment,
    })

    provider = TracerProvider(resource=resource)

    # OTLP exporter (Jaeger, Tempo, Grafana Cloud, etc.)
    if settings.otel_exporter_otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Console exporter for local dev
    if settings.otel_console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    # Instrument FastAPI (auto-creates spans for HTTP requests)
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,live,ready,metrics,/docs,/redoc,/openapi.json",
    )

    # Inject trace context into structlog
    _patch_structlog()


def _patch_structlog() -> None:
    """Ensure structlog picks up trace_id and span_id from OTel context."""
    import structlog

    old_processors = structlog.get_config().get("processors", [])
    if old_processors:
        # Insert after the renderer but before the last processor
        insert_at = max(0, len(old_processors) - 1)
        old_processors.insert(insert_at, _otel_event_processor)
        structlog.configure(processors=old_processors)


def _otel_event_processor(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    from app.middleware.correlation import get_request_id
    req_id = get_request_id()
    if req_id:
        event_dict["request_id"] = req_id
    return event_dict


def get_tracer(name: str = "flowagent"):
    return trace.get_tracer(name)
