from unittest.mock import patch

from src.agents.vision import _split_transcript_steps, vision_agent


def test_vision_requests_transcript_once_and_derives_steps_locally():
    fake = {
        "transcript_latex": r"x=1 \Rightarrow x=2 \quad Ответ: b) -3\pi/4",
        "steps": [],
        "confidence": 0.95,
        "uncertain_fragments": [],
        "_model": "test-vlm",
        "_elapsed_seconds": 1.2,
        "_ollama_telemetry": {"num_ctx": 16384, "custom_output_cap": False},
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake) as mocked:
        out = vision_agent({"image_b64": "abc", "task_statement": "test"})
    kwargs = mocked.call_args.kwargs
    assert kwargs["response_schema"] is None
    assert kwargs["use_num_predict_limit"] is False
    assert out["transcript_steps"]
    assert out["transcript"].count("Ответ") == 1


def test_local_step_splitter_does_not_change_math_text():
    text = r"a=1 \Rightarrow b=2 \quad Ответ: b) -3\pi/4"
    steps = _split_transcript_steps(text)
    assert any("a=1" in s for s in steps)
    assert any("b=2" in s for s in steps)
    assert any(r"-3\pi/4" in s for s in steps)
