from src.tools.display_math import latex_to_human_text
from src.tools.ege13_student import extract_ege13_student_evidence
from src.tools.ege13_reference import _extract_part_a_equation


def test_latex_draft_becomes_human_readable_unicode():
    raw = r"a) 1-\cos2x+\sqrt{2}\sin x=\sqrt{2}-2\sin(x+\pi)\n\Rightarrow \sin x=-\frac{\sqrt{2}}{2}\nx=\frac{\pi}{2}+\pi n, n\in\mathbb{Z}"
    display = latex_to_human_text(raw)
    assert "\\cos" not in display
    assert "\\sqrt" not in display
    assert "\\frac" not in display
    assert "\\n" not in display
    assert "cos 2x" in display
    assert "√2" in display
    assert "⇒" in display
    assert "π/2" in display
    assert "n∈ℤ" in display.replace(" ", "")
    assert len(display.splitlines()) == 3


def test_human_readable_confirmed_solution_still_extracts_student_family():
    confirmed = """a) 1 − cos 2x + √2 sin x = √2 − 2 sin(x + π)
    sin x = 1
    x = π/2 + π n, n ∈ ℤ
    """
    evidence = extract_ege13_student_evidence(confirmed)
    assert evidence.part_a_present is True
    assert evidence.general_solution_families
    assert evidence.general_solution_families[0]["expression"] == "pi*(n + 1/2)"


def test_human_readable_task_statement_is_parser_compatible():
    statement = "а) Решите уравнение 1 − cos 2x + √2 sin x = √2 − 2 sin(x + π). б) Найдите корни на [−3π; −3π/2]."
    residual = _extract_part_a_equation(statement, "x")
    assert str(residual)
