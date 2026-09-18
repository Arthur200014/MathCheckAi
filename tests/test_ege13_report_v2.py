from src.tools.ege13_report_v2 import build_compact_report_node


def _state():
    return {
        "review_id": "r-format",
        "task_type": "ege_13",
        "task_title": "Тригонометрическое уравнение и отбор корней",
        "status": "REVIEWED",
        "final_score": 0,
        "max_score": 2,
        "reference_verification_ok": False,
        "reference_verified_families": [
            {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
            {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
            {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reviewer_part_a_status": "substantive_error",
        "reviewer_part_a_equivalent": False,
        "reviewer_part_b_status": "missing",
        "reviewer_part_b_roots_match": False,
        "grader_student_evidence": {"part_b_present": False},
        "grader_step_assessments": [
            {
                "step_id": "S10",
                "text": "x = pi/2 + pi*n, n ∈ Z",
                "status": "incorrect",
                "comment": "Общее решение содержит неверный период.",
            }
        ],
    }


def test_part_a_reference_uses_school_notation():
    report = build_compact_report_node(_state())["report"]
    assert report["correct_answer_part_a"].splitlines() == [
        "x = π/2 + 2πn, n ∈ ℤ",
        "x = -π/4 + 2πn, n ∈ ℤ",
        "x = -3π/4 + 2πn, n ∈ ℤ",
    ]
    assert "π(4n + 1)" not in report["correct_answer_part_a"]
    assert report["correct_answer_part_b"] == "-11π/4; -9π/4; -3π/2"


def test_incorrect_family_step_contains_exact_correction():
    report = build_compact_report_node(_state())["report"]
    step = report["step_checks"][0]
    assert step["status"] == "incorrect"
    assert step["correction"] == "x = π/2 + 2πn, n ∈ ℤ"
    assert "Правильно: x = π/2 + 2πn, n ∈ ℤ" in step["comment"]
    assert report["part_b_comment"] == "Пункт б не выполнялся."
