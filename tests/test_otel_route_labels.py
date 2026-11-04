"""Regression tests for safe, recognizable HTTP route labels."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.observability import otel


def test_http_metric_routes_have_templates_not_user_supplied_ids(monkeypatch):
    events = []
    metrics = []
    monkeypatch.setattr(otel, "record_http_completion", lambda **kwargs: metrics.append(kwargs))
    monkeypatch.setattr(otel, "emit_event", lambda *args, **kwargs: events.append(kwargs))

    app = FastAPI()

    @app.get("/api/reviews/{review_id}")
    def get_review(review_id: str):
        return {"found": bool(review_id)}

    @app.get("/api/task-types")
    def task_types():
        return {"types": []}

    app.add_middleware(otel.HttpTelemetryMiddleware, routes=tuple(app.routes))
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/api/task-types").status_code == 200
        assert client.get("/api/reviews/secret-student-123").status_code == 200
        assert client.get("/unknown/student-345").status_code == 404

    by_path = [m["route"] for m in metrics]
    assert by_path == [
        "/docs",
        "/api/task-types",
        "/api/reviews/{review_id}",
        "unmatched",
    ]
    assert all("secret-student-123" not in m["route"] for m in metrics)
    assert all("student-345" not in str(e) for e in events)
