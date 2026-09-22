from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskProfile(BaseModel):
    

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    max_score: int = Field(ge=0)
    enabled: bool = True

    solver_skill: str | None = None
    grader_skill: str | None = None
    criteria_path: str | None = None

    tool_names: list[str] = Field(default_factory=list)
    required_checkpoints: list[str] = Field(default_factory=list)

    requires_diagram: bool = False
    diagram_tool: str | None = None
    diagram_reader_skill: str | None = None
    diagram_rubric_path: str | None = None
    diagram_error_catalog: str | None = None
    supports_sympy: bool = True
    reference_verifier: str | None = None
    manual_review_on: list[str] = Field(default_factory=list)
    implementation_note: str = ""


class UnknownTaskTypeError(ValueError):
    pass


class TaskTypeNotImplementedError(ValueError):
    pass


TASK_REGISTRY: dict[str, TaskProfile] = {
    "ege_13": TaskProfile(
        id="ege_13",
        title="Тригонометрическое уравнение и отбор корней",
        max_score=2,
        solver_skill="skills/task_13/solve.md",
        grader_skill="skills/task_13/grade.md",
        criteria_path="criteria/task_13.md",
        tool_names=[
            "load_criteria",
            "verify_expression",
            "verify_roots",
            "render_trig_circle",
            "save_review",
            "load_student_history",
            "save_report",
        ],
        required_checkpoints=[
            "trig_transformation",
            "division_domain_check",
            "general_solution",
            "integer_parameter",
            "interval_root_selection",
            "final_answer_by_parts",
        ],
        requires_diagram=False,
        diagram_tool="render_trig_circle",
        diagram_reader_skill=None,
        diagram_rubric_path=None,
        diagram_error_catalog=None,
        supports_sympy=True,
        reference_verifier="verify_ege13_reference",
        manual_review_on=[
            "ambiguous_task_statement",
            "unsupported_nonstandard_method",
            "solver_low_confidence",
        ],
        implementation_note="Task pack №13: 4-agent sequential LangGraph flow for one local accelerator; original-quality Vision input; deterministic SymPy reference verification; mandatory human confirmation of task statement + student OCR; source-locked student evidence from confirmed transcript; deterministic family/root verification; compact per-step expert report; verified trig-circle renderer. Student diagram OCR is deferred from MVP for latency.",
    ),
   
    "ege_15": TaskProfile(
        id="ege_15",
        title="Неравенство",
        max_score=2,
        enabled=False,
        solver_skill=None,
        grader_skill=None,
        criteria_path="criteria/task_15.md",
        tool_names=["verify_expression", "solve_inequality"],
        required_checkpoints=[
            "domain_restrictions",
            "equivalent_transformations",
            "critical_points",
            "interval_method",
            "final_interval",
        ],
        requires_diagram=False,
        supports_sympy=True,
        implementation_note="Зарегистрирован как следующий MVP task pack; пока отключён.",
    ),
}


def get_task_profile(task_type: str, *, require_enabled: bool = True) -> TaskProfile:
    normalized = str(task_type).strip()
    profile = TASK_REGISTRY.get(normalized)
    if profile is None:
        raise UnknownTaskTypeError(f"Неизвестный тип задания: {normalized or '<empty>'}")
    if require_enabled and not profile.enabled:
        raise TaskTypeNotImplementedError(
            f"Тип задания {normalized} зарегистрирован, но его task pack ещё не реализован."
        )
    return profile


def list_task_profiles() -> list[dict]:
    
    return [
        {
            "id": profile.id,
            "title": profile.title,
            "max_score": profile.max_score,
            "enabled": profile.enabled,
            "requires_diagram": profile.requires_diagram,
            "supports_sympy": profile.supports_sympy,
            "implementation_note": profile.implementation_note,
        }
        for profile in TASK_REGISTRY.values()
    ]


def load_task_profile_node(state: dict) -> dict:
    
    try:
        profile = get_task_profile(state.get("task_type", ""))
    except (UnknownTaskTypeError, TaskTypeNotImplementedError) as exc:
        return {
            "task_profile_ok": False,
            "status": "UNSUPPORTED_TASK_TYPE",
            "feedback": str(exc),
            "errors": list(state.get("errors", [])) + [f"task_registry:{exc}"],
        }

    return {
        "task_profile_ok": True,
        "task_title": profile.title,
        "task_max_score": profile.max_score,
        "task_profile": profile.model_dump(),
    }
