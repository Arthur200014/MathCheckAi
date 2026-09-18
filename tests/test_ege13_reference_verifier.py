from src.tools.ege13_reference import verify_ege13_reference


TASK = "а) Решите уравнение: 2sin(x - π/6) - 2√3 cos(π/2 - x) = 0. б) Найдите все корни этого уравнения, принадлежащие отрезку [-6π; -9π/2]."


def base_spec(selected_roots=None, family="-pi/6 + pi*n"):
    return {
        "variable": "x",
        "general_solution_families": [
            {"expression": family, "parameter": "n"},
        ],
        "part_b": {
            "has_interval": True,
            "interval_left": "-6*pi",
            "interval_right": "-9*pi/2",
            "left_closed": True,
            "right_closed": True,
            "selected_roots": selected_roots if selected_roots is not None else ["-31*pi/6"],
        },
    }


def test_verifier_accepts_correct_reference_and_uses_task_as_trust_root():
    out = verify_ege13_reference(base_spec(), task_statement=TASK)
    assert out.ok is True
    assert out.status in {"REFERENCE_VERIFIED", "REFERENCE_VERIFIED_WITH_CORRECTION"}
    assert out.expected_roots == ["-31*pi/6"]
    assert out.equation_source == "task_statement_independent_parse+sympy"
    assert out.corrected_answer_part_a


def test_verifier_repairs_wrong_interval_selection_from_solver():
    out = verify_ege13_reference(base_spec(["-13*pi/6", "-19*pi/6"]), task_statement=TASK)
    assert out.ok is True
    assert out.status == "REFERENCE_VERIFIED_WITH_CORRECTION"
    assert out.expected_roots == ["-31*pi/6"]
    assert any("outside_interval" in e for e in out.errors)


def test_verifier_repairs_wrong_general_family_using_independent_solveset():
    # Realistic 4B-model algebra slip: tan(x)=-sqrt(3) -> x=-pi/3+pi*n.
    out = verify_ege13_reference(base_spec(family="-pi/3 + pi*n"), task_statement=TASK)
    assert out.ok is True
    assert out.expected_roots == ["-31*pi/6"]
    assert out.status in {"REFERENCE_VERIFIED_SOLVER_FALLBACK", "REFERENCE_VERIFIED_WITH_CORRECTION"}
    assert any("family_root_fails_equation" in e for e in out.errors)


def test_verifier_can_build_reference_when_solver_json_is_missing_entirely():
    out = verify_ege13_reference({}, task_statement=TASK)
    assert out.ok is True
    assert out.status == "REFERENCE_VERIFIED_SOLVER_FALLBACK"
    assert out.solver_fallback_used is True
    assert out.expected_roots == ["-31*pi/6"]
    assert len(out.verified_families) >= 1


def test_real_observed_six_wrong_roots_are_ignored():
    spec = base_spec([
        "-37*pi/6",
        "-31*pi/6",
        "-25*pi/6",
        "-19*pi/6",
        "-13*pi/6",
        "-7*pi/6",
    ])
    out = verify_ege13_reference(spec, task_statement=TASK)
    assert out.ok is True
    assert out.expected_roots == ["-31*pi/6"]
    assert any(e.startswith("solver_selected_roots_extra:") for e in out.errors)


def test_task_statement_without_colon_after_resite_uravnenie_is_parsed():
    from src.tools.ege13_reference import verify_ege13_reference

    task_statement = (
        "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). "
        "б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    )
    result = verify_ege13_reference({}, task_statement=task_statement)

    assert result.ok is True
    assert result.expected_roots == ["-11*pi/4", "-9*pi/4", "-3*pi/2"]
    assert not any("Р" in item or "уравнение" in item.lower() for item in result.results)
