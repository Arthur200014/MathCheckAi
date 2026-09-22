from src.agents import solver as solver_module


def test_solver_requests_small_machine_first_json(monkeypatch):
    captured = {}

    def fake_call(**kwargs):
        captured.update(kwargs)
        return {
            "can_solve": True,
            "final_answer_part_a": "x=-pi/6+pi*n",
            "confidence": 0.95,
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

    monkeypatch.setattr(solver_module, "ollama_chat_json", fake_call)
    monkeypatch.setattr(solver_module, "get_solver_model", lambda: "test-model")

    out = solver_module.solver_agent({
        "task_type": "ege_13",
        "task_statement": "Решите тестовое уравнение",
    })

    assert out["solver_ok"] is True
    assert captured["num_ctx"] == 4096
    assert captured["num_predict"] == 560
    schema = captured["response_schema"]
    assert "machine_spec" in schema["required"]
                                                                
    assert "reference_solution" not in schema["properties"]
    assert "reference_steps" not in schema["properties"]
    assert "final_answer" not in schema["properties"]
# fix
