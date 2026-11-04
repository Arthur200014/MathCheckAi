"""Run enabled OpenTelemetry wiring in an isolated interpreter (no Collector required)."""
import os
import subprocess
import sys


def test_enabled_otel_sdk_wires_all_signals():
    snippet = """
from fastapi import FastAPI
from src.observability.otel import (
    configure_otel, emit_event, record_http_completion, record_stage_completion, stage_span,
)
app = FastAPI()
assert configure_otel(app)
with stage_span(stage="test", review_id="r-test"):
    emit_event("stage.started", status="started", stage="test", review_id="r-test")
record_stage_completion(stage="test", status="done", duration=0.02)
record_http_completion(method="GET", route="/health", status_code=200, duration=0.01)
"""
    env = dict(os.environ)
    env["MATHCHECK_OTEL_ENABLED"] = "true"
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:9"
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        text=True,
        capture_output=True,
        env=env,
        timeout=40,
    )
    assert result.returncode == 0, result.stderr[-2500:]
