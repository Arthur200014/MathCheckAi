"""Unit tests for the safe HTTP traffic generator."""
from scripts import demo_http_load as app


def test_http_generator_requests_only_known_safe_endpoints(monkeypatch):
    seen = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, count):
            return b"ok"

    def fetch(url, timeout):
        seen.append(url)
        return Response()

    monkeypatch.setattr(app, "urlopen", fetch)
    monkeypatch.setattr(app.time, "sleep", lambda interval: None)
    app.main(["--requests", "9", "--interval", "0"])

    assert seen == [
        "http://127.0.0.1:8000" + app.ENDPOINTS[i % len(app.ENDPOINTS)]
        for i in range(9)
    ]
