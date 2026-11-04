"""OpenTelemetry smoke checks: the disabled default must be harmless."""
import pytest
from fastapi import FastAPI

from src.observability import otel


def test_otel_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MATHCHECK_OTEL_ENABLED", raising=False)
    assert not otel.otel_enabled()
    assert otel.configure_otel(FastAPI()) is False


def test_stage_span_is_safe_without_collector():
    with otel.stage_span(stage="solver", review_id="r-local"):
        pass


def test_stage_span_preserves_exceptions():
    with pytest.raises(ValueError, match="example"):
        with otel.stage_span(stage="vision", review_id="r-test"):
            raise ValueError("example")


def test_metrics_are_noop_when_disabled():
    otel.record_stage_completion(stage="solver", status="done", duration=1.25)
