from pathlib import Path

from src.llm.config import get_solver_model
from src.llm.ollama_client import OllamaError, ollama_chat_json
from src.state import ReviewState
from src.task_registry import TaskProfile, get_task_profile

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _profile_from_state(state: ReviewState) -> TaskProfile:
    raw_profile = state.get("task_profile")
    if raw_profile:
        return TaskProfile.model_validate(raw_profile)
    return get_task_profile(state.get("task_type", ""))


def solver_agent(state: ReviewState) -> dict:









    statement = str(state.get("task_statement", "")).strip()
    if not statement:
        return {
            "solver_ok": False,
            "solver_model": get_solver_model(),
            "solver_confidence": 0.0,
            "solver_error": "empty_task_statement",
            "solver_machine_spec": {},
            "warnings": list(state.get("warnings", [])) + ["solver:empty_task_statement"],
        }

    try:
        profile = _profile_from_state(state)
    except Exception as exc:
        return {
            "solver_ok": False,
            "solver_model": get_solver_model(),
            "solver_confidence": 0.0,
            "solver_error": f"task_profile:{exc}",
            "solver_machine_spec": {},
            "status": "UNSUPPORTED_TASK_TYPE",
            "errors": list(state.get("errors", [])) + [f"solver:task_profile:{exc}"],
        }

    if not profile.solver_skill:
        return {
            "solver_ok": False,
            "solver_model": get_solver_model(),
            "solver_confidence": 0.0,
            "solver_error": "missing_solver_skill",
            "solver_machine_spec": {},
            "status": "UNSUPPORTED_TASK_TYPE",
            "errors": list(state.get("errors", [])) + ["solver:missing_solver_skill"],
        }

    system_prompt = _load_text("prompts/solver_agent.md")
    task_skill = _load_text(profile.solver_skill)

                                                                                 
                                                                                
    user_prompt = f"""
ПРОФИЛЬ: {profile.id} — {profile.title}

УСЛОВИЕ:
{statement}

TASK-SPECIFIC SKILL (используй как ориентир, но ответ должен быть кратким):
{task_skill}

Верни ТОЛЬКО короткий JSON по schema.
Никакого развёрнутого решения, комментариев, LaTeX-блоков и списков шагов.

Требования к machine_spec:
- variable: обычно x;
- general_solution_families: все семейства общего решения в SymPy-синтаксисе;
- part_b: границы отрезка и корни, которые ты считаешь подходящими;
- выражения: pi, sqrt, sin, cos, tan, log, exp, **;
- parameter должен быть целочисленным параметром, обычно n.

Пример формата семейства: {{"expression":"-pi/6 + pi*n","parameter":"n"}}.
Не оценивай ученика. Решение ученика тебе не передано.
""".strip()

                                                                             
    solver_schema = {
        "type": "object",
        "properties": {
            "can_solve": {"type": "boolean"},
            "final_answer_part_a": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "machine_spec": {
                "type": "object",
                "properties": {
                    "variable": {"type": "string"},
                    "general_solution_families": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "expression": {"type": "string"},
                                "parameter": {"type": "string"},
                            },
                            "required": ["expression", "parameter"],
                            "additionalProperties": False,
                        },
                    },
                    "part_b": {
                        "type": "object",
                        "properties": {
                            "has_interval": {"type": "boolean"},
                            "interval_left": {"type": "string"},
                            "interval_right": {"type": "string"},
                            "left_closed": {"type": "boolean"},
                            "right_closed": {"type": "boolean"},
                            "selected_roots": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "has_interval",
                            "interval_left",
                            "interval_right",
                            "left_closed",
                            "right_closed",
                            "selected_roots",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["variable", "general_solution_families", "part_b"],
                "additionalProperties": False,
            },
        },
        "required": ["can_solve", "final_answer_part_a", "confidence", "machine_spec"],
        "additionalProperties": False,
    }

    try:
        result = ollama_chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=get_solver_model(),
            response_schema=solver_schema,
            num_ctx=4096,
            num_predict=560,
        )
    except OllamaError as exc:
                                                                                   
                                                                                   
        return {
            "solver_ok": False,
            "solver_model": "ollama-error",
            "solver_confidence": 0.0,
            "solver_error": str(exc),
            "solver_machine_spec": {},
            "reference_answer_part_a": "",
            "warnings": list(state.get("warnings", [])) + [f"solver:{exc}"],
        }

    can_solve = bool(result.get("can_solve", True))
    final_answer_part_a = str(result.get("final_answer_part_a", "")).strip()
    machine_spec = result.get("machine_spec")

    try:
        confidence = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    solver_ok = bool(
        can_solve
        and final_answer_part_a
        and isinstance(machine_spec, dict)
        and confidence >= 0.60
    )

    payload = {
        "solver_ok": solver_ok,
        "solver_model": str(result.get("_model", get_solver_model())),
        "solver_elapsed_seconds": float(result.get("_elapsed_seconds", 0) or 0),
        "solver_confidence": confidence,
        "solver_error": "" if solver_ok else "low_confidence_or_incomplete_output",
        "reference_answer_part_a": final_answer_part_a,
        "solver_machine_spec": machine_spec if isinstance(machine_spec, dict) else {},
                                                                                               
        "reference_solution": "",
        "reference_steps": [],
        "key_checkpoints": list(profile.required_checkpoints),
        "solver_notes": "machine-first structured pass",
    }

    if not solver_ok:
        payload["warnings"] = list(state.get("warnings", [])) + ["solver:low_confidence_or_incomplete_output"]
    return payload
