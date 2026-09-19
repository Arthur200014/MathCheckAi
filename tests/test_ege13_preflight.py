from src.tools.ege13_preflight import validate_ege13_input


def test_preflight_accepts_normal_ege13_input():
    out = validate_ege13_input(
        "1 - cos 2x + √2 sin x = √2 - 2 sin(x+π)",
        "[-3π; -3π/2]",
        "a) решение ученика",
    )
    assert out["ok"] is True
    assert out["issues"] == []


def test_preflight_stops_ambiguous_trig_argument_before_models():
    out = validate_ege13_input(
        "1 - cos 2x + √2 sin x = √2 - 2 sin x (x+π)",
        "[-3π; -3π/2]",
        "a) решение ученика",
    )
    assert out["ok"] is False
    assert any(x["code"] == "task_equation_ambiguous_trig_argument" for x in out["issues"])


def test_preflight_keeps_user_in_editor_for_bad_parentheses():
    out = validate_ege13_input(
        "sin(x = 1/2",
        "[-π; π]",
        "a) решение ученика",
    )
    assert out["ok"] is False
    assert any(x["field"] == "equation" for x in out["issues"])
