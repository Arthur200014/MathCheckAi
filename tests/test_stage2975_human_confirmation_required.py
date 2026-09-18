from unittest.mock import patch

from src.agents.vision import vision_agent


def test_photo_ocr_never_auto_confirms_even_at_perfect_model_confidence():
    fake = {
        "transcript_latex": r"x=\\frac{\\pi}{2}+2\\pi n",
        "steps": [],
        "confidence": 1.0,
        "uncertain_fragments": [],
        "_model": "fake-vlm",
        "_elapsed_seconds": 0.1,
        "_ollama_telemetry": {},
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake):
        out = vision_agent({"image_b64": "abc", "task_statement": "test"})

    assert out["transcript"]
    assert out["original_transcript"] == out["transcript"]
    assert out["confirmed_transcript"] == ""
    assert out["needs_confirmation"] is True
    assert out["transcript_confirmed"] is False
    assert out["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"


def test_ocr_uncertainty_is_metadata_not_a_scoring_gate():
    fake = {
        "transcript_latex": r"x=\\frac{\\pi}{4}+2\\pi n",
        "steps": [],
        "confidence": 0.25,
        "uncertain_fragments": [r"\\frac{\\pi}{4}"],
        "_model": "fake-vlm",
        "_ollama_telemetry": {},
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake):
        out = vision_agent({"image_b64": "abc", "task_statement": "test"})

    assert out["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"
    assert out["transcript_confidence"] == 0.25
    assert out["uncertain_fragments"]


def test_source_code_contains_photo_confirmation_hard_gate():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    graph_src = (root / "src" / "graph.py").read_text(encoding="utf-8")
    api_src = (root / "src" / "api.py").read_text(encoding="utf-8")
    assert 'state.get("human_confirmation_required", False)' in graph_src
    assert '"human_confirmation_required": True' in api_src
    assert '"transcript_confirmation_source": "human"' in api_src
