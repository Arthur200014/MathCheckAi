from src.tools.ege13_task_input import (
    build_ege13_task_statement,
    extract_interval_draft,
    extract_task_equation_draft,
    normalize_interval_input,
    validate_task_fields,
)


def test_equation_is_taken_from_student_leading_line():
    transcript = (
        r"a) 1-\cos2x+\sqrt{2}\sin x=\sqrt{2}-2\sin(x+\pi)\n"
        r"2\sin^2x+\sqrt{2}\sin x=\sqrt{2}+2\sin x"
    )
    equation, source = extract_task_equation_draft(transcript, "")
    assert source == "student_leading_equation"
    assert equation == r"1-\cos2x+\sqrt{2}\sin x=\sqrt{2}-2\sin(x+\pi)"


def test_interval_is_never_invented_when_missing():
    transcript = r"a) \sin x=1\nx=\pi/2+2\pi n"
    interval, source = extract_interval_draft(transcript, "")
    assert interval == ""
    assert source == "empty"


def test_visible_interval_is_reused_as_draft():
    transcript = r"б) x\in[-3\pi; -3\pi/2]"
    interval, source = extract_interval_draft(transcript, "")
    assert interval == r"[-3\pi; -3\pi/2]"
    assert source == "visible_interval"


def test_plain_keyboard_interval_gets_brackets():
    assert normalize_interval_input("-3pi; -3pi/2") == "[-3pi; -3pi/2]"


def test_task_statement_is_built_only_after_equation_and_interval_confirmed():
    statement = build_ege13_task_statement(
        "1-cos 2x+sqrt(2) sin x=sqrt(2)-2 sin(x+pi)",
        "-3pi; -3pi/2",
    )
    assert "а) Решите уравнение" in statement
    assert "[-3pi; -3pi/2]" in statement
    assert "б) Найдите все корни" in statement


def test_preflight_requires_equation_and_interval():
    assert validate_task_fields("ege_13", "sin x=1", "[-pi; pi]") == []
    assert "part_b_interval_missing" in validate_task_fields("ege_13", "sin x=1", "")
    assert "task_equation_missing_equals" in validate_task_fields("ege_13", "sin x", "[-pi; pi]")


def test_preflight_blocks_ambiguous_trig_argument_before_solver():
    issues = validate_task_fields(
        "ege_13",
        "1-cos 2x + √2 sin x = √2 - 2 sin x (x+π)",
        "[-3π; -3π/2]",
    )
    assert "task_equation_ambiguous_trig_argument" in issues


def test_preflight_accepts_explicit_trig_argument():
    issues = validate_task_fields(
        "ege_13",
        "1-cos 2x + √2 sin x = √2 - 2 sin(x+π)",
        "[-3π; -3π/2]",
    )
    assert "task_equation_ambiguous_trig_argument" not in issues
