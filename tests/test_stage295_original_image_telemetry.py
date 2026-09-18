import io
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.agents import vision as vision_mod
from src.llm import ollama_client


def test_vision_exposes_phase_telemetry(monkeypatch):
    def fake_call(**kwargs):
        return {
            "transcript_latex": "Ответ: б) -3\\pi/4",
            "steps": [],
            "confidence": 0.96,
            "uncertain_fragments": [],
            "_model": "fake-vlm",
            "_elapsed_seconds": 7.5,
            "_ollama_telemetry": {
                "total_seconds": 7.2,
                "load_seconds": 0.3,
                "prompt_eval_seconds": 2.0,
                "generation_seconds": 4.9,
                "prompt_tokens": 800,
                "output_tokens": 240,
                "prompt_tokens_per_second": 400.0,
                "generation_tokens_per_second": 48.98,
                "done_reason": "stop",
                "num_ctx": 16384,
                "custom_output_cap": False,
            },
        }

    monkeypatch.setattr(vision_mod, "ollama_chat_json", fake_call)
    out = vision_mod.vision_agent({"image_b64": "abc", "task_statement": "t"})
    assert out["vision_ollama_prompt_eval_seconds"] == 2.0
    assert out["vision_ollama_generation_seconds"] == 4.9
    assert out["vision_ollama_output_tokens"] == 240
    assert out["vision_num_ctx"] == 16384
    assert out["vision_num_predict_custom_cap"] is False


def test_invalid_json_error_keeps_ollama_telemetry(monkeypatch):
    raw_final = {
        "model": "fake",
        "message": {"content": ""},
        "done": True,
        "total_duration": 5_000_000_000,
        "load_duration": 500_000_000,
        "prompt_eval_count": 100,
        "prompt_eval_duration": 1_000_000_000,
        "eval_count": 200,
        "eval_duration": 3_000_000_000,
        "done_reason": "length",
    }

    class Sock:
        def settimeout(self, value): pass
    class Resp:
        status = 200
        def __init__(self):
            self.lines = iter([
                (json.dumps({"message": {"content": '{\"transcript_latex\":\"cut'}, "done": False}) + "\n").encode(),
                (json.dumps(raw_final) + "\n").encode(),
            ])
        def readline(self): return next(self.lines, b"")
    class Conn:
        def __init__(self, response): self.response=response; self.sock=Sock()
        def close(self): pass

    resp = Resp()
    conn = Conn(resp)
    monkeypatch.setattr(ollama_client, "_open_streaming_post", lambda **kwargs: (conn, resp))
    try:
        ollama_client.ollama_chat_json(
            system_prompt="s",
            user_prompt="u",
            image_b64="abc",
            num_ctx=16384,
            use_num_predict_limit=False,
        )
        assert False, "expected OllamaError"
    except ollama_client.OllamaError as exc:
        assert exc.telemetry["prompt_eval_seconds"] == 1.0
        assert exc.telemetry["generation_seconds"] == 3.0
        assert exc.telemetry["output_tokens"] == 200
        assert exc.telemetry["custom_output_cap"] is False
        assert exc.telemetry["done_reason"] == "length"


def test_api_source_sends_original_bytes_without_resize_or_recompression():
    api_source = Path(__file__).resolve().parents[1] / "src" / "api.py"
    text = api_source.read_text(encoding="utf-8")
    assert "base64.b64encode(image_bytes)" in text
    assert "save_pending_image(initial_state[\"review_id\"], image_bytes)" in text
    assert ".thumbnail(" not in text
    assert 'format="JPEG"' not in text
    assert '"image_preprocessing": "none-original-bytes"' in text
