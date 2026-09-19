from src.agents import vision as vision_mod


def test_vision_uses_schema_and_local_step_split(monkeypatch):
    seen = {}

    def fake_call(**kwargs):
        seen.update(kwargs)
        return {
            "task_statement_latex": "test",
            "student_transcript_latex": "a) x=1\nб) x=2\nОтвет: a) 1; б) 2",
            "confidence": 0.97,
            "task_confidence": 0.97,
            "uncertain_fragments": [],
            "task_uncertain_fragments": [],
            "_model": "fake",
            "_elapsed_seconds": 1.2,
            "_ollama_telemetry": {"num_ctx": 16384, "custom_output_cap": True},
        }

    monkeypatch.setattr(vision_mod, "ollama_chat_json", fake_call)
    result = vision_mod.vision_agent({
        "image_b64": "abc",
        "task_statement": "test",
    })

    assert seen["response_schema"] == vision_mod.VISION_RESPONSE_SCHEMA
    assert seen["num_ctx"] == 16384
    assert seen["use_num_predict_limit"] is True
    assert seen["num_predict"] == 2048
    assert result["transcript_confirmed"] is False
    assert result["needs_confirmation"] is True
    assert result["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"
    assert result["confirmed_transcript"] == ""
    assert result["transcript_steps"]


def test_vision_prompt_forbids_duplicate_output(monkeypatch):
    seen = {}

    def fake_call(**kwargs):
        seen.update(kwargs)
        return {
            "task_statement_latex": "t",
            "student_transcript_latex": "Ответ: б) -3\\pi/4",
            "confidence": 0.95,
            "task_confidence": 0.95,
            "uncertain_fragments": [],
            "task_uncertain_fragments": [],
            "_ollama_telemetry": {},
        }

    monkeypatch.setattr(vision_mod, "ollama_chat_json", fake_call)
    vision_mod.vision_agent({"image_b64": "abc", "task_statement": "t"})
    prompt = seen["user_prompt"]
    assert "одну буквальную транскрипцию" in prompt
    assert "не повторяй уже переписанные строки" in prompt
    assert "не описывай рисунок" in prompt
    assert "строку `Ответ:`" in prompt
