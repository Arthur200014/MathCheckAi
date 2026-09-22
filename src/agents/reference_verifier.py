from __future__ import annotations

from src.state import ReviewState
from src.task_registry import TaskProfile, get_task_profile
from src.tools.registry import run_reference_verifier


def _profile_from_state(state: ReviewState) -> TaskProfile:
    raw = state.get("task_profile")
    if raw:
        return TaskProfile.model_validate(raw)
    return get_task_profile(state.get("task_type", ""))


def reference_verifier_agent(state: ReviewState) -> dict:





    try:
        profile = _profile_from_state(state)
    except Exception as exc:
        return {
            "reference_verification_ok": False,
            "reference_verification_status": "TASK_PROFILE_ERROR",
            "reference_verification_errors": [str(exc)],
        }

    verifier_name = profile.reference_verifier
    if not verifier_name:
        return {
            "reference_verification_ok": False,
            "reference_verification_status": "REFERENCE_VERIFIER_NOT_CONFIGURED",
            "reference_verification_errors": ["Task profile has no reference_verifier"],
        }

    spec = state.get("solver_machine_spec")
    if not isinstance(spec, dict):
        spec = {}

    try:
        verification = run_reference_verifier(
            verifier_name,
            spec,
            task_statement=state.get("task_statement", ""),
        )
    except Exception as exc:
        return {
            "reference_verification_ok": False,
            "reference_verification_status": "REFERENCE_VERIFIER_ERROR",
            "reference_verification_errors": [str(exc)],
        }

    payload = {
        "reference_verification_ok": bool(verification.ok),
        "reference_verification_status": verification.status,
        "reference_verification_results": verification.results,
        "reference_verification_errors": verification.errors,
        "reference_expected_roots": verification.expected_roots,
        "reference_solver_selected_roots": verification.selected_roots,
        "reference_answer_part_b_verified": verification.corrected_answer_part_b,
        "reference_answer_part_a_verified": verification.corrected_answer_part_a,
        "reference_equation_source": verification.equation_source,
        "reference_verified_families": verification.verified_families,
        "solver_fallback_used": bool(verification.solver_fallback_used),
    }

    if verification.ok:
        part_a = verification.corrected_answer_part_a.strip()
        part_b = verification.corrected_answer_part_b.strip()
        payload["reference_answer_raw"] = state.get("reference_answer", "")
        payload["reference_answer_part_a"] = part_a
        payload["reference_answer"] = f"а) {part_a}; б) {part_b}".strip()
        payload["reference_solution"] = (
            "Проверенный машинный эталон: общее решение получено/подтверждено "
            "детерминированным SymPy-слоем; корни пункта б вычислены независимо "
            "по условию задачи и проверенным семействам."
        )
        payload["reference_steps"] = [
            "Исходное уравнение восстановлено непосредственно из task_statement.",
            "SymPy независимо построил/проверил множество решений пункта а).",
            "Интервал пункта б восстановлен непосредственно из task_statement.",
            "Корни на интервале перечислены детерминированно по проверенным семействам.",
        ]

    return payload
