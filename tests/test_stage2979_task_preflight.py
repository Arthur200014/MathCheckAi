from src.tools.ege13_task_input import (
    infer_task_statement_draft,
    validate_confirmed_task_statement,
)


def test_visible_leading_equation_becomes_task_draft_when_vision_task_empty():
    transcript = (
        "a) 1-\\cos2x+\\sqrt{2}\\sin x=\\sqrt{2}-2\\sin(x+\\pi)\n"
        "2\\sin^2x+\\sqrt{2}\\sin x=\\sqrt{2}+2\\sin x"
    )
    draft, source = infer_task_statement_draft("", transcript)
    assert draft.startswith("1-")
    assert source == "student_leading_equation"


def test_fallback_never_invents_missing_interval():
    transcript = "a) sin x = 1\nx=pi/2+2*pi*n"
    draft, _ = infer_task_statement_draft("", transcript)
    assert "[" not in draft
    assert ";" not in draft


def test_ege13_preflight_rejects_equation_without_part_b_interval():
    issues = validate_confirmed_task_statement(
        "ege_13",
        "1-cos 2x+√2 sin x=√2-2 sin(x+π)",
    )
    assert "part_b_interval_missing" in issues


def test_ege13_preflight_accepts_equation_and_interval():
    issues = validate_confirmed_task_statement(
        "ege_13",
        "а) 1-cos 2x+√2 sin x=√2-2 sin(x+π). б) [-3π; -3π/2]",
    )
    assert issues == []
