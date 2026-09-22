from src.tools.ege13_user_report import build_user_report_node


def _state():
    return {
        "review_id": "r-family",
        "task_type": "ege_13",
        "task_title": "Тригонометрическое уравнение и отбор корней",
        "status": "REVIEWED",
        "final_score": 0,
        "max_score": 2,
        "reference_verification_ok": False,
        "reference_verified_families": [
            {"expression": "pi/2 + 2*pi*n", "parameter": "n"},
            {"expression": "-pi/4 + 2*pi*n", "parameter": "n"},
            {"expression": "-3*pi/4 + 2*pi*n", "parameter": "n"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "confirmed_transcript": "x=π/2+π n, n∈ℤ",
        "grader_part_a_status": "substantive_error",
        "grader_part_a_equivalent": False,
        "grader_part_b_status": "missing",
        "reviewer_part_a_status": "substantive_error",
        "reviewer_part_a_equivalent": False,
        "reviewer_part_b_status": "missing",
        "reviewer_error_class": "substantive_math_error",
        "grader_student_evidence": {"part_b_present": False},
    }


def test_wrong_period_keeps_student_seed_and_corrects_same_branch():
    report = build_user_report_node(_state())["report"]
    comments = [item for item in report["expert_comments"] if item.get("section") == "а"]
    assert comments
    period = comments[0]
    assert "Неверный период" in period["title"]
    assert "x = π/2 + 2πn, n ∈ ℤ" in period["correction"]
    assert "-3π/4" not in period["correction"]
    assert "-π/4" not in period["correction"]


def test_reference_answer_uses_school_family_form():
    answer = build_user_report_node(_state())["report"]["correct_answer_part_a"]
    assert "π(4n" not in answer
    assert "x = π/2 + 2πn, n ∈ ℤ" in answer
    assert "x = -π/4 + 2πn, n ∈ ℤ" in answer
    assert "x = -3π/4 + 2πn, n ∈ ℤ" in answer
# fix
