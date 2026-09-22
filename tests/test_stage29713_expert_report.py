from pathlib import Path

from src.tools.ege13_reasoning import deterministic_reasoning_overrides_ege13
from src.tools.ege13_user_report import build_user_report_node


def test_case_split_branches_are_not_marked_wrong_for_not_being_globally_equivalent():
    steps = [
        {"step_id": "S1", "text": "(sin x-1)(2sin x+sqrt(2))=0"},
        {"step_id": "S2", "text": "sin x-1=0"},
        {"step_id": "S3", "text": "2sin x+sqrt(2)=0"},
    ]
    got = deterministic_reasoning_overrides_ege13(
        steps,
        task_statement=(
            "а) Решите уравнение 1-cos 2x+sqrt(2) sin x=sqrt(2)-2 sin(x+pi). "
            "б) Найдите корни на отрезке [-3*pi; -3*pi/2]."
        ),
        expected_roots=[],
    )
    assert got.get("S2", {}).get("status") != "incorrect"
    assert got.get("S3", {}).get("status") != "incorrect"
    assert "не эквивалентен исходному" not in str(got).lower()


def test_report_shows_confirmed_solution_once_and_concrete_period_comment():
    transcript = """а) 1-cos 2x+√2 sin x=√2-2 sin(x+π)
(sin x-1)(2sin x+√2)=0
sin x=1
sin x=-√2/2
x=π/2+π n, n∈ℤ
x=-π/4+2π k, k∈ℤ
x=-3π/4+2π k, k∈ℤ"""
    state = {
        "status": "REVIEWED",
        "review_id": "r-expert",
        "task_type": "test-no-circle",
        "task_title": "Тригонометрическое уравнение",
        "confirmed_transcript": transcript,
        "final_score": 0,
        "max_score": 2,
        "reference_verified_families": [
            {"expression": "pi/2 + 2*pi*n", "parameter": "n"},
            {"expression": "-pi/4 + 2*pi*k", "parameter": "k"},
            {"expression": "-3*pi/4 + 2*pi*k", "parameter": "k"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "grader_part_a_equivalent": False,
        "grader_part_b_roots_match": None,
        "grader_part_a_status": "substantive_error",
        "grader_part_b_status": "missing",
        "reviewer_part_a_status": "substantive_error",
        "reviewer_part_b_status": "missing",
        "reviewer_error_class": "substantive_math_error",
        "grader_student_evidence": {"part_b_present": False},
    }
    out = build_user_report_node(state)["report"]
    assert out["confirmed_solution_text"] == transcript
    comments = out["expert_comments"]
    assert comments
    period = next(item for item in comments if "период" in item["title"].lower())
    assert "π/2 + 2πn" in period["correction"]
    assert "-3π/4" not in period["correction"]
    assert out["part_b_comment"] == "Пункт б не выполнялся."


def test_browser_report_is_not_a_step_by_step_green_red_list():
    html = Path("web/index29710.html").read_text(encoding="utf-8")
    assert 'id="confirmedSolution"' in html
    assert 'id="expertComments"' in html
    assert 'id="steps"' not in html
    assert "Шаг ${i+1}" not in html
    assert "Комментарий эксперта" in html
# fix
