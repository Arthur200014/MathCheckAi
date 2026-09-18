from src.tools.ege13_report import build_compact_report_node


def test_missing_part_b_is_reported_as_not_attempted():
    state = {
        "review_id": "r-missing-b",
        "task_type": "ege_13",
        "task_title": "Тригонометрическое уравнение и отбор корней",
        "task_statement": "а) Решите уравнение sin(x)=1. б) Найдите корни на отрезке [-3*pi; -3*pi/2].",
        "status": "REVIEWED",
        "final_score": 0,
        "max_score": 2,
        "reference_verification_ok": False,
        "reference_verified_families": [
            {"expression": "pi/2 + 2*pi*n", "parameter": "n"},
        ],
        "reference_expected_roots": ["-3*pi/2"],
        "reviewer_part_a_status": "substantive_error",
        "reviewer_part_b_status": "missing",
        "reviewer_part_a_equivalent": False,
        "reviewer_part_b_roots_match": False,
        "reviewer_error_class": "substantive_math_error",
        "grader_student_evidence": {"part_b_present": False},
        "grader_student_math_errors": ["student_family_value_not_solution"],
        "grader_step_assessments": [
            {
                "step_id": "S1",
                "text": "x = pi/2 + pi*n, n in Z",
                "status": "incorrect",
                "comment": "В общем решении указан неверный период.",
            }
        ],
    }
    report = build_compact_report_node(state)["report"]
    assert report["part_b_present"] is False
    assert report["part_b_comment"] == "Пункт б не выполнялся."
    assert "не подтвержд" not in report["part_a_comment"].lower()
    assert report["score_label"] == "Итоговый балл"


def test_reference_answers_are_human_readable_not_raw_latex():
    state = {
        "review_id": "r-human-answer",
        "task_type": "ege_13",
        "task_title": "Тригонометрическое уравнение и отбор корней",
        "task_statement": "а) Решите уравнение sin(x)=1. б) Найдите корни на отрезке [-3*pi; -3*pi/2].",
        "status": "REVIEWED",
        "final_score": 2,
        "max_score": 2,
        "reference_verification_ok": False,
        "reference_verified_families": [
            {"expression": "pi/2 + 2*pi*n", "parameter": "n"},
        ],
        "reference_expected_roots": ["-3*pi/2"],
        "reviewer_part_a_status": "correct",
        "reviewer_part_b_status": "correct",
        "reviewer_part_a_equivalent": True,
        "reviewer_part_b_roots_match": True,
        "reviewer_error_class": "none",
        "grader_student_evidence": {"part_b_present": True},
        "grader_step_assessments": [],
    }
    report = build_compact_report_node(state)["report"]
    assert "\\frac" not in report["correct_answer_part_a"]
    assert "\\pi" not in report["correct_answer_part_a"]
    assert "\\frac" not in report["correct_answer_part_b"]
    assert "π" in report["correct_answer_part_a"]
    assert "ℤ" in report["correct_answer_part_a"]
    assert report["part_a_comment"] == "Верно."
    assert report["part_b_comment"] == "Верно."
