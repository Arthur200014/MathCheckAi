from unittest.mock import patch

from src.agents.grader import grader_agent
from src.agents.reviewer import reviewer_agent
from src.task_registry import get_task_profile
from src.tools.ege13_student import (
    deterministic_step_overrides_ege13,
    extract_ege13_student_evidence,
    verify_ege13_student_machine_spec,
)
from src.tools.ege13_report import extract_solution_steps

TASK = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
REF = [
    {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
    {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
    {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
]
ROOTS = ["-11*pi/4", "-9*pi/4", "-3*pi/2"]

CASE_A = r"""a) 1-\cos 2x+\sqrt{2}\sin x=\sqrt{2}-2\sin(x+\pi)
1-1+2\sin^2 x+\sqrt{2}\sin x=\sqrt{2}-2\sin(\pi+x)
2\sin^2 x+\sqrt{2}\sin x=\sqrt{2}+2\sin x
(2\sin x+\sqrt{2})(\sin x-1)=0
\begin{cases}x=(-1)^k\left(-\frac{\pi}{4}\right)+\pi k,\ k\in\mathbb{Z}\\x=\frac{\pi}{2}+2\pi n,\ n\in\mathbb{Z}\end{cases}
b) Найдём корни
x_1=-3\pi+\frac{\pi}{4}=-\frac{11\pi}{4}
x_2=-2\pi-\frac{\pi}{4}=-\frac{9\pi}{4}
x_3=-\frac{3\pi}{2}"""

CASE_B = r"""a) 1-\cos 2x+\sqrt{2}\sin x=\sqrt{2}-2\sin(x+\pi)
x=-\frac{\pi}{4}+2\pi k, x=\frac{\pi}{2}+2\pi k, x=-\frac{3\pi}{4}+2\pi k, k\in\mathbb{Z}.
б) -\frac{\pi}{4}-2\pi=-\frac{9\pi}{4}; -\frac{3\pi}{4}-2\pi=-\frac{11\pi}{4}; -\frac{3\pi}{2}.
Ответ: a) ...; b) -\frac{3\pi}{4}, -\frac{11\pi}{4}, -\frac{9\pi}{4}"""

CASE_C = r"""a) 1-\cos 2x+\sqrt{2}\sin x=\sqrt{2}-2\sin(x+\pi)
1-1+2\sin^2 x+\sqrt{2}\sin x=\sqrt{2}-2\sin(\pi+x)
2\sin^2 x+\sqrt{2}\sin x=\sqrt{2}+2\sin x
2\sin^2 x-2\sin x+\sqrt{2}\sin x-\sqrt{2}=0
2\sin x(\sin x-1)+\sqrt{2}(\sin x-1)=0
(\sin x-1)(2\sin x+\sqrt{2})=0
\sin x-1=0\quad \text{или}\quad 2\sin x+\sqrt{2}=0
\sin x=1
x=\frac{\pi}{2}+\pi n,\ n\in\mathbb{Z}
\sin x=-\frac{\sqrt{2}}{2}
x=-\frac{\pi}{4}+2\pi k,\ k\in\mathbb{Z}
x=-\frac{3\pi}{4}+2\pi k,\ k\in\mathbb{Z}"""


def _state(transcript: str):
    return {
        "task_type": "ege_13",
        "task_statement": TASK,
        "task_profile": get_task_profile("ege_13").model_dump(),
        "task_max_score": 2,
        "confirmed_transcript": transcript,
        "transcript_confirmed": True,
        "reference_verification_ok": True,
        "reference_verified_families": REF,
        "reference_expected_roots": ROOTS,
        "reference_answer_part_a_verified": "verified",
        "reference_answer_part_b_verified": "verified",
        "errors": [],
        "warnings": [],
    }


def _friendly_llm():
    return {
        "can_grade": True,
        "part_a_status": "correct",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": False,
        "confidence": 0.98,
        "checked_step_ids": [f"S{i}" for i in range(1, 25)],
        "issue_steps": [],
        "_model": "test-grader",
        "_elapsed_seconds": 1.0,
        "_ollama_telemetry": {},
    }


def test_transcript_only_extractor_case_c_never_invents_part_b_or_repairs_period():
    evidence = extract_ege13_student_evidence(CASE_C)
    assert evidence.source == "confirmed_transcript_only"
    assert evidence.part_b_present is False
    assert evidence.selected_roots == []
    expressions = {x["expression"] for x in evidence.general_solution_families}
    assert "pi*(n + 1/2)" in expressions  # student's wrong pi*n period is preserved
    assert "pi*(4*n + 1)/2" not in expressions  # reference 2*pi*n family was NOT injected


def test_case_c_deterministic_math_is_zero_and_wrong_family_step_is_red_even_if_llm_says_all_correct():
    with patch("src.agents.grader._call_grader_llm_once", return_value=_friendly_llm()):
        out = grader_agent(_state(CASE_C))
    assert out["grader_student_evidence_source"] == "confirmed_transcript_only"
    assert out["grader_part_a_equivalent"] is False
    assert out["grader_part_a_status"] == "substantive_error"
    assert out["grader_part_b_status"] == "missing"
    assert out["grader_student_selected_roots"] == []
    assert out["draft_score"] == 0
    row = next(x for x in out["grader_step_assessments"] if "\\frac{\\pi}{2}+\\pi n" in x["text"])
    assert row["status"] == "incorrect"


def test_case_a_scores_two_from_transcript_facts():
    with patch("src.agents.grader._call_grader_llm_once", return_value=_friendly_llm()):
        out = grader_agent(_state(CASE_A))
    assert out["grader_part_a_equivalent"] is True
    assert out["grader_part_b_roots_match"] is True
    assert out["draft_score"] == 2


def test_case_b_explicit_wrong_final_answer_cannot_be_repaired_by_llm():
    with patch("src.agents.grader._call_grader_llm_once", return_value=_friendly_llm()):
        out = grader_agent(_state(CASE_B))
    assert out["grader_part_a_equivalent"] is True
    assert out["grader_part_b_roots_match"] is False
    assert set(out["grader_student_selected_roots"]) == {"-11*pi/4", "-9*pi/4", "-3*pi/4"}
    assert out["grader_part_b_status"] == "incorrect"
    assert out["draft_score"] == 1


def test_deterministic_step_override_detects_invalid_period_family():
    steps = extract_solution_steps(CASE_C)
    overrides = deterministic_step_overrides_ege13(steps, task_statement=TASK, expected_roots=ROOTS)
    sid = next(s["step_id"] for s in steps if "\\frac{\\pi}{2}+\\pi n" in s["text"])
    assert overrides[sid]["status"] == "incorrect"


def test_reviewer_advisory_never_erases_existing_score():
    state = _state(CASE_C)
    state.update({
        "draft_score": 0,
        "grader_ok": True,
        "grader_manual_review_required": True,
        "grader_review_advisories": ["grader_requested_manual_review"],
        "grader_student_evidence_source": "confirmed_transcript_only",
        "grader_part_a_status": "substantive_error",
        "grader_part_b_status": "missing",
        "grader_error_class": "substantive_math_error",
        "grader_part_a_equivalent": False,
        "grader_part_b_roots_match": False,
        "grader_invariant_overrides": [],
    })
    fake = {
        "consistent": False,
        "manual_review_required": True,
        "confidence": 0.5,
        "score_agrees": False,
        "reason_codes": ["semantic_uncertainty"],
        "_model": "test-reviewer",
        "_elapsed_seconds": 0.5,
        "_ollama_telemetry": {},
    }
    with patch("src.agents.reviewer._call_once", return_value=fake):
        out = reviewer_agent(state)
    assert out["final_score"] == 0
    assert out["status"] == "REVIEWED"
    assert out["reviewer_manual_review_required"] is True
