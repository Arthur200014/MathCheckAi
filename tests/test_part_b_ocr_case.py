from src.tools.ege13_fast_reference import verify_ege13_reference_fast
from src.tools.ege13_reasoning import deterministic_reasoning_overrides_ege13
from src.tools.ege13_student import (
    extract_ege13_student_evidence,
    extract_ege13_explicit_final_answer,
    verify_ege13_student_machine_spec,
)
from src.tools.solution_steps import split_solution_step_texts


TASK = (
    "а) Решите уравнение cos 2x - √2 sin(x + π) - 1 = 0. "
    "б) Найдите все корни этого уравнения, принадлежащие отрезку [-13π/4; -2π]."
)

TRANSCRIPT = """n13. cos 2x - √2 sin(x + π) - 1 = 0
а) (1 - 2sin² x) + √2 sin x - 1 = 0 sin x = t
-2t² + √2 t = 0
-t(2t - √2) = 0
1) t = 0 2) t = √2/2
sin x = 0 sin x = √2/2
x = nπ; n ∈ ℤ x = π/4 + 2nπ n ∈ ℤ
x = 3π/4 + 2nπ; n ∈ ℤ
а) x = nπ; x = π/4 + 2nπ; x = 3π/4 + 2nπ; n ∈ ℤ
d) Определим на [-13π/4; -2π]; nπ; π/4 + 2nπ; 3π/4 + 2nπ.
-13π/4; -3π; -2π Ответ: -13π/4; -3π; -2π"""


def test_d_marker_is_read_as_part_b_after_ocr():
    evidence = extract_ege13_student_evidence(TRANSCRIPT)
    assert evidence.part_b_present is True
    assert evidence.selected_roots == ["-13*pi/4", "-3*pi", "-2*pi"]


def test_final_answer_without_second_b_marker_is_still_locked():
    answer = extract_ege13_explicit_final_answer(TRANSCRIPT)
    assert answer.final_answer_found is True
    assert answer.final_part_b_roots == ["-13*pi/4", "-3*pi", "-2*pi"]
    assert "explicit_answer_part_b_marker_not_found" not in answer.errors


def test_n_pi_school_notation_is_parsed_and_both_parts_match():
    evidence = extract_ege13_student_evidence(TRANSCRIPT)
    assert evidence.general_solution_families
    assert not any("student_family_parse_failed" in item for item in evidence.errors)

    reference = verify_ege13_reference_fast({}, task_statement=TASK)
    assert reference.ok is True

    checked = verify_ege13_student_machine_spec(
        evidence.machine_spec(),
        task_statement=TASK,
        reference_families=reference.verified_families,
        expected_roots=reference.expected_roots,
    )
    assert checked.part_a_equivalent is True
    assert checked.part_b_matches is True


def test_compact_part_b_root_row_cannot_be_marked_wrong_by_llm():
    reference = verify_ege13_reference_fast({}, task_statement=TASK)
    steps = [
        {"step_id": f"S{i + 1}", "text": text}
        for i, text in enumerate(split_solution_step_texts(TRANSCRIPT, max_steps=30))
    ]
    overrides = deterministic_reasoning_overrides_ege13(
        steps,
        task_statement=TASK,
        expected_roots=reference.expected_roots,
    )
    row = next(step for step in steps if step["text"] == "-13π/4; -3π; -2π")
    assert overrides[row["step_id"]]["status"] == "correct"
