from src.agents.reference_verifier import reference_verifier_agent
from src.task_registry import get_task_profile


TASK = "а) Решите уравнение: 2sin(x - π/6) - 2√3 cos(π/2 - x) = 0. б) Найдите все корни этого уравнения, принадлежащие отрезку [-6π; -9π/2]."


def test_reference_verifier_agent_works_without_solver_machine_spec():
    profile = get_task_profile("ege_13")
    state = {
        "task_type": "ege_13",
        "task_statement": TASK,
        "task_profile": profile.model_dump(),
        "solver_ok": False,
        "solver_machine_spec": {},
    }
    out = reference_verifier_agent(state)
    assert out["reference_verification_ok"] is True
    assert out["reference_verification_status"] == "REFERENCE_VERIFIED_SOLVER_FALLBACK"
    assert out["reference_expected_roots"] == ["-31*pi/6"]
    assert out["solver_fallback_used"] is True
    assert "31" in out["reference_answer"]


def test_reference_verifier_agent_corrects_wrong_solver_family_and_roots():
    profile = get_task_profile("ege_13")
    state = {
        "task_type": "ege_13",
        "task_statement": TASK,
        "task_profile": profile.model_dump(),
        "solver_machine_spec": {
            "variable": "x",
            "general_solution_families": [{"expression": "-pi/3 + pi*n", "parameter": "n"}],
            "part_b": {
                "has_interval": True,
                "interval_left": "-6*pi",
                "interval_right": "-9*pi/2",
                "left_closed": True,
                "right_closed": True,
                "selected_roots": ["-37*pi/6", "-31*pi/6", "-25*pi/6"],
            },
        },
    }
    out = reference_verifier_agent(state)
    assert out["reference_verification_ok"] is True
    assert out["reference_expected_roots"] == ["-31*pi/6"]
    assert out["reference_equation_source"] == "task_statement_independent_parse+sympy"
