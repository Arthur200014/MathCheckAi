import json
from pathlib import Path

import pytest

from src.tools.ege13_reference import verify_ege13_reference
from src.tools.ege13_student import (
    extract_ege13_explicit_final_answer,
    extract_ege13_student_evidence,
    verify_ege13_student_machine_spec,
)
from src.tools.ege13_task_input import build_ege13_task_statement


@pytest.mark.parametrize(
    ("family_text", "parameter"),
    [
        ("x = πk, k ∈ ℤ", "k"),
        ("x = kπ, k ∈ Z", "k"),
        ("x = 2πn, n ∈ ℤ", "n"),
        ("x = 2nπ, n ∈ ℤ", "n"),
        ("x = 3πm/4, m ∈ ℤ", "m"),
        (r"x = -\pi/4 + 2\pi n, n \in \mathbb{Z}", "n"),
        ("x = (-1)^k·(-π/4) + πk, k ∈ ℤ", "k"),
        ("x = πk₁, k₁ ∈ ℤ", "k1"),
        ("x = πk_2, k_2 ∈ ℤ", "k2"),
        ("x = πk_{3}, k_{3} ∈ ℤ", "k3"),
    ],
)
def test_common_school_periodic_notation_is_parsed(family_text, parameter):
    evidence = extract_ege13_student_evidence("а) " + family_text + "\nб) x₁ = 0")
    assert evidence.errors == []
    assert len(evidence.general_solution_families) == 1
    assert evidence.general_solution_families[0]["parameter"] == parameter
    assert parameter in evidence.general_solution_families[0]["expression"]


def test_shared_parameter_declaration_and_multiple_families_are_parsed():
    text = (
        "а) x = π/4 + 2πn; x = 3π/4 + 2πn, n ∈ ℤ\n"
        "б) x₁ = -13π/4; x₂ = -3π; x₃ = -2π"
    )
    evidence = extract_ege13_student_evidence(text)
    assert evidence.errors == []
    assert len(evidence.general_solution_families) == 2
    assert {item["parameter"] for item in evidence.general_solution_families} == {"n"}


@pytest.mark.parametrize("marker", ["б)", "б.", "б:", "b)", "d)", "6)"])
def test_common_part_b_markers_are_recognized(marker):
    evidence = extract_ege13_student_evidence(
        f"а) x = πk, k ∈ ℤ\n{marker} x₁ = -13π/4\nx₂ = -3π\nx₃ = -2π"
    )
    assert evidence.part_b_present is True
    assert set(evidence.selected_roots) == {"-13*pi/4", "-3*pi", "-2*pi"}


def test_enumerated_root_calculations_are_aggregated():
    text = (
        "а) x = (-1)^k·(-π/4) + πk, k ∈ ℤ; x = π/2 + 2πn, n ∈ ℤ\n"
        "б) (1): -π/4 - 2π = -9π/4\n"
        "(2): -3π/4 - 2π = -11π/4\n"
        "(3): -3π/2"
    )
    evidence = extract_ege13_student_evidence(text)
    assert set(evidence.selected_roots) == {"-11*pi/4", "-9*pi/4", "-3*pi/2"}


def test_part_b_families_never_pollute_part_a_families():
    text = "а) x = πk, k ∈ ℤ\nб) x = π/4 + 2πn, n ∈ ℤ"
    evidence = extract_ege13_student_evidence(text)
    assert len(evidence.general_solution_families) == 1
    assert evidence.general_solution_families[0]["parameter"] == "k"


def test_compact_final_answer_after_part_b_is_locked():
    out = extract_ege13_explicit_final_answer(
        "а) x = πk, k ∈ ℤ\nб) вычисления\nОтвет: -13π/4; -3π; -2π"
    )
    assert out.final_answer_found is True
    assert set(out.final_part_b_roots) == {"-13*pi/4", "-3*pi", "-2*pi"}


def test_final_answer_with_repeated_part_labels_is_locked():
    out = extract_ege13_explicit_final_answer(
        "а) решение\nб) решение\nОтвет: а) x = πk, k ∈ ℤ; б) -13π/4; -3π; -2π"
    )
    assert set(out.final_part_b_roots) == {"-13*pi/4", "-3*pi", "-2*pi"}


def test_expert_two_case_131_is_deterministically_ready_for_two_points():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "evals" / "task_13" / "benchmark_cases.json").read_text(encoding="utf-8"))
    case = next(item for item in data["cases"] if item["id"] == "13.1.1")
    statement = build_ege13_task_statement(case["task_equation"], case["interval"])
    reference = verify_ege13_reference({}, task_statement=statement)
    assert reference.ok is True

    evidence = extract_ege13_student_evidence(case["manual_transcript"])
    assert evidence.errors == []
    verified = verify_ege13_student_machine_spec(
        evidence.machine_spec(),
        task_statement=statement,
        reference_families=reference.verified_families,
        expected_roots=reference.expected_roots,
    )
    assert verified.part_a_equivalent is True
    assert verified.part_b_matches is True
    assert verified.errors == []
