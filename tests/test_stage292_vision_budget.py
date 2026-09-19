from unittest.mock import patch

from src.agents.vision import VISION_RESPONSE_SCHEMA, vision_agent


def test_vision_uses_structured_output_budget():
    fake = {
        "task_statement_latex": "test",
        "student_transcript_latex": "x=1",
        "confidence": 0.99,
        "task_confidence": 0.99,
        "uncertain_fragments": [],
        "task_uncertain_fragments": [],
        "_model": "qwen3-vl:4b-instruct",
        "_ollama_telemetry": {"num_ctx": 16384, "custom_output_cap": True},
    }
    state = {"task_statement": "test", "task_type": "ege_13", "image_b64": "ZmFrZQ=="}
    with patch("src.agents.vision.ollama_chat_json", return_value=fake) as mocked:
        result = vision_agent(state)
    kwargs = mocked.call_args.kwargs
    assert kwargs["num_ctx"] == 16384
    assert kwargs["response_schema"] == VISION_RESPONSE_SCHEMA
    assert kwargs["use_num_predict_limit"] is True
    assert kwargs["num_predict"] == 2048
    assert result["transcript"] == "x=1"
