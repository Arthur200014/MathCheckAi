from pathlib import Path
from unittest.mock import patch

from src.agents.vision import vision_agent

ROOT = Path(__file__).resolve().parents[1]


def test_vision_extracts_task_and_solution_in_one_call_and_requires_human_confirmation():
    fake = {
        "task_statement_latex": r"а) Решите sin x=1. б) Отберите корни на [0;2\pi].",
        "student_transcript_latex": r"\sin x=1\\x=\frac{\pi}{2}+2\pi n",
        "confidence": 0.98,
        "task_confidence": 0.97,
        "uncertain_fragments": [],
        "task_uncertain_fragments": [],
        "_model": "fake-vlm",
        "_elapsed_seconds": 0.1,
        "_ollama_telemetry": {},
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake) as call:
        out = vision_agent({"image_b64": "abc", "task_statement": ""})

    assert call.call_count == 1
    assert out["detected_task_statement"].startswith("а) Решите")
    assert out["original_task_statement"] == out["detected_task_statement"]
    assert out["confirmed_task_statement"] == ""
    assert "\\sin x=1" in out["transcript"]
    assert out["needs_confirmation"] is True
    assert out["transcript_confirmed"] is False
    assert out["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"


def test_vision_does_not_invent_missing_task_statement():
    fake = {
        "task_statement_latex": "",
        "student_transcript_latex": r"x=\frac{\pi}{2}+2\pi n",
        "confidence": 0.95,
        "task_confidence": 0.0,
        "uncertain_fragments": [],
        "task_uncertain_fragments": [],
        "_model": "fake-vlm",
        "_ollama_telemetry": {},
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake):
        out = vision_agent({"image_b64": "abc", "task_statement": ""})

    assert out["detected_task_statement"] == ""
    assert out["transcript"]
    assert out["needs_confirmation"] is True


def test_web_ui_uses_one_photo_and_two_editable_confirmation_fields():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="taskOcrText"' in html
    assert 'id="ocrText"' in html
    assert "confirmed_task_statement" in html
    assert "original_task_statement" in html
    assert "Условие отдельно вводить не нужно" in html
    assert "fd.append('task_statement'" not in html


def test_api_confirmation_promotes_human_confirmed_task_statement_to_authoritative_task():
    source = (ROOT / "src" / "api.py").read_text(encoding="utf-8")
    assert 'confirmed_statement = (payload.confirmed_task_statement or payload.task_statement).strip()' in source
    assert '"task_statement": confirmed_statement' in source
    assert '"confirmed_task_statement": confirmed_statement' in source
    assert '"task_statement_confirmation_source": "human"' in source
    assert '"single_photo_extracts_student_work": True' in source
