"""The synthetic demo defaults to success, with failures opt-in only."""

from contextlib import contextmanager

import pytest

from scripts import demo_observability as demo


@pytest.mark.parametrize(
    ("args", "expected_failure"),
    [
        ([], False),
        (["--with-error"], True),
    ],
)
def test_demo_error_is_explicit_only(monkeypatch, capsys, args, expected_failure):
    monkeypatch.setenv("MATHCHECK_OTEL_ENABLED", "true")
    monkeypatch.setattr(demo, "configure_otel", lambda app: True)
    monkeypatch.setattr(demo, "flush_telemetry", lambda: None)
    monkeypatch.setattr(demo.time, "sleep", lambda seconds: None)

    stages = []
    events = []
    metrics = []

    @contextmanager
    def fake_stage_span(*, stage, review_id):
        stages.append(stage)
        yield

    monkeypatch.setattr(demo, "stage_span", fake_stage_span)
    monkeypatch.setattr(demo, "emit_event", lambda event, **kw: events.append((event, kw)))
    monkeypatch.setattr(
        demo, "record_stage_completion", lambda **kw: metrics.append(kw)
    )

    demo.main(args)

    assert len([s for s in stages if s.startswith("demo_")]) == (
        8 if expected_failure else 7
    )
    assert ("demo_failure" in stages) is expected_failure
    assert any(e == "demo.failure" for e, kw in events) is expected_failure
    assert any(m["status"] == "error" for m in metrics) is expected_failure
    assert len(metrics) == (8 if expected_failure else 7)
    assert all(m["status"] == "done" for m in metrics[:7])
    assert ("mode=with_error" if expected_failure else "mode=success") in capsys.readouterr().out
