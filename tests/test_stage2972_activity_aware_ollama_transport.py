import json
import socket
from unittest.mock import patch

import pytest

from src.llm import ollama_client
from src.llm.ollama_client import OllamaError, ollama_chat_json


class FakeSocket:
    def __init__(self):
        self.timeouts = []
    def settimeout(self, value):
        self.timeouts.append(value)


class FakeConn:
    def __init__(self, response):
        self.response = response
        self.sock = FakeSocket()
        self.closed = False
    def close(self):
        self.closed = True


class FakeResponse:
    status = 200
    reason = "OK"
    def __init__(self, lines):
        self.lines = iter(lines)
    def readline(self):
        return next(self.lines, b"")
    def read(self):
        return b""


def _line(obj):
    return (json.dumps(obj) + "\n").encode()


def test_stream_finishes_and_combines_json(monkeypatch):
    lines = [
        _line({"message": {"content": '{"x":'}, "done": False}),
        _line({"message": {"content": "1}"}, "done": False}),
        _line({
            "model": "m",
            "message": {"content": ""},
            "done": True,
            "total_duration": 2_000_000_000,
            "load_duration": 100_000_000,
            "prompt_eval_count": 10,
            "prompt_eval_duration": 500_000_000,
            "eval_count": 20,
            "eval_duration": 1_000_000_000,
            "done_reason": "stop",
        }),
    ]
    conn = FakeConn(FakeResponse(lines))
    monkeypatch.setattr(ollama_client, "_open_streaming_post", lambda **kwargs: (conn, conn.response))
    out = ollama_chat_json(system_prompt="s", user_prompt="u", model="m", num_predict=20)
    assert out["x"] == 1
    assert out["_ollama_telemetry"]["transport_mode"] == "ndjson-stream-idle-timeout-emergency-ceiling"
    assert out["_ollama_telemetry"]["chunks_received"] == 3
    assert conn.closed is True


def test_total_deadline_stops_a_neverending_but_active_stream(monkeypatch):
    response = FakeResponse([
        _line({"message": {"content": "{"}, "done": False}),
        _line({"message": {"content": '"x":'}, "done": False}),
        _line({"message": {"content": "1"}, "done": False}),
    ])
    conn = FakeConn(response)
    monkeypatch.setattr(ollama_client, "_open_streaming_post", lambda **kwargs: (conn, response))
    # Started at 0; first loop 0.1, second loop 0.6 => total 0.5 exceeded.
    ticks = iter([0.0, 0.1, 0.1, 0.6, 0.6])
    monkeypatch.setattr(ollama_client.time, "perf_counter", lambda: next(ticks, 0.6))
    with pytest.raises(OllamaError) as ei:
        ollama_chat_json(system_prompt="s", user_prompt="u", model="m", timeout=0.5)
    assert ei.value.code == "OLLAMA_TOTAL_DEADLINE"
    assert "Ollama не ответил за отведённое время" not in str(ei.value)
    assert ei.value.telemetry["wall_seconds"] >= 0.5
    assert conn.closed is True


def test_idle_timeout_reports_real_progress_and_elapsed(monkeypatch):
    class TimeoutResponse(FakeResponse):
        def __init__(self):
            self.calls = 0
        def readline(self):
            self.calls += 1
            if self.calls == 1:
                return _line({"message": {"content": '{"x":'}, "done": False})
            raise socket.timeout("stalled")
    response = TimeoutResponse()
    conn = FakeConn(response)
    monkeypatch.setattr(ollama_client, "_open_streaming_post", lambda **kwargs: (conn, response))
    with pytest.raises(OllamaError) as ei:
        ollama_chat_json(system_prompt="s", user_prompt="u", model="m", timeout=30)
    assert ei.value.code == "OLLAMA_IDLE_TIMEOUT"
    assert ei.value.telemetry["chunks_received"] == 1
    assert ei.value.telemetry["partial_output_chars"] > 0
    assert ei.value.telemetry["wall_seconds"] >= 0
    assert "Ollama не ответил за отведённое время" not in str(ei.value)


def test_legacy_ollama_timeout_env_is_not_used(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("OLLAMA_VISION_TOTAL_TIMEOUT_SECONDS", "900")
    captured = {}
    final = FakeResponse([_line({
        "model": "m", "message": {"content": '{"ok":true}'}, "done": True,
        "total_duration": 1, "load_duration": 1, "prompt_eval_count": 1,
        "prompt_eval_duration": 1, "eval_count": 1, "eval_duration": 1,
        "done_reason": "stop",
    })])
    conn = FakeConn(final)
    def fake_open(**kwargs):
        captured.update(kwargs)
        return conn, final
    monkeypatch.setattr(ollama_client, "_open_streaming_post", fake_open)
    out = ollama_chat_json(system_prompt="s", user_prompt="u", image_b64="abc", model="m", use_num_predict_limit=False)
    assert out["ok"] is True
    assert captured["total_deadline_seconds"] == 900


def test_default_emergency_ceiling_is_900_for_vision_and_text(monkeypatch):
    monkeypatch.delenv("OLLAMA_VISION_TOTAL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OLLAMA_TEXT_TOTAL_TIMEOUT_SECONDS", raising=False)
    captured = []

    def one_response():
        return FakeResponse([_line({
            "model": "m", "message": {"content": '{"ok":true}'}, "done": True,
            "total_duration": 1, "load_duration": 1, "prompt_eval_count": 1,
            "prompt_eval_duration": 1, "eval_count": 1, "eval_duration": 1,
            "done_reason": "stop",
        })])

    def fake_open(**kwargs):
        response = one_response()
        conn = FakeConn(response)
        captured.append(kwargs["total_deadline_seconds"])
        return conn, response

    monkeypatch.setattr(ollama_client, "_open_streaming_post", fake_open)
    assert ollama_chat_json(system_prompt="s", user_prompt="u", model="m")["ok"] is True
    assert ollama_chat_json(system_prompt="s", user_prompt="u", image_b64="abc", model="m", use_num_predict_limit=False)["ok"] is True
    assert captured == [900.0, 900.0]


def test_partial_json_is_discarded_when_emergency_ceiling_fires(monkeypatch):
    response = FakeResponse([
        _line({"message": {"content": '{"transcript_latex":"partial'}, "done": False}),
        _line({"message": {"content": ' text'}, "done": False}),
    ])
    conn = FakeConn(response)
    monkeypatch.setattr(ollama_client, "_open_streaming_post", lambda **kwargs: (conn, response))
    ticks = iter([0.0, 0.1, 0.1, 1.1, 1.1])
    monkeypatch.setattr(ollama_client.time, "perf_counter", lambda: next(ticks, 1.1))

    with pytest.raises(OllamaError) as ei:
        ollama_chat_json(system_prompt="s", user_prompt="u", model="m", timeout=1.0)

    assert ei.value.code == "OLLAMA_TOTAL_DEADLINE"
    assert ei.value.telemetry["partial_output_chars"] > 0
    # The function raises rather than returning/parsing a partial JSON object.
    assert conn.closed is True
