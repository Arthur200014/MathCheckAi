from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.llm.config import get_reviewer_model
from src.llm.ollama_client import OllamaError, ollama_chat_json
from src.state import ReviewState
from src.tools.core import compact_criteria_summary
from src.tools.ege13_student import extract_ege13_explicit_final_answer

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "consistent": {"type": "boolean"},
            "manual_review_required": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "score_agrees": {"type": "boolean"},
            "reason_codes": {"type": "array", "items": {"type": "string", "maxLength": 120}, "maxItems": 4},
        },
        "required": ["consistent", "manual_review_required", "confidence", "score_agrees", "reason_codes"],
        "additionalProperties": False,
    }


def _call_once(system_prompt: str, user_prompt: str) -> dict[str, Any]:

    return ollama_chat_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=get_reviewer_model(),
        response_schema=_schema(),
        num_ctx=3072,
        use_num_predict_limit=False,
    )


def _reviewer_telemetry_fields(llm_or_telemetry: dict[str, Any] | None) -> dict[str, Any]:
    source = llm_or_telemetry or {}
    telemetry = source.get("_ollama_telemetry", source) if isinstance(source, dict) else {}
    raw_len = telemetry.get("raw_output_length") or telemetry.get("partial_output_chars") or 0
    return {
        "reviewer_output_chars": int(telemetry.get("partial_output_chars") or raw_len or 0),
        "reviewer_raw_output_length": int(raw_len or 0),
        "reviewer_output_tokens": telemetry.get("output_tokens"),
        "reviewer_done_reason": telemetry.get("done_reason"),
        "reviewer_raw_output_preview": str(telemetry.get("raw_output_preview") or ""),
    }


