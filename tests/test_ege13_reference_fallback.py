from src.tools.ege13_fast_reference import verify_ege13_reference_fast


def test_fast_reference_keeps_exact_inverse_trig_families():
    task = (
        "а) Решите уравнение 1-cos 2x+√2 sin x=√2-sin(x+π). "
        "б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    )
    solver_spec = {
        "variable": "x",
        "general_solution_families": [
            {"expression": "-pi/4 + 2*pi*n", "parameter": "n"},
            {"expression": "3*pi/4 + 2*pi*n", "parameter": "n"},
        ],
        "part_b": {
            "has_interval": True,
            "interval_left": "-3*pi",
            "interval_right": "-3*pi/2",
            "left_closed": True,
            "right_closed": True,
            "selected_roots": ["-11*pi/4", "-7*pi/4"],
        },
    }

    result = verify_ege13_reference_fast(solver_spec, task_statement=task)

    assert result.ok is True
    assert result.verified_families
    assert result.expected_roots
    assert "no_authoritative_solution_families" not in result.errors
