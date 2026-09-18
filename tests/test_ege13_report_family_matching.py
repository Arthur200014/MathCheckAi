from src.tools.ege13_report_v3 import _display_step_checks, _format_reference_part_a


def _state():
    return {
        "task_type": "ege_13",
        "status": "REVIEWED",
        "reference_verification_ok": True,
        "reference_verified_families": [
            {"expression": "pi/2 + 2*pi*n", "parameter": "n"},
            {"expression": "-pi/4 + 2*pi*n", "parameter": "n"},
            {"expression": "-3*pi/4 + 2*pi*n", "parameter": "n"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "grader_student_evidence": {"part_b_present": False},
        "grader_step_assessments": [
            {
                "step_id": "S10",
                "text": "x=π/2+π n, n∈ℤ",
                "status": "incorrect",
                "comment": "Ошибка в общем решении.",
            }
        ],
    }


def test_wrong_period_keeps_student_seed_and_corrects_same_branch():
    rows = _display_step_checks(_state())
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "incorrect"
    assert "Неверный период" in row["comment"]
    assert "x = π/2 + 2πn, n ∈ ℤ" in row["comment"]
    assert "-3π/4" not in row["comment"]
    assert "-π/4" not in row["comment"]


def test_reference_answer_uses_school_family_form():
    answer = _format_reference_part_a(_state())
    assert "π(4n" not in answer
    assert "x = π/2 + 2πn, n ∈ ℤ" in answer
    assert "x = -π/4 + 2πn, n ∈ ℤ" in answer
    assert "x = -3π/4 + 2πn, n ∈ ℤ" in answer