def reviewer_agent(state: ReviewState) -> dict:







    if state.get("task_type") != "ege_13":
        return {
            "reviewer_ok": False,
            "reviewer_manual_review_required": True,
            "reviewer_error": "unsupported_task_type",
            "status": "MANUAL_REVIEW_REQUIRED",
        }

    if state.get("draft_score") is None:
                                                                             
                                                                        
        return {
            "reviewer_ok": False,
            "reviewer_manual_review_required": True,
            "reviewer_error": "grader_did_not_produce_score",
            "status": "MANUAL_REVIEW_REQUIRED",
            "feedback": "Не удалось получить даже детерминированный черновой балл.",
        }

    draft_score = int(state.get("draft_score", 0))
    max_score = int(state.get("task_max_score", state.get("max_score", 2)))
    transcript = str(state.get("confirmed_transcript") or state.get("transcript") or "")
    answer_lock = extract_ege13_explicit_final_answer(transcript) if transcript else None
    answer_lock_applied = bool(answer_lock and answer_lock.final_answer_found and answer_lock.final_part_b_roots)

    diagram_invalid = bool(state.get("grader_diagram_override_applied", False)) or (
        bool(state.get("diagram_method_used", False)) and state.get("diagram_part_b_valid") is False
    )
    diagram_unverified_nonblocking = (
        bool(state.get("diagram_method_used", False))
        and state.get("diagram_part_b_valid") is None
        and state.get("grader_part_a_equivalent") is True
        and state.get("grader_part_b_roots_match") is True
    )
    explicit_final_answer_mismatch = answer_lock_applied and state.get("grader_part_b_roots_match") is False

    part_a_status = state.get("grader_part_a_status")
    if not part_a_status:
        if state.get("grader_part_a_equivalent") is True:
            part_a_status = "correct"
        elif state.get("grader_part_a_equivalent") is False:
            part_a_status = "substantive_error"
        else:
            part_a_status = "uncertain"

    part_b_status = state.get("grader_part_b_status")
    if not part_b_status:
        if state.get("grader_part_b_roots_match") is True:
            part_b_status = "correct"
        elif state.get("grader_part_b_roots_match") is False:
            part_b_status = "incorrect"
        else:
            part_b_status = "uncertain"

    error_class = state.get("grader_error_class")
    if not error_class:
        if part_a_status in {"substantive_error", "missing"}:
            error_class = "substantive_math_error"
        elif part_b_status in {"incorrect", "missing"}:
            error_class = "root_selection_error"
        elif part_a_status == "correct" and part_b_status == "correct":
            error_class = "none"
        else:
            error_class = "ambiguous"

    if diagram_invalid:
        part_b_status = "incorrect"
        error_class = "diagram_selection_error"

    deterministic_conflicts: list[str] = []
    if state.get("grader_part_b_roots_match") is False and draft_score == 2:
        deterministic_conflicts.append("score_2_with_wrong_part_b_roots")
    if state.get("grader_part_a_equivalent") is False and draft_score > 1:
        deterministic_conflicts.append("positive_high_score_with_non_equivalent_part_a")
    if state.get("grader_part_b_status") == "missing" and draft_score == 2:
        deterministic_conflicts.append("score_2_with_missing_part_b")
    if not state.get("reference_verification_ok", False):
        deterministic_conflicts.append("reference_not_verified")

    audit = {
        "score_to_audit": draft_score,
        "max_score": max_score,
        "part_a_status": part_a_status,
        "part_b_status": part_b_status,
        "error_class": error_class,
        "part_a_equivalent": state.get("grader_part_a_equivalent"),
        "part_b_roots_match": state.get("grader_part_b_roots_match"),
        "student_evidence_source": state.get("grader_student_evidence_source"),
        "grader_invariant_overrides": state.get("grader_invariant_overrides", []),
        "grader_advisories": state.get("grader_review_advisories", []),
        "deterministic_conflicts": deterministic_conflicts,
        "explicit_final_answer_locked": answer_lock_applied,
        "reference_verification_ok": state.get("reference_verification_ok", False),
    }

    system_prompt = _load("prompts/reviewer_agent.md")
    criteria_summary = compact_criteria_summary("ege_13")
    user_prompt = f"""Проверь только непротиворечивость уже рассчитанного результата.
КРИТЕРИИ: {criteria_summary}
AUDIT DATA: {json.dumps(audit, ensure_ascii=False)}
Не решай задачу заново и НЕ вычисляй другой балл. score_to_audit неизменяем.
Если есть сомнение, укажи его как reason/manual advisory, но не отменяй балл. Верни только JSON schema."""

    llm_error = ""
    llm_error_code = ""
    try:
        llm = _call_once(system_prompt, user_prompt)
        telemetry_fields = _reviewer_telemetry_fields(llm)
        if "consistent" in llm or "score_agrees" in llm:
            consistent = bool(llm.get("consistent", False)) and bool(llm.get("score_agrees", False))
            reasons = [str(x) for x in llm.get("reason_codes", [])]
            reviewer_manual = bool(llm.get("manual_review_required", False)) or not consistent
        else:
                                                                                 
            proposed = int(llm.get("proposed_score", draft_score))
            reviewer_manual = bool(llm.get("manual_review_required", False)) or proposed != draft_score
            consistent = not reviewer_manual
            reasons = [str(x) for x in llm.get("evidence", [])]
            if proposed != draft_score:
                reasons.append(f"reviewer_score_disagrees_with_grader:{proposed}!={draft_score}")
    except OllamaError as exc:
        telemetry = getattr(exc, "telemetry", {}) or {}
        llm = {
            "confidence": 0.0,
            "consistent": False,
            "score_agrees": False,
            "manual_review_required": True,
            "reason_codes": ["reviewer_llm_failed"],
            "_model": str(telemetry.get("model") or "ollama-error"),
            "_elapsed_seconds": float(telemetry.get("wall_seconds") or 0),
        }
        telemetry_fields = _reviewer_telemetry_fields(telemetry)
        llm_error = str(exc)
        llm_error_code = getattr(exc, "code", "OLLAMA_ERROR")
        consistent = False
        reviewer_manual = True
        reasons = ["reviewer_llm_failed"]

    if diagram_unverified_nonblocking and not deterministic_conflicts and not llm_error:
        reviewer_manual = False
        consistent = True

    all_advisories = []
    all_advisories.extend(str(x) for x in state.get("grader_review_advisories", []))
    all_advisories.extend(str(x) for x in state.get("grader_conflicts", []))
    if state.get("grader_manual_review_required", False) and not state.get("grader_review_advisories"):
        all_advisories.append("grader_manual_review_advisory")
    all_advisories.extend(deterministic_conflicts)
    all_advisories.extend(reasons if reviewer_manual else [])

    warnings = list(state.get("warnings", []))
    warnings.extend(f"review_advisory:{x}" for x in all_advisories if x)
    if diagram_unverified_nonblocking:
        warnings.append("diagram_unverified_no_penalty")
    if llm_error:
        warnings.append(f"reviewer:{llm_error_code}")

    reviewer_overrides = ["reviewer_cannot_change_draft_score"]
    if diagram_invalid:
        reviewer_overrides.append("reviewer_llm_score_overridden_by_diagram:score_is_immutable")
    if diagram_unverified_nonblocking:
        reviewer_overrides.append("reviewer_llm_score_overridden_unreadable_diagram_no_proven_error:score_is_immutable")
    if explicit_final_answer_mismatch:
        reviewer_overrides.append("reviewer_llm_score_overridden_by_explicit_final_answer:score_is_immutable")

                                                             
    return {
        "reviewer_ok": not bool(deterministic_conflicts) and not bool(llm_error),
        "reviewer_model": str(llm.get("_model", get_reviewer_model())),
        "reviewer_elapsed_seconds": float(llm.get("_elapsed_seconds", 0) or 0),
        "reviewer_retry_used": False,
        "reviewer_confidence": float(llm.get("confidence", 0) or 0),
        "reviewer_manual_review_required": bool(reviewer_manual or all_advisories),
        "reviewer_review_advisory_only": bool(reviewer_manual or all_advisories),
        "reviewer_error": llm_error,
        "reviewer_error_code": llm_error_code,
        "reviewer_assessment": "consistent" if consistent and not deterministic_conflicts else "warning",
        "reviewer_proposed_score_llm": -1,
        "reviewer_score_source": "deterministic_grader_rubric_audited_by_reviewer",
        "reviewer_independent_score": draft_score,
        "reviewer_conflicts": deterministic_conflicts,
        "reviewer_evidence": reasons,
        "reviewer_overrides": reviewer_overrides,
        "reviewer_part_a_status": part_a_status,
        "reviewer_part_b_status": part_b_status,
        "reviewer_error_class": error_class,
        "reviewer_part_a_equivalent": state.get("grader_part_a_equivalent"),
        "reviewer_part_b_roots_match": state.get("grader_part_b_roots_match"),
        "reviewer_diagram_override_applied": diagram_invalid,
        "reviewer_diagram_unverified_ignored_for_score": diagram_unverified_nonblocking,
        "reviewer_student_answer_lock_applied": answer_lock_applied,
        "reviewer_student_final_answer_part_b": list(answer_lock.final_part_b_roots) if answer_lock else [],
        "reviewer_student_final_answer_source_text": answer_lock.source_text if answer_lock else "",
        "reviewer_student_answer_extraction_errors": list(answer_lock.errors) if answer_lock else [],
        "reviewer_student_machine_spec": {},
        **telemetry_fields,
        "final_score": draft_score,
        "max_score": max_score,
        "status": "REVIEWED",
        "feedback": f"Итоговый балл рассчитан по подтверждённой работе: {draft_score}/{max_score}.",
        "errors": list(state.get("errors", [])),
        "warnings": warnings,
    }
# fix
