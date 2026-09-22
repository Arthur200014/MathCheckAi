from unittest.mock import patch

from src.agents.grader import _apply_rubric, grader_agent
from src.task_registry import get_task_profile
from src.tools.ege13_student import verify_ege13_student_machine_spec

TASK = "а) Решите уравнение: 2sin(x - π/6) - 2√3 cos(π/2 - x) = 0. б) Найдите все корни этого уравнения, принадлежащие отрезку [-6π; -9π/2]."
TRANSCRIPT = r"""13. а) 2\sin\left(x-\frac{\pi}{6}\right)-2\sqrt{3}\cos\left(\frac{\pi}{2}-x\right)=0
\cos x+\sqrt{3}\sin x=0
\tan x=-\frac{1}{\sqrt{3}}
x=-\frac{\pi}{6}+\pi n, n\in\mathbb{Z}
б) n=-5, x=-\frac{31\pi}{6}
Ответ: а) x=-\frac{\pi}{6}+\pi n; б) -\frac{31\pi}{6}"""


def _three_family_transcript() -> str:
                                                                                  
                                                 
    return r"""a) x=-\frac{\pi}{4}+2\pi k,\ k\in\mathbb{Z}; x=\frac{\pi}{2}+2\pi n,\ n\in\mathbb{Z}; x=-\frac{3\pi}{4}+2\pi m,\ m\in\mathbb{Z}
б) x_1=-\frac{11\pi}{4}
x_2=-\frac{9\pi}{4}
x_3=-\frac{3\pi}{2}"""


