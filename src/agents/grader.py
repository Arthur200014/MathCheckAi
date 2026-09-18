from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.llm.config import get_grader_model
from src.llm.ollama_client import OllamaError, ollama_chat_json
from src.state import ReviewState
from src.tools.core import compact_criteria_summary, load_criteria, load_runtime_rubric
from src.tools.ege13_reasoning import deterministic_reasoning_overrides_ege13
from src.tools.ege13_report import extract_solution_steps, normalize_step_assessments
from src.tools.ege13_rubric import apply_ege13_rubric, resolve_confirmed_ege13_score
from src.tools.ege13_student import (
    extract_ege13_explicit_final_answer,
    extract_ege13_student_evidence,
    verify_ege13_student_machine_spec,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _grader_schema() -> dict[str, Any]:
    """Semantic-only Grader schema.

    Student mathematical facts are deliberately absent. They are extracted by a
    deterministic, transcript-only layer before the LLM call. This prevents the
    Grader from copying/reconstructing reference values into student_* fields.
    """
    return {
        "type": "object",
        "properties": {
            "can_grade": {"type": "boolean"},
            "part_a_status": {
                "type": "string",
                "enum": ["correct", "computation_error_only", "substantive_error", "missing", "uncertain"],
            },
            "part_b_status": {
                "type": "string",
                "enum": ["correct", "incorrect", "missing", "uncertain"],
            },
            "overall_sequence_correct_both_parts": {"type": "boolean"},
            "error_class": {
                "type": "string",
                "enum": ["none", "computation_error", "substantive_math_error", "root_selection_error", "ambiguous"],
            },
            "manual_review_required": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "checked_step_ids": {
                "type": "array",
                "maxItems": 24,
                "items": {"type": "string", "maxLength": 12},
            },
            "issue_steps": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "step_id": {"type": "string"},
                        "status": {"type": "string", "enum": ["incorrect", "uncertain"]},
                        "comment": {"type": "string", "maxLength": 180},
                    },
                    "required": ["step_id", "status", "comment"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "can_grade",
            "part_a_status",
            "part_b_status",
            "overall_sequence_correct_both_parts",
            "error_class",
            "manual_review_required",
            "confidence",
            "checked_step_ids",
            "issue_steps",
        ],
        "additionalProperties": False,
    }


def _call_grader_llm_once(*, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Exactly one Grader LLM call, with no application output cap and no retry."""
    return ollama_chat_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=get_grader_model(),
        response_schema=_grader_schema(),
        num_ctx=6144,
        use_num_predict_limit=False,
    )


def _llm_telemetry_fields(llm_or_telemetry: dict[str, Any] | None) -> dict[str, Any]:
    source = llm_or_telemetry or {}
    telemetry = source.get("_ollama_telemetry", source) if isinstance(source, dict) else {}
    raw_len = telemetry.get("raw_output_length") or telemetry.get("partial_output_chars") or 0
    return {
        "grader_output_chars": int(telemetry.get("partial_output_chars") or raw_len or 0),
        "grader_raw_output_length": int(raw_len or 0),
        "grader_output_tokens": telemetry.get("output_tokens"),
        "grader_done_reason": telemetry.get("done_reason"),
        "grader_raw_output_preview": str(telemetry.get("raw_output_preview") or ""),
    }


def _apply_rubric(
    *,
    llm: dict[str, Any],
    part_a_equivalent: bool | None,
    part_b_matches: bool | None,
    diagram_part_b_valid: bool | None = None,
    diagram_method_used: bool = False,
):
    # Kept for legacy tests/imports. Runtime scoring below uses the confirmed-
    # transcript resolver that never withholds a score solely due to LLM caution.
    return apply_ege13_rubric(
        assessment=llm,
        part_a_equivalent=part_a_equivalent,
        part_b_matches=part_b_matches,
        diagram_part_b_valid=None,
        diagram_method_used=False,
    )


def _fallback_semantic_assessment(*, evidence, math_check) -> dict[str, Any]:
    if math_check.part_a_equivalent is True:
        a_status = "correct"
    elif math_check.part_a_equivalent is False:
        a_status = "substantive_error"
    elif not evidence.general_solution_families:
        a_status = "missing"
    else:
        a_status = "uncertain"

    if not evidence.part_b_present:
        b_status = "missing"
    elif math_check.part_b_matches is True:
        b_status = "correct"
    elif math_check.part_b_matches is False:
        b_status = "incorrect"
    else:
        b_status = "uncertain"

    if a_status in {"substantive_error", "missing"}:
        error_class = "substantive_math_error"
    elif b_status in {"incorrect", "missing"}:
        error_class = "root_selection_error"
    elif a_status == "correct" and b_status == "correct":
        error_class = "none"
    else:
        error_class = "ambiguous"

    return {
        "can_grade": True,
        "part_a_status": a_status,
        "part_b_status": b_status,
        "overall_sequence_correct_both_parts": a_status == "correct" and b_status == "correct",
        "error_class": error_class,
        "manual_review_required": True,
        "confidence": 0.0,
        "checked_step_ids": [],
        "issue_steps": [],
    }


def _enforce_source_locked_invariants(*, assessment: dict[str, Any], evidence, math_check) -> tuple[dict[str, Any], list[str]]:
    """Make impossible states impossible before scoring/reporting."""
    out = dict(assessment)
    overrides: list[str] = []

    a_status = str(out.get("part_a_status", "uncertain"))
    b_status = str(out.get("part_b_status", "uncertain"))
    error_class = str(out.get("error_class", "ambiguous"))

    if math_check.part_a_equivalent is False:
        computation_exception = (
            a_status == "computation_error_only"
            and error_class == "computation_error"
            and bool(out.get("overall_sequence_correct_both_parts", False))
        )
        if not computation_exception:
            if a_status != "substantive_error":
                overrides.append(f"part_a_status:{a_status}->substantive_error")
            a_status = "substantive_error"
            error_class = "substantive_math_error"
    elif math_check.part_a_equivalent is True and a_status in {"uncertain", "missing"}:
        overrides.append(f"part_a_status:{a_status}->correct_by_deterministic_equivalence")
        a_status = "correct"

    if not evidence.part_b_present:
        if b_status != "missing":
            overrides.append(f"part_b_status:{b_status}->missing_from_confirmed_transcript")
        b_status = "missing"
    elif math_check.part_b_matches is False:
        if b_status != "incorrect":
            overrides.append(f"part_b_status:{b_status}->incorrect_by_transcript_roots")
        b_status = "incorrect"
    elif math_check.part_b_matches is True and b_status in {"uncertain", "missing"}:
        overrides.append(f"part_b_status:{b_status}->correct_by_deterministic_roots")
        b_status = "correct"

    if a_status in {"substantive_error", "missing"}:
        error_class = "substantive_math_error"
    elif b_status in {"incorrect", "missing"} and error_class in {"none", "ambiguous"}:
        error_class = "root_selection_error"
    elif a_status == "correct" and b_status == "correct" and error_class == "ambiguous":
        error_class = "none"

    out["part_a_status"] = a_status
    out["part_b_status"] = b_status
    out["error_class"] = error_class
    out["overall_sequence_correct_both_parts"] = a_status == "correct" and b_status == "correct"
    return out, overrides


def grader_agent(state: ReviewState) -> dict:
    """Third agent: source-locked grading over a confirmed transcript.

    Architecture rule: student_* facts come only from the confirmed transcript.
    The LLM may classify reasoning, but it cannot author, repair or replace the
    student's mathematical families/selected roots.
    """
    if state.get("task_type") != "ege_13":
        return {
            "grader_mode": "unsupported",
            "grader_ok": False,
            "grader_manual_review_required": True,
            "grader_error": "unsupported_task_type",
        }

    transcript = str(state.get("confirmed_transcript") or state.get("transcript") or "").strip()
    if not transcript:
        return {
            "grader_mode": "real",
            "grader_ok": False,
            "grader_manual_review_required": True,
            "grader_error": "empty_confirmed_transcript",
        }

    profile = state.get("task_profile", {})
    criteria_path = str(profile.get("criteria_path", "criteria/task_13.md"))
    full_criteria = load_criteria("ege_13")
    criteria_summary = compact_criteria_summary("ege_13")
    rubric = load_runtime_rubric("ege_13")
    grader_skill_path = str(profile.get("grader_skill", "skills/task_13/grade.md"))
    grader_skill = _load(grader_skill_path) if grader_skill_path else ""
    system_prompt = _load("prompts/grader_agent.md")

    student_steps = extract_solution_steps(transcript, max_steps=24)
    student_evidence = extract_ege13_student_evidence(transcript)
    student_spec = student_evidence.machine_spec()
    math_check = verify_ege13_student_machine_spec(
        student_spec,
        task_statement=str(state.get("task_statement", "")),
        reference_families=list(state.get("reference_verified_families", [])),
        expected_roots=list(state.get("reference_expected_roots", [])),
    )
    deterministic_step_overrides = deterministic_reasoning_overrides_ege13(
        student_steps,
        task_statement=str(state.get("task_statement", "")),
        expected_roots=list(state.get("reference_expected_roots", [])),
    )

    answer_lock = extract_ege13_explicit_final_answer(transcript)
    verified_reference = {
        "families": state.get("reference_verified_families", []),
        "expected_roots": state.get("reference_expected_roots", []),
        "answer_a": state.get("reference_answer_part_a_verified", ""),
        "answer_b": state.get("reference_answer_part_b_verified", ""),
    }
    prompt_payload = {
        "task_statement": state.get("task_statement", ""),
        "student_steps": student_steps,
        "student_evidence_FROM_CONFIRMED_TRANSCRIPT_ONLY": {
            "part_a_present": student_evidence.part_a_present,
            "part_b_present": student_evidence.part_b_present,
            "general_solution_families": student_evidence.general_solution_families,
            "selected_roots": student_evidence.selected_roots,
            "source": student_evidence.source,
        },
        "deterministic_math": {
            "part_a_equivalent": math_check.part_a_equivalent,
            "part_b_roots_match": math_check.part_b_matches,
            "errors": math_check.errors,
        },
        "verified_reference": verified_reference,
        "criteria_summary": criteria_summary,
        "rubric": rubric,
        "skill": grader_skill[:1900],
    }
    user_prompt = (
        "Проверь рассуждения ученика по критериям. Student evidence уже извлечён ДО тебя только из подтверждённой транскрипции. "
        "НЕ создавай и НЕ исправляй student_machine_spec, семейства или корни. "
        "Детерминированные student_evidence/deterministic_math имеют приоритет над твоей интерпретацией. "
        "IMMUTABLE DETERMINISTIC FINAL-ANSWER EXTRACTION и source-locked student evidence имеют приоритет. "
        "НЕ выставляй балл. В checked_step_ids перечисли каждый реально просмотренный step_id; "
        "в issue_steps — только ошибочные/неоднозначные шаги. Один вызов, без retry. Верни только JSON schema.\n\n"
        + json.dumps(prompt_payload, ensure_ascii=False)
    )

    llm_error = ""
    llm_error_code = ""
    try:
        llm = _call_grader_llm_once(system_prompt=system_prompt, user_prompt=user_prompt)
        telemetry_fields = _llm_telemetry_fields(llm)
    except OllamaError as exc:
        telemetry = getattr(exc, "telemetry", {}) or {}
        llm = _fallback_semantic_assessment(evidence=student_evidence, math_check=math_check)
        llm_error = str(exc)
        llm_error_code = getattr(exc, "code", "OLLAMA_ERROR")
        telemetry_fields = _llm_telemetry_fields(telemetry)
        llm["_model"] = str(telemetry.get("model") or "ollama-error")
        llm["_elapsed_seconds"] = float(telemetry.get("wall_seconds") or 0)

    assessment, invariant_overrides = _enforce_source_locked_invariants(
        assessment=llm,
        evidence=student_evidence,
        math_check=math_check,
    )

    diagram_method_used = bool(state.get("diagram_method_used", False))
    diagram_part_b_valid = state.get("diagram_part_b_valid") if diagram_method_used else None
    diagram_invalid = diagram_method_used and diagram_part_b_valid is False
    diagram_unverified_nonblocking = (
        diagram_method_used
        and diagram_part_b_valid is None
        and math_check.part_a_equivalent is True
        and math_check.part_b_matches is True
    )
    if diagram_invalid:
        assessment["part_b_status"] = "incorrect"
        if assessment.get("part_a_status") == "correct":
            assessment["error_class"] = "diagram_selection_error"
        assessment["overall_sequence_correct_both_parts"] = False

    score, rubric_reason, score_warnings = resolve_confirmed_ege13_score(
        assessment=assessment,
        part_a_equivalent=math_check.part_a_equivalent,
        part_b_matches=False if diagram_invalid else math_check.part_b_matches,
        part_b_present=student_evidence.part_b_present,
    )
    if diagram_invalid and score == 1:
        rubric_reason = "part_a_correct_part_b_diagram_error"
    elif diagram_unverified_nonblocking and score == 2:
        rubric_reason = "both_parts_correct_unreadable_diagram_no_proven_error"

    explicit_final_answer_mismatch = bool(
        student_evidence.explicit_final_answer_used and math_check.part_b_matches is False
    )
    step_assessments = normalize_step_assessments(
        student_steps,
        llm.get("issue_steps", []),
        explicit_final_answer_mismatch=explicit_final_answer_mismatch,
        diagram_invalid=diagram_invalid,
        sparse_issues=True,
        checked_step_ids=list(llm.get("checked_step_ids", [])),
        deterministic_overrides=deterministic_step_overrides,
    )

    advisory_reasons: list[str] = []
    fully_math_confirmed = (
        math_check.part_a_equivalent is True
        and student_evidence.part_b_present
        and math_check.part_b_matches is True
        and not student_evidence.errors
    )
    if bool(llm.get("manual_review_required", False)) and not fully_math_confirmed:
        advisory_reasons.append("grader_requested_manual_review")
    if llm_error:
        advisory_reasons.append(f"grader_llm_error:{llm_error_code}")
    advisory_reasons.extend(str(x) for x in student_evidence.errors)
    advisory_reasons.extend(score_warnings)

    evidence_rows = [
        "student_evidence_source:confirmed_transcript_only",
        f"student_part_b_present:{str(student_evidence.part_b_present).lower()}",
    ]
    if math_check.part_a_equivalent is not None:
        evidence_rows.append(f"student_part_a_periodic_set_equivalence:{str(math_check.part_a_equivalent).lower()}")
    if math_check.part_b_matches is not None:
        evidence_rows.append(f"student_part_b_roots_match_reference:{str(math_check.part_b_matches).lower()}")
    evidence_rows.extend(f"invariant_override:{x}" for x in invariant_overrides)
    if diagram_invalid:
        evidence_rows.append("diagram_verified_invalid")
    elif diagram_unverified_nonblocking:
        evidence_rows.append("diagram_unverified_no_penalty_no_proven_student_error")

    feedback = "Баллы рассчитаны по подтверждённой транскрипции и детерминированным проверкам."
    if advisory_reasons:
        feedback += " Есть предупреждения проверки, но они не блокируют выставление балла."

    return {
        "grader_mode": "real",
        "grader_ok": True,
        "grader_model": str(llm.get("_model", get_grader_model())),
        "grader_elapsed_seconds": float(llm.get("_elapsed_seconds", 0) or 0),
        "grader_retry_used": False,
        "grader_confidence": float(llm.get("confidence", 0) or 0),
        "grader_manual_review_required": bool(advisory_reasons),
        "grader_review_advisory_only": bool(advisory_reasons),
        "grader_review_advisories": advisory_reasons,
        "grader_error": llm_error,
        "grader_error_code": llm_error_code,
        "grader_part_a_status": assessment.get("part_a_status"),
        "grader_part_b_status": assessment.get("part_b_status"),
        "grader_error_class": assessment.get("error_class"),
        "grader_overall_sequence_correct_both_parts": bool(assessment.get("overall_sequence_correct_both_parts", False)),
        "grader_evidence": evidence_rows,
        "grader_feedback": feedback,
        "grader_proposed_score_llm": -1,
        "grader_score_source": "deterministic_ege13_rubric",
        "grader_score_provenance": "source_locked_confirmed_transcript",
        "grader_student_evidence_source": student_evidence.source,
        "grader_student_evidence": {
            "part_a_present": student_evidence.part_a_present,
            "part_b_present": student_evidence.part_b_present,
            "general_solution_families": student_evidence.general_solution_families,
            "selected_roots": student_evidence.selected_roots,
            "family_sources": student_evidence.family_sources,
            "selected_root_sources": student_evidence.selected_root_sources,
            "errors": student_evidence.errors,
        },
        "grader_student_machine_spec": student_spec,
        "grader_llm_selected_roots_before_answer_lock": [],
        "grader_student_answer_lock_applied": student_evidence.explicit_final_answer_used,
        "grader_student_final_answer_part_b": list(answer_lock.final_part_b_roots),
        "grader_student_final_answer_source_text": answer_lock.source_text,
        "grader_student_answer_extraction_errors": list(answer_lock.errors),
        "grader_student_math_results": math_check.results,
        "grader_student_math_errors": math_check.errors,
        "grader_part_a_equivalent": math_check.part_a_equivalent,
        "grader_part_b_roots_match": math_check.part_b_matches,
        "grader_student_selected_roots": math_check.student_roots,
        "grader_rubric_reason": rubric_reason,
        "grader_diagram_override_applied": diagram_invalid,
        "grader_diagram_unverified_ignored_for_score": diagram_unverified_nonblocking,
        "grader_conflicts": [],
        "grader_invariant_overrides": invariant_overrides,
        **telemetry_fields,
        "student_steps": student_steps,
        "grader_step_assessments": step_assessments,
        "criteria_source": criteria_path,
        "criteria_rubric": "criteria/task_13_rubric.json",
        "criteria_loaded": bool(full_criteria and rubric),
        "draft_score": int(score),
        "max_score": int(state.get("task_max_score", 2)),
    }
