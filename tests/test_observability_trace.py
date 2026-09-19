import json

from src.observability import runtime


def test_trace_span_is_written(tmp_path, monkeypatch):
    trace_path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(runtime, "OBS_DIR", tmp_path)
    monkeypatch.setattr(runtime, "TRACE_PATH", trace_path)

    span = runtime.start_trace_span(review_id="review-1", stage="solver")
    runtime.finish_trace_span(span, status="done")

    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["event"] == "span_start"
    assert rows[1]["event"] == "span_end"
    assert rows[0]["trace_id"] == "review-1"
    assert rows[1]["trace_id"] == "review-1"
    assert rows[0]["span_id"] == rows[1]["span_id"]
    assert rows[1]["stage"] == "solver"
    assert rows[1]["status"] == "done"
    assert rows[1]["duration_seconds"] >= 0


def test_observability_status_has_all_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "LOG_PATH", tmp_path / "llm_calls.jsonl")
    monkeypatch.setattr(runtime, "TRACE_PATH", tmp_path / "traces.jsonl")
    monkeypatch.setattr(runtime, "ALERT_PATH", tmp_path / "alerts.jsonl")

    status = runtime.observability_status()
    assert "json_logs" in status
    assert "traces" in status
    assert "alerts" in status
    assert "slow_agent_threshold_seconds" in status
