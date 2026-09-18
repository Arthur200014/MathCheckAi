import sympy as sp

from src.tools.ege13_reference import _enumerate_integer_family
from src.tools.ege13_student import verify_ege13_student_machine_spec

TASK_131 = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."

REFERENCE_FAMILIES = [
    {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
    {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
    {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
]


def test_standard_alternating_sine_family_is_enumerated_by_parity():
    values, errors = _enumerate_integer_family(
        "(-1)^k * (-pi/4) + pi*k",
        "k",
        -3 * sp.pi,
        -3 * sp.pi / 2,
        left_closed=True,
        right_closed=True,
    )
    assert errors == []
    assert [sp.sstr(v) for v in values] == ["-11*pi/4", "-9*pi/4"]


def test_case_131_student_machine_spec_is_fully_confirmed():
    out = verify_ege13_student_machine_spec(
        {
            "general_solution_families": [
                {"expression": "(-1)^k * (-pi/4) + pi*k", "parameter": "k"},
                {"expression": "pi/2 + 2*pi*n", "parameter": "n"},
            ],
            "selected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        },
        task_statement=TASK_131,
        reference_families=REFERENCE_FAMILIES,
        expected_roots=["-11*pi/4", "-9*pi/4", "-3*pi/2"],
    )
    assert out.part_a_equivalent is True
    assert out.part_b_matches is True
    assert out.errors == []
