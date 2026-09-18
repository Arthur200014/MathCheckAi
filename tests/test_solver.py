from unittest.mock import patch

from src.agents.solver import solver_agent
from src.graph import route_after_solver
from src.task_registry import get_task_profile


def fake_solver_payload():
    return {
        "can_solve": True,
        "final_answer_part_a": "x=-pi/6+pi*n",
        "confidence": 0.98,
        "machine_spec": {
            "variable": "x",
            "general_solution_families": [{"expression": "-pi/6 + pi*n", "parameter": "n"}],
            "part_b": {
                "has_interval": True,
                "interval_left": "-6*pi",
                "interval_right": "-9*pi/2",
                "left_closed": True,
                "right_closed": True,
                "selected_roots": ["-31*pi/6"],
            },
        },
        "_model": "test-model",
    }


def test_solver_never_receives_student_solution():
    captured = {}

    def fake_call(**kwargs):
        captured.update(kwargs)
        return fake_solver_payload()

    profile = get_task_profile("ege_13")
    state = {
        "task_type": "ege_13",
        "task_statement": "Solve this task",
        "task_profile": profile.model_dump(),
        "transcript": "SECRET STUDENT TRANSCRIPT",
        "confirmed_transcript": "SECRET CONFIRMED TRANSCRIPT",
    }

    with patch("src.agents.solver.ollama_chat_json", side_effect=fake_call):
        result = solver_agent(state)

    assert result["solver_ok"] is True
    assert "SECRET STUDENT TRANSCRIPT" not in captured["user_prompt"]
    assert "SECRET CONFIRMED TRANSCRIPT" not in captured["user_prompt"]
    assert "Тригонометрическое уравнение и отбор корней" in captured["user_prompt"]


def test_solver_failure_still_routes_to_deterministic_verifier():
    assert route_after_solver({"solver_ok": False}) == "verify_reference"
    assert route_after_solver({"solver_ok": True}) == "verify_reference"
    assert route_after_solver({"solver_ok": False, "status": "UNSUPPORTED_TASK_TYPE"}) == "solver_failed"
