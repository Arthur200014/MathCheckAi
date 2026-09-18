from src.agents import vision as vision_mod


def test_vision_uses_plain_json_mode_no_custom_output_cap_and_local_step_split(monkeypatch):
    seen = {}

    def fake_call(**kwargs):
        seen.update(kwargs)
        return {
            "transcript_latex": "a) x=1\nб) x=2\nОтвет: a) 1; б) 2",
            "steps": [],
            "confidence": 0.97,
            "uncertain_fragments": [],
            "_model": "fake",
            "_elapsed_seconds": 1.2,
            "_ollama_telemetry": {"num_ctx": 16384, "custom_output_cap": False},
        }

    monkeypatch.setattr(vision_mod, "ollama_chat_json", fake_call)
    result = vision_mod.vision_agent({
        "image_b64": "abc",
        "task_statement": "test",
    })

    assert seen["response_schema"] is None
    assert seen["num_ctx"] == 16384
    assert seen["use_num_predict_limit"] is False
    assert "num_predict" not in seen
    assert '"steps": []' in seen["user_prompt"]
    assert result["transcript_confirmed"] is False
    assert result["needs_confirmation"] is True
    assert result["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"
    assert result["confirmed_transcript"] == ""
    assert result["transcript_steps"]
    assert result["vision_elapsed_seconds"] == 1.2


def test_vision_prompt_forbids_duplicate_output(monkeypatch):
    seen = {}

    def fake_call(**kwargs):
        seen.update(kwargs)
        return {
            "transcript_latex": "Ответ: б) -3\\pi/4",
            "steps": [],
            "confidence": 0.95,
            "uncertain_fragments": [],
            "_ollama_telemetry": {},
        }

    monkeypatch.setattr(vision_mod, "ollama_chat_json", fake_call)
    vision_mod.vision_agent({"image_b64": "abc", "task_statement": "t"})
    prompt = seen["user_prompt"]
    assert "ОДИН РАЗ" in prompt
    assert "`steps` всегда []" in prompt
    assert "Не описывай рисунок словами" in prompt
    assert "Строку `Ответ:`" in prompt
