import pytest
import sympy as sp

from src.tools.ege13_reference import (
    _parse_math_expr,
    _sympify,
    verify_ege13_reference,
)


@pytest.mark.parametrize(
    ("task", "expected_roots"),
    [
        (
            "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). "
            "б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2].",
            ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        ),
        (
            "а) Решите уравнение cos 2x - √2 sin(x + π) - 1 = 0. "
            "б) Укажите корни этого уравнения, принадлежащие отрезку [-7π/2; -2π].",
            ["-13*pi/4", "-3*pi", "-2*pi"],
        ),
        (
            "а) Решите уравнение sin x · cos 2x + √2 cos^2 x + sin x = 0. "
            "б) Укажите корни этого уравнения, принадлежащие отрезку [3π/2; 3π].",
            ["3*pi/2", "7*pi/4", "5*pi/2"],
        ),
        (
            "а) Решите уравнение sin 2x + 2 sin(-x) + cos(-x) - 1 = 0. "
            "б) Укажите корни этого уравнения, принадлежащие отрезку [2π; 7π/2].",
            ["2*pi", "19*pi/6"],
        ),
        (
            "а) Решите уравнение 9·81^(cos x) - 28·9^(cos x) + 3 = 0. "
            "б) Укажите корни этого уравнения, принадлежащие отрезку [5π/2; 4π].",
            ["3*pi", "11*pi/3"],
        ),
        (
            "а) Решите уравнение 2log_4^2(4sin x) - 5log_4(4sin x) + 2 = 0. "
            "б) Укажите корни этого уравнения, принадлежащие отрезку [-3π/2; 0].",
            ["-7*pi/6"],
        ),
    ],
)
def test_documented_task13_families_parse_and_verify(task, expected_roots):
    out = verify_ege13_reference({}, task_statement=task)
    assert out.ok is True
    assert out.expected_roots == expected_roots


def test_part_labels_and_instruction_punctuation_variants():
    task = (
        "№13.1 A. Решите уравнение: 1 − cos 2x + √2 sin x = √2 − 2 sin(x + π). "
        "B. Найдите все корни этого уравнения, принадлежащие отрезку [−3π; −3π/2]."
    )
    out = verify_ege13_reference({}, task_statement=task)
    assert out.ok is True
    assert out.expected_roots == ["-11*pi/4", "-9*pi/4", "-3*pi/2"]


def test_latex_task_statement_variants_are_supported():
    task = (
        r"a) Решите уравнение: 2\sin\left(x-\frac{\pi}{6}\right)"
        r"-2\sqrt{3}\cos\left(\frac{\pi}{2}-x\right)=0. "
        r"b) Найдите корни на отрезке [ -6\pi, -9\pi/2 ]"
    )
    out = verify_ege13_reference({}, task_statement=task)
    assert out.ok is True
    assert out.expected_roots == ["-31*pi/6"]


def test_latex_function_powers_log_base_and_exponential_powers():
    x = sp.Symbol("x", real=True)
    trig = _parse_math_expr(r"\sin^{2} x + \sqrt{2}\cos^{2} x", extra={"x": x})
    assert sp.simplify(trig - (sp.sin(x) ** 2 + sp.sqrt(2) * sp.cos(x) ** 2)) == 0

    log_expr = _parse_math_expr(
        r"2\log_{4}^{2}(4\sin x)-5\log_{4}(4\sin x)+2",
        extra={"x": x},
    )
    assert x in log_expr.free_symbols

    exp_expr = _parse_math_expr(
        r"9\cdot81^{\cos x}-28\cdot9^{\cos x}+3",
        extra={"x": x},
    )
    assert x in exp_expr.free_symbols


def test_bare_trig_products_are_not_greedily_nested():
    x = sp.Symbol("x", real=True)
    parsed = _parse_math_expr("sin x · cos 2x", extra={"x": x})
    assert sp.simplify(parsed - sp.sin(x) * sp.cos(2 * x)) == 0


def test_unicode_machine_spec_math_is_tolerated():
    n = sp.Symbol("n", integer=True)
    parsed = _sympify("-π/6 + π*n", extra={"n": n})
    assert sp.simplify(parsed - (-sp.pi / 6 + sp.pi * n)) == 0


def test_decimal_comma_and_unicode_multiplication_are_normalized():
    x = sp.Symbol("x", real=True)
    parsed = _parse_math_expr("0,5×x + 1", extra={"x": x})
    assert sp.simplify(parsed - (sp.Rational(1, 2) * x + 1)) == 0


def test_comma_interval_separator_with_spaces_is_supported():
    task = (
        "а) Решите уравнение 2sin(x - π/6) - 2√3 cos(π/2 - x)=0. "
        "б) Найдите корни на отрезке [-6π, -9π/2]."
    )
    out = verify_ege13_reference({}, task_statement=task)
    assert out.ok is True
    assert out.expected_roots == ["-31*pi/6"]


def test_stray_prose_is_rejected_instead_of_becoming_symbol_product():
    task = (
        "а) Решите уравнение случайный текст 2sin x = 0. "
        "б) Найдите корни на отрезке [0; 2π]."
    )
    out = verify_ege13_reference({}, task_statement=task)
    assert out.ok is False
    assert any("unsupported_identifier_in_math_expression" in err for err in out.errors)


def test_no_space_before_part_b_marker_is_supported():
    task = (
        "Задание 13. а) Решите уравнение 2sin(x-pi/6)-2sqrt(3)cos(pi/2-x)=0."
        "б) Найдите корни на отрезке [-6pi;-9pi/2]."
    )
    out = verify_ege13_reference({}, task_statement=task)
    assert out.ok is True
    assert out.expected_roots == ["-31*pi/6"]


def test_latex_interval_with_nested_frac_is_supported():
    task = (
        r"а) Решите уравнение 2\sin(x-\frac{\pi}{6})-2\sqrt{3}\cos(\frac{\pi}{2}-x)=0. "
        r"б) Найдите корни на отрезке \left[-6\pi;-\frac{9\pi}{2}\right]."
    )
    out = verify_ege13_reference({}, task_statement=task)
    assert out.ok is True
    assert out.expected_roots == ["-31*pi/6"]