def _reference_three_families():
    return [
        {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
        {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
        {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
    ]


def _semantic_ok(*, manual_review_required=False):
    return {
        "can_grade": True,
        "part_a_status": "correct",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": manual_review_required,
        "confidence": 0.98,
        "checked_step_ids": [],
        "issue_steps": [],
        "_model": "test-grader",
    }


def test_student_machine_spec_equivalent_even_if_reference_is_canonicalized():
    out = verify_ege13_student_machine_spec(
        {
            "general_solution_families": [{"expression": "-pi/6 + pi*n", "parameter": "n"}],
            "selected_roots": ["-31*pi/6"],
        },
        task_statement=TASK,
        reference_families=[{"expression": "pi*(n - 1/6)", "parameter": "n"}],
        expected_roots=["-31*pi/6"],
    )
    assert out.part_a_equivalent is True
    assert out.part_b_matches is True
    assert out.errors == []


def test_rubric_correct_both_parts_is_two():
    score, reason, conflicts = _apply_rubric(
        llm={
            "can_grade": True,
            "part_a_status": "correct",
            "part_b_status": "correct",
            "overall_sequence_correct_both_parts": True,
            "error_class": "none",
            "manual_review_required": False,
            "confidence": 0.98,
        },
        part_a_equivalent=True,
        part_b_matches=True,
    )
    assert score == 2
    assert reason == "both_parts_correct_and_justified"
    assert conflicts == []


def test_rubric_correct_a_wrong_b_is_one():
    score, _, _ = _apply_rubric(
        llm={
            "can_grade": True,
            "part_a_status": "correct",
            "part_b_status": "incorrect",
            "overall_sequence_correct_both_parts": False,
            "error_class": "root_selection_error",
            "manual_review_required": False,
            "confidence": 0.95,
        },
        part_a_equivalent=True,
        part_b_matches=False,
    )
    assert score == 1


def test_rubric_substantive_error_in_a_is_zero():
    score, _, _ = _apply_rubric(
        llm={
            "can_grade": True,
            "part_a_status": "substantive_error",
            "part_b_status": "incorrect",
            "overall_sequence_correct_both_parts": False,
            "error_class": "substantive_math_error",
            "manual_review_required": False,
            "confidence": 0.95,
        },
        part_a_equivalent=False,
        part_b_matches=False,
    )
    assert score == 0


def test_real_grader_correct_current_case_scores_two_and_does_not_return_full_criteria():
    profile = get_task_profile("ege_13")
    state = {
        "task_type": "ege_13",
        "task_statement": TASK,
        "task_profile": profile.model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": TRANSCRIPT,
        "reference_answer_part_a_verified": r"x = -\frac{\pi}{6}+\pi n",
        "reference_verified_families": [{"expression": "pi*(n - 1/6)", "parameter": "n"}],
        "reference_expected_roots": ["-31*pi/6"],
        "reference_answer_part_b_verified": r"-\frac{31\pi}{6}",
    }
    with patch("src.agents.grader.ollama_chat_json", return_value=_semantic_ok()):
        out = grader_agent(state)

    assert out["grader_ok"] is True
    assert out["draft_score"] == 2
    assert out["grader_part_a_equivalent"] is True
    assert out["grader_part_b_roots_match"] is True
    assert out["criteria_loaded"] is True
    assert "criteria" not in out


def test_real_grader_diagram_error_overrides_text_only_score_two_to_one():
    task = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    profile = get_task_profile("ege_13")
    state = {
        "task_type": "ege_13",
        "task_statement": task,
        "task_profile": profile.model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": _three_family_transcript(),
        "reference_answer_part_a_verified": "verified",
        "reference_verified_families": _reference_three_families(),
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_b_verified": "verified",
        "diagram_method_used": True,
        "diagram_verification_status": "DIAGRAM_INVALID",
        "diagram_part_b_valid": False,
        "diagram_verification_issues": [
            "diagram_point_value_mismatch:id=1:value=-9*pi/4:drawn=lower_left:mathematical=lower_right",
            "diagram_point_value_mismatch:id=2:value=-11*pi/4:drawn=lower_right:mathematical=lower_left",
        ],
        "diagram_verification_results": ["diagram_claimed_root_set_matches_reference:true"],
    }
    with patch("src.agents.grader.ollama_chat_json", return_value=_semantic_ok()):
        out = grader_agent(state)

    assert out["grader_ok"] is True
    assert out["draft_score"] == 1
    assert out["grader_part_a_equivalent"] is True
    assert out["grader_part_b_roots_match"] is True
    assert out["grader_part_b_status"] == "incorrect"
    assert out["grader_error_class"] == "diagram_selection_error"
    assert out["grader_diagram_override_applied"] is True
    assert out["grader_rubric_reason"] == "part_a_correct_part_b_diagram_error"


def test_real_grader_unreadable_diagram_but_confirmed_math_still_scores_two():
    task = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    profile = get_task_profile("ege_13")
    state = {
        "task_type": "ege_13",
        "task_statement": task,
        "task_profile": profile.model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": _three_family_transcript(),
        "reference_answer_part_a_verified": "verified",
        "reference_verified_families": _reference_three_families(),
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_b_verified": "verified",
        "diagram_method_used": True,
        "diagram_verification_status": "DIAGRAM_UNVERIFIED_AFTER_REINSPECTION",
        "diagram_part_b_valid": None,
        "diagram_verification_issues": ["uncertain:handwritten labels unreadable"],
        "diagram_verification_results": ["diagram_final_unverified_no_automatic_penalty"],
    }
    with patch(
        "src.agents.grader.ollama_chat_json",
        return_value=_semantic_ok(manual_review_required=True),
    ):
        out = grader_agent(state)

    assert out["grader_ok"] is True
    assert out["grader_manual_review_required"] is False
    assert out["draft_score"] == 2
    assert out["grader_diagram_unverified_ignored_for_score"] is True
    assert out["grader_diagram_override_applied"] is False
    assert out["grader_rubric_reason"] == "both_parts_correct_unreadable_diagram_no_proven_error"
    assert "diagram_unverified_no_penalty_no_proven_student_error" in out["grader_evidence"]


def test_explicit_final_answer_lock_prevents_grader_from_repairing_case_b():
    task = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    profile = get_task_profile("ege_13")
    transcript = r"""13. а) решение корректно
x = (-1)^k*(-\frac{\pi}{4})+\pi k, k\in\mathbb{Z}; x=\frac{\pi}{2}+2\pi n, n\in\mathbb{Z}
б) (1): -\frac{\pi}{4}-2\pi=-\frac{9\pi}{4}; (2): -\frac{3\pi}{4}-2\pi=-\frac{11\pi}{4}; (3): -\frac{3\pi}{2}
Ответ: а) x = ...; б) -\frac{3\pi}{4}, -\frac{11\pi}{4}, -\frac{9\pi}{4}"""
    state = {
        "task_type": "ege_13",
        "task_statement": task,
        "task_profile": profile.model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": transcript,
        "reference_answer_part_a_verified": "verified",
        "reference_verified_families": _reference_three_families(),
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_b_verified": "verified",
        "diagram_method_used": True,
        "diagram_verification_status": "DIAGRAM_UNVERIFIED_AFTER_REINSPECTION",
        "diagram_part_b_valid": None,
    }
    with patch("src.agents.grader.ollama_chat_json", return_value=_semantic_ok()):
        out = grader_agent(state)

    assert out["grader_student_answer_lock_applied"] is True
    assert set(out["grader_student_final_answer_part_b"]) == {"-3*pi/4", "-11*pi/4", "-9*pi/4"}
    assert out["grader_part_b_roots_match"] is False
    assert out["grader_part_b_status"] == "incorrect"
    assert out["grader_error_class"] == "root_selection_error"
    assert out["draft_score"] == 1
    assert out["grader_rubric_reason"] == "part_a_correct_part_b_not_fully_correct"


def test_grader_never_retries_malformed_json_and_preserves_error_telemetry():
    from src.llm.ollama_client import OllamaError

    profile = get_task_profile("ege_13")
    state = {
        "task_type": "ege_13",
        "task_statement": TASK,
        "task_profile": profile.model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": TRANSCRIPT,
        "reference_answer_part_a_verified": r"x = -\frac{\pi}{6}+\pi n",
        "reference_verified_families": [{"expression": "pi*(n - 1/6)", "parameter": "n"}],
        "reference_expected_roots": ["-31*pi/6"],
        "reference_answer_part_b_verified": r"-\frac{31\pi}{6}",
    }
    failure = OllamaError(
        "Модель вернула невалидный JSON: truncated",
        telemetry={
            "wall_seconds": 42.5,
            "partial_output_chars": 1234,
            "output_tokens": 321,
            "done_reason": "length",
            "model": "test-grader",
        },
        code="OLLAMA_INVALID_JSON",
    )
    with patch("src.agents.grader.ollama_chat_json", side_effect=failure) as mocked:
        out = grader_agent(state)

    assert mocked.call_count == 1
    assert out["grader_retry_used"] is False
    assert out["grader_ok"] is True
    assert out["grader_manual_review_required"] is True
    assert out["draft_score"] == 2
    assert out["grader_elapsed_seconds"] == 42.5
    assert out["grader_output_chars"] == 1234
    assert out["grader_error_code"] == "OLLAMA_INVALID_JSON"


def test_grader_prompt_contains_immutable_final_answer_lock_before_llm():
    profile = get_task_profile("ege_13")
    transcript = r"""13. а) решение
б) промежуточные вычисления
Ответ: а) x=...; б) -\frac{3\pi}{4}, -\frac{11\pi}{4}, -\frac{9\pi}{4}"""
    state = {
        "task_type": "ege_13",
        "task_statement": "а) Решите. б) Найдите корни на отрезке [-3π; -3π/2].",
        "task_profile": profile.model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": transcript,
        "reference_answer_part_a_verified": "verified",
        "reference_verified_families": [],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_b_verified": "verified",
    }
    fake = {
        "can_grade": True,
        "part_a_status": "uncertain",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": False,
        "error_class": "ambiguous",
        "manual_review_required": True,
        "confidence": 0.5,
        "checked_step_ids": [],
        "issue_steps": [],
        "_model": "test-grader",
    }
    with patch("src.agents.grader.ollama_chat_json", return_value=fake) as mocked:
        grader_agent(state)

    prompt = mocked.call_args.kwargs["user_prompt"]
    assert "IMMUTABLE DETERMINISTIC FINAL-ANSWER EXTRACTION" in prompt
    assert "-3*pi/4" in prompt
    assert "-11*pi/4" in prompt
    assert "-9*pi/4" in prompt
