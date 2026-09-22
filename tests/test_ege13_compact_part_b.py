from src.tools.ege13_student import extract_ege13_student_evidence
from src.tools.ege13_user_report import build_user_report_node


TRANSCRIPT = """а) (1 - 2sin² x) + √2 sin x - 1 = 0
sin x = t
-2t² + √2 t = 0
sin x = 0 sin x = √2/2
x = π n; n ∈ ℤ
x = π/4 + 2π k, k ∈ ℤ
x = 3π/4 + 2π k, k ∈ ℤ
b)на [-13π/4; -2π]; -13π/4; -3π; -2π
Ответ: -13π/4; -3π; -2π"""


def test_compact_part_b_marker_without_space_is_detected():
    evidence = extract_ege13_student_evidence(TRANSCRIPT)
    assert evidence.part_b_present is True
    assert evidence.explicit_final_answer_used is True
    assert evidence.selected_roots == ["-13*pi/4", "-3*pi", "-2*pi"]


def test_equivalent_pi_n_family_does_not_get_fake_period_comment():
    state = {
        "task_type": "ege_13",
        "task_title": "Тригонометрическое уравнение и отбор корней",
        "status": "REVIEWED",
        "final_score": 2,
        "max_score": 2,
        "confirmed_transcript": TRANSCRIPT,
        "reference_verification_ok": False,
        "reference_verified_families": [
            {"expression": "2*pi*n", "parameter": "n"},
            {"expression": "pi*(2*n - 1)", "parameter": "n"},
            {"expression": "pi/4 + 2*pi*n", "parameter": "n"},
            {"expression": "3*pi/4 + 2*pi*n", "parameter": "n"},
        ],
        "reference_expected_roots": ["-13*pi/4", "-3*pi", "-2*pi"],
        "grader_student_evidence": {"part_b_present": True},
        "grader_part_a_status": "correct",
        "grader_part_b_status": "correct",
        "grader_part_a_equivalent": True,
        "grader_part_b_roots_match": True,
        "reviewer_part_a_status": "correct",
        "reviewer_part_b_status": "correct",
        "reviewer_part_a_equivalent": True,
        "reviewer_part_b_roots_match": True,
    }
    report = build_user_report_node(state)["report"]
    assert report["part_a_comment"] == "Верно."
    assert report["part_b_comment"] == "Верно."
    assert report["expert_comment"] == "Решение верное."
    assert not any(item.get("section") == "а" for item in report["expert_comments"])
# fix
