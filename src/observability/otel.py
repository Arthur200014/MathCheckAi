"""Opt-in OpenTelemetry instrumentation for MathCheck AI.

The existing JSONL audit logs remain untouched. This module never records
student text, OCR content, image bytes or prompts as span attributes.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

_configured = False
_stage_calls = None
_stage_duration = None
_stage_errors = None
_completed_reviews = None


def otel_enabled() -> bool:
    return os.getenv("MATHCHECK_OTEL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def configure_otel(app) -> bool:
    """Configure OTLP exporters and FastAPI exactly once, when explicitly enabled."""
    global _configured, _stage_calls, _stage_duration, _stage_errors, _completed_reviews
    if _configured:
        return True
    if not otel_enabled():
        return False

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    insecure = endpoint.startswith("http://")
    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "mathcheck-ai"),
        "service.version": "0.2.5",
    })

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint, insecure=insecure, timeout=5),
    ))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=insecure, timeout=5),
        export_interval_millis=10000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    meter = meter_provider.get_meter("mathcheck.observability")
    _stage_calls = meter.create_counter(
        "mathcheck.stage.calls", description="Finished LangGraph stages", unit="1",
    )
    _stage_duration = meter.create_histogram(
        "mathcheck.stage.duration", description="LangGraph stage duration", unit="s",
    )
    _stage_errors = meter.create_counter(
        "mathcheck.stage.errors", description="Failed LangGraph stages", unit="1",
    )
    _completed_reviews = meter.create_counter(
        "mathcheck.reviews.completed", description="Reviews persisted successfully", unit="1",
    )

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls="^/health$",
    )
    _configured = True
    return True


@contextmanager
def stage_span(*, stage: str, review_id: str) -> Iterator[None]:
    """Create a real OTel child span for a LangGraph stage."""
    tracer = trace.get_tracer("mathcheck.langgraph")
    with tracer.start_as_current_span(f"langgraph.{stage}") as span:
        span.set_attribute("mathcheck.stage", stage)
        if review_id:
            span.set_attribute("mathcheck.review_id", review_id)
        try:
            yield
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise


def record_stage_completion(*, stage: str, status: str, duration: float) -> None:
    """Keep metrics low-cardinality: never attach per-student or per-review IDs."""
    if not _configured:
        return
    labels = {"stage": stage, "status": status}
    _stage_calls.add(1, attributes=labels)
    _stage_duration.record(max(0.0, duration), attributes=labels)
    if status == "error":
        _stage_errors.add(1, attributes={"stage": stage})
    if stage == "persist_review" and status == "done":
        _completed_reviews.add(1)
