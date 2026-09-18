from unittest.mock import patch
from src.agents.vision import vision_agent


def test_vision_no_longer_uses_small_output_budget():
    fake = {
        "transcript_latex": "x=1",
        "steps": [],
        "confidence": 0.99,
        "uncertain_fragments": [],
        "_model": "qwen3-vl:4b-instruct",
        "_ollama_telemetry": {"num_ctx": 16384, "custom_output_cap": False},
    }
    state = {"task_statement": "test", "task_type": "ege_13", "image_b64": "ZmFrZQ=="}
    with patch("src.agents.vision.ollama_chat_json", return_value=fake) as mocked:
        result = vision_agent(state)
    kwargs = mocked.call_args.kwargs
    assert kwargs["num_ctx"] == 16384
    assert kwargs["use_num_predict_limit"] is False
    assert "num_predict" not in kwargs
    assert result["transcript"] == "x=1"
