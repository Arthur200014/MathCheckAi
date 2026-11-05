"""Opt-in OpenTelemetry instrumentation for MathCheck AI.

The existing JSONL audit logs remain untouched. This module never records
student text, OCR content, image bytes or prompts as span attributes.
"""
from __future__ import annotations

import json
import logging
import os
import time
from functools import wraps
from contextlib import contextmanager
from typing import Iterator

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

_LOGGER = logging.getLogger("mathcheck.telemetry")
_LOGGER.setLevel(logging.INFO)
_LOGGER.propagate = False
_log_provider = None
_http_calls = None
_http_duration = None

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
    global _log_provider, _http_calls, _http_duration
    if _configured:
        return True
    if not otel_enabled():
        return False

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.metrics.view import View, ExplicitBucketHistogramAggregation
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
    # Default OTel histogram buckets are 0, 5, 10... in the instrument unit.
    # Our metrics are in seconds, so those defaults incorrectly estimate
    # millisecond requests as multi-second p95 latencies.
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
        views=[
            View(
                instrument_name="mathcheck.http.duration",
                aggregation=ExplicitBucketHistogramAggregation(boundaries=[
                    0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1,
                    0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 900,
                ]),
            ),
            View(
                instrument_name="mathcheck.stage.duration",
                aggregation=ExplicitBucketHistogramAggregation(boundaries=[
                    0.01, 0.025, 0.05, 0.1, 0.15, 0.25, 0.5, 1,
                    2.5, 5, 10, 30, 60, 120, 300, 900,
                ]),
            ),
        ],
    )
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
    _http_calls = meter.create_counter(
        "mathcheck.http.requests", description="HTTP requests served", unit="1",
    )
    _http_duration = meter.create_histogram(
        "mathcheck.http.duration", description="HTTP request duration", unit="s",
    )

    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(
        OTLPLogExporter(endpoint=endpoint, insecure=insecure, timeout=5),
    ))
    _log_provider = log_provider
    _LOGGER.addHandler(LoggingHandler(level=logging.INFO, logger_provider=log_provider))

    # The HTTP logger is inner middleware and the OTel FastAPI tracer is outer.
    # This keeps logs correlated to their current HTTP trace.
    app.add_middleware(HttpTelemetryMiddleware, routes=tuple(app.routes))
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
    with tracer.start_as_current_span(
        f"langgraph.{stage}", record_exception=False, set_status_on_exception=False,
    ) as span:
        span.set_attribute("mathcheck.stage", stage)
        if review_id:
            span.set_attribute("mathcheck.review_id", review_id)
        try:
            yield
        except Exception as exc:
            span.add_event("stage.failed", {"exception.type": type(exc).__name__})
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


def emit_event(
    event: str, *, status: str = "done", stage: str = "",
    review_id: str = "", duration_seconds: float | None = None,
    error_type: str = "",
) -> None:
    """Export a small, explicitly whitelisted event as an OpenTelemetry log."""
    if not _configured:
        return
    row = {"event": event, "status": status}
    if stage:
        row["stage"] = stage
    if review_id:
        row["review_id"] = review_id
    if duration_seconds is not None:
        row["duration_seconds"] = round(max(0.0, duration_seconds), 4)
    if error_type:
        row["error_type"] = error_type
    _LOGGER.info(json.dumps(row, ensure_ascii=False))


def record_http_completion(*, method: str, route: str, status_code: int, duration: float) -> None:
    if not _configured:
        return
    attrs = {
        "method": method if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"} else "OTHER",
        "route": route,
        "status_class": f"{status_code // 100}xx",
    }
    _http_calls.add(1, attributes=attrs)
    _http_duration.record(max(0.0, duration), attributes=attrs)


class HttpTelemetryMiddleware:
    """ASGI middleware with bounded-cardinality route labels and no request bodies."""
    def __init__(self, app, routes=()):
        self.app = app
        # FastAPI executes user middleware before the router. Resolve labels
        # against the known templates, never from a raw URL (which can contain
        # personal information such as a student/review ID).
        self.routes = tuple(routes)

    def _route_template(self, scope) -> str:
        from starlette.routing import Match

        matched_route = scope.get("route")
        if matched_route is not None and getattr(matched_route, "path", None):
            return matched_route.path
        for route in self.routes:
            if getattr(route, "path", None) is None:
                continue
            match, _ = route.matches(scope)
            if match == Match.FULL:
                return str(route.path)
        return "unmatched"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        started = time.perf_counter()
        status_code = 500
        error_type = ""

        async def send_with_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            # Never use a raw URL path: it can include student IDs or review IDs.
            route = self._route_template(scope)
            method = str(scope.get("method", "OTHER"))
            elapsed = time.perf_counter() - started
            record_http_completion(
                method=method, route=route, status_code=status_code, duration=elapsed,
            )
            emit_event(
                "http.request", status=str(status_code), stage=route,
                duration_seconds=elapsed, error_type=error_type,
            )


def trace_ollama_call(func):
    """Nested OTel span around one Ollama call; never capture prompts or images."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        started = time.perf_counter()
        with trace.get_tracer("mathcheck.ollama").start_as_current_span(
            "ollama.chat", record_exception=False, set_status_on_exception=False,
        ) as span:
            span.set_attribute("mathcheck.llm.image_input", bool(kwargs.get("image_b64")))
            emit_event("ollama.started", status="started", stage="ollama")
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                span.add_event("ollama.failed", {"exception.type": type(exc).__name__})
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                emit_event(
                    "ollama.finished", status="error", stage="ollama",
                    duration_seconds=time.perf_counter() - started,
                    error_type=type(exc).__name__,
                )
                raise
            elapsed = time.perf_counter() - started
            span.set_attribute("mathcheck.llm.elapsed_seconds", elapsed)
            emit_event("ollama.finished", status="done", stage="ollama", duration_seconds=elapsed)
            return result

    return wrapper


def flush_telemetry() -> None:
    """Useful for short-lived demo scripts; the server exports in the background."""
    tracer = trace.get_tracer_provider()
    meter = metrics.get_meter_provider()
    for provider in (tracer, meter, _log_provider):
        if provider is not None and hasattr(provider, "force_flush"):
            provider.force_flush(timeout_millis=10000)
