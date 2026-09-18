from unittest.mock import patch

from src.agents import reviewer as reviewer_module
from src.agents.grader import grader_agent
from src.agents.vision import _detect_suspicious_ocr_fragments, vision_agent
from src.task_registry import get_task_profile
from src.tools.ege13_report import normalize_step_assessments
from src.tools.solution_steps import split_solution_step_texts


TASK = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."


def _grader_state(transcript: str):
    profile = get_task_profile("ege_13")
    return {
        "task_type": "ege_13",
        "task_statement": TASK,
        "task_profile": profile.model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": transcript,
        "reference_answer_part_a_verified": "verified",
        "reference_verified_families": [
            {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
            {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
            {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_b_verified": "verified",
    }


def test_grader_single_call_has_no_output_cap_and_no_score_request():
    transcript = r"""a) ...
Ответ: а) x=...; б) -\frac{11\pi}{4}, -\frac{9\pi}{4}, -\frac{3\pi}{2}"""
    fake = {
        "can_grade": True,
        "part_a_status": "correct",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": False,
        "confidence": 0.98,
        "student_machine_spec": {
            "general_solution_families": [
                {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
                {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
                {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
            ],
            "selected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        },
        "issue_steps": [],
        "_model": "test-grader",
        "_elapsed_seconds": 1.2,
        "_ollama_telemetry": {"partial_output_chars": 700, "output_tokens": 180, "done_reason": "stop"},
    }
    with patch("src.agents.grader.ollama_chat_json", return_value=fake) as mocked:
        out = grader_agent(_grader_state(transcript))

    assert mocked.call_count == 1
    kwargs = mocked.call_args.kwargs
    assert kwargs["use_num_predict_limit"] is False
    assert "num_predict" not in kwargs
    assert "НЕ выставляй балл" in kwargs["user_prompt"]
    assert out["grader_retry_used"] is False
    assert out["grader_score_source"] == "deterministic_ege13_rubric"
    assert out["grader_proposed_score_llm"] == -1


def test_sparse_issue_rows_expand_deterministically_for_report():
    steps = [
        {"step_id": "S1", "text": "first"},
        {"step_id": "S2", "text": "second"},
        {"step_id": "S3", "text": "third"},
    ]
    rows = normalize_step_assessments(
        steps,
        [{"step_id": "S2", "status": "incorrect", "comment": "Ошибка преобразования."}],
        sparse_issues=True,
    )
    assert [r["status"] for r in rows] == ["correct", "incorrect", "correct"]
    assert rows[0]["comment"] == "Ошибок в этом шаге не обнаружено."


def test_step_parser_drops_ocr_connector_and_merges_divide_by_pi_annotation():
    text = r"""\sin x-1=0 \quad \text{unu} \quad 2\sin x+\sqrt2=0
-3\pi \le x \le -\frac{3\pi}{2} \quad / : \pi
-3 \le x/\pi \le -3/2"""
    steps = split_solution_step_texts(text)
    assert not any("unu" in s for s in steps)
    assert not any(s.strip() == r"/ : \pi" for s in steps)
    assert any(r"/ : \pi" in s for s in steps)


def test_vision_detects_obvious_text_ocr_garbage_and_forces_confirmation():
    assert _detect_suspicious_ocr_fragments(r"\sin x=1 \quad \text{unu} \quad x=\pi/2") == [r"\text{unu}"]
    fake = {
        "transcript_latex": r"\sin x=1 \quad \text{unu} \quad x=\pi/2",
        "steps": [],
        "confidence": 0.95,
        "uncertain_fragments": [],
        "_model": "vision-test",
        "_elapsed_seconds": 1.0,
        "_ollama_telemetry": {},
    }
    with patch("src.agents.vision.ollama_chat_json", return_value=fake):
        out = vision_agent({"image_b64": "abc", "task_statement": TASK})
    assert out["needs_confirmation"] is True
    assert out["transcript_confirmed"] is False
    assert out["status"] == "NEEDS_TRANSCRIPT_CONFIRMATION"
    assert r"\text{unu}" in out["uncertain_fragments"]
    assert out["transcript_confidence"] == 0.95


def test_reviewer_runtime_contract_is_one_call_without_output_cap(monkeypatch):
    state = {
        "task_type": "ege_13",
        "task_statement": TASK,
        "confirmed_transcript": "solution",
        "grader_ok": True,
        "grader_manual_review_required": False,
        "grader_part_a_status": "correct",
        "grader_part_b_status": "correct",
        "grader_error_class": "none",
        "grader_part_a_equivalent": True,
        "grader_part_b_roots_match": True,
        "grader_conflicts": [],
        "reference_verification_ok": True,
        "solver_ok": True,
        "solver_fallback_used": False,
        "draft_score": 2,
        "task_max_score": 2,
        "errors": [],
        "warnings": [],
    }
    fake = {
        "consistent": True,
        "manual_review_required": False,
        "confidence": 0.99,
        "score_agrees": True,
        "reason_codes": [],
        "_model": "reviewer-test",
        "_elapsed_seconds": 0.5,
        "_ollama_telemetry": {"partial_output_chars": 120, "output_tokens": 35, "done_reason": "stop"},
    }
    seen = []
    def call(**kwargs):
        seen.append(kwargs)
        return fake
    monkeypatch.setattr(reviewer_module, "ollama_chat_json", call)
    out = reviewer_module.reviewer_agent(state)
    assert len(seen) == 1
    assert seen[0]["use_num_predict_limit"] is False
    assert "num_predict" not in seen[0]
    assert out["final_score"] == 2
    assert out["reviewer_retry_used"] is False
    assert out["reviewer_score_source"] == "deterministic_grader_rubric_audited_by_reviewer"


def test_invalid_json_telemetry_keeps_raw_preview(monkeypatch):
    import json
    from src.llm import ollama_client
    from src.llm.ollama_client import OllamaError

    class Sock:
        def settimeout(self, value):
            pass
    class Resp:
        status = 200
        def __init__(self):
            self.lines = iter([
                (json.dumps({"message": {"content": '{"broken":'}, "done": False}) + "\n").encode(),
                (json.dumps({"model": "m", "message": {"content": ""}, "done": True, "total_duration": 1, "load_duration": 1, "prompt_eval_count": 1, "prompt_eval_duration": 1, "eval_count": 1, "eval_duration": 1, "done_reason": "stop"}) + "\n").encode(),
            ])
        def readline(self):
            return next(self.lines, b"")
        def read(self):
            return b""
    class Conn:
        def __init__(self, response):
            self.response = response
            self.sock = Sock()
        def close(self):
            pass
    response = Resp()
    conn = Conn(response)
    monkeypatch.setattr(ollama_client, "_open_streaming_post", lambda **kwargs: (conn, response))
    try:
        ollama_client.ollama_chat_json(system_prompt="s", user_prompt="u", model="m", use_num_predict_limit=False)
        assert False, "expected invalid JSON"
    except OllamaError as exc:
        assert exc.code == "OLLAMA_INVALID_JSON"
        assert exc.telemetry["raw_output_length"] > 0
        assert '{"broken":' in exc.telemetry["raw_output_preview"]
