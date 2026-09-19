from unittest.mock import patch

from src.agents.vision import evaluate_transcript_gate, vision_agent
from src.graph import route_after_vision


def test_high_confidence_photo_ocr_still_requires_human_confirmation():
    gate = evaluate_transcript_gate("x=1", 0.99, [])
    assert gate["needs_confirmation"] is True
    assert gate["transcript_confirmed"] is False
    assert gate["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"


def test_uncertain_fragment_forces_confirmation_even_at_high_confidence():
    gate = evaluate_transcript_gate("x=1", 0.97, ["x or y"])
    assert gate["needs_confirmation"] is True
    assert gate["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"


def test_medium_confidence_forces_confirmation():
    gate = evaluate_transcript_gate("x=1", 0.75, [])
    assert gate["needs_confirmation"] is True
    assert gate["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"


def test_low_confidence_nonempty_ocr_is_still_editable_by_human():
    gate = evaluate_transcript_gate("x=1", 0.20, [])
    assert gate["needs_confirmation"] is True
    assert gate["transcript_confirmed"] is False
    assert gate["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"


def test_empty_transcript_forces_manual_review():
    gate = evaluate_transcript_gate("", 0.99, [])
    assert gate["status"] == "MANUAL_REVIEW_REQUIRED"


def test_real_vision_ignores_model_needs_confirmation_field():
    fake = {
        "transcript_latex": r"\\sin x = \\frac12",
        "steps": [r"\\sin x = \\frac12"],
        "confidence": 0.75,
        "uncertain_fragments": [],
        "needs_confirmation": False,
        "_model": "qwen3-vl:4b-instruct",
    }
    state = {
        "task_statement": "test",
        "task_type": "ege_13",
        "image_b64": "ZmFrZQ==",
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake):
        result = vision_agent(state)

    assert result["needs_confirmation"] is True
    assert result["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"
    assert result["transcript_confirmed"] is False


def test_vision_uses_strict_schema_and_bounded_context():
    fake = {
        "task_statement_latex": "",
        "student_transcript_latex": "x=1",
        "confidence": 0.9,
        "task_confidence": 0.0,
        "uncertain_fragments": [],
        "task_uncertain_fragments": [],
        "_model": "qwen3-vl:4b-instruct",
        "_elapsed_seconds": 1.0,
        "_ollama_telemetry": {},
    }
    state = {
        "task_statement": "",
        "task_type": "ege_13",
        "image_b64": "ZmFrZQ==",
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake) as call:
        result = vision_agent(state)

    kwargs = call.call_args.kwargs
    assert kwargs["response_schema"]["additionalProperties"] is False
    assert "student_transcript_latex" in kwargs["response_schema"]["required"]
    assert kwargs["num_ctx"] == 8192
    assert kwargs["num_predict"] == 3072
    assert kwargs["use_num_predict_limit"] is True
    assert result["transcript"] == "x=1"


def test_graph_router_stops_unconfirmed_transcript():
    assert route_after_vision({"needs_confirmation": True, "transcript_confirmed": False}) == "stop_for_confirmation"
    assert route_after_vision({"needs_confirmation": False, "transcript_confirmed": True}) == "solver"
