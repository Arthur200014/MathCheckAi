from __future__ import annotations

from typing import Any


def _unverified_diagram_is_nonblocking(
    *,
    assessment: dict[str, Any],
    part_a_equivalent: bool | None,
    part_b_matches: bool | None,
    diagram_part_b_valid: bool | None,
    diagram_method_used: bool,
) -> bool:








    if not diagram_method_used or diagram_part_b_valid is not None:
        return False
    return (
        part_a_equivalent is True
        and part_b_matches is True
        and str(assessment.get("part_a_status", "uncertain")) == "correct"
        and str(assessment.get("part_b_status", "uncertain")) == "correct"
        and str(assessment.get("error_class", "ambiguous")) == "none"
    )


def apply_ege13_rubric(
    *,
    assessment: dict[str, Any],
    part_a_equivalent: bool | None,
    part_b_matches: bool | None,
    diagram_part_b_valid: bool | None = None,
    diagram_method_used: bool = False,
) -> tuple[int | None, str, list[str]]:







    conflicts: list[str] = []
    a_status = str(assessment.get("part_a_status", "uncertain"))
    b_status = str(assessment.get("part_b_status", "uncertain"))
    error_class = str(assessment.get("error_class", "ambiguous"))
    confidence = float(assessment.get("confidence", 0) or 0)

    can_assess = bool(assessment.get("can_grade", assessment.get("can_review", False)))
    if not can_assess:
        return None, "llm_cannot_assess", conflicts

    diagram_override = diagram_method_used and diagram_part_b_valid is False
    diagram_unverified_nonblocking = _unverified_diagram_is_nonblocking(
        assessment=assessment,
        part_a_equivalent=part_a_equivalent,
        part_b_matches=part_b_matches,
        diagram_part_b_valid=diagram_part_b_valid,
        diagram_method_used=diagram_method_used,
    )

                                                                            
                                                                               
                   
    if assessment.get("manual_review_required", False) and not (
        (diagram_override and a_status == "correct" and part_a_equivalent is True)
        or diagram_unverified_nonblocking
    ):
        return None, "llm_requested_manual_review", conflicts

    if a_status == "uncertain" or error_class == "ambiguous":
        return None, "ambiguous_assessment", conflicts
    if b_status == "uncertain" and not diagram_override:
        return None, "ambiguous_assessment", conflicts
    if confidence < 0.75:
        return None, "low_confidence_assessment", conflicts

    if part_a_equivalent is True and a_status in {"substantive_error", "missing"}:
        conflicts.append("llm_part_a_conflicts_with_deterministic_equivalence")
    if part_a_equivalent is False and a_status == "correct":
        conflicts.append("llm_part_a_correct_but_machine_set_not_equivalent")

                                                                               
                                                                           
                                                                       
                        
    if not diagram_override:
        if part_b_matches is True and b_status in {"incorrect", "missing"}:
            conflicts.append("llm_part_b_conflicts_with_deterministic_roots")
        if part_b_matches is False and b_status == "correct":
            conflicts.append("llm_part_b_correct_but_roots_do_not_match")
    if conflicts:
        return None, "deterministic_llm_conflict", conflicts

                                                                           
    if diagram_override:
        if part_a_equivalent is not True:
            return None, "diagram_error_but_part_a_not_confirmed", conflicts
        return 1, "part_a_correct_part_b_diagram_error", conflicts

    if a_status == "correct" and b_status == "correct":
        if part_a_equivalent is not True or part_b_matches is not True:
            return None, "correct_claim_not_fully_deterministically_confirmed", conflicts
        if diagram_unverified_nonblocking:
            return 2, "both_parts_correct_unreadable_diagram_no_proven_error", conflicts
        return 2, "both_parts_correct_and_justified", conflicts

    if a_status == "correct":
        if part_a_equivalent is not True:
            return None, "part_a_correct_not_deterministically_confirmed", conflicts
        return 1, "part_a_correct_part_b_not_fully_correct", conflicts

    if (
        a_status == "computation_error_only"
        and error_class == "computation_error"
        and bool(assessment.get("overall_sequence_correct_both_parts", False))
    ):
        return 1, "computational_error_only_with_correct_sequence", conflicts

    if a_status in {"missing", "substantive_error"}:
        return 0, "part_a_missing_or_substantive_error", conflicts

    return None, "rubric_case_not_resolved", conflicts


def resolve_confirmed_ege13_score(
    *,
    assessment: dict[str, Any],
    part_a_equivalent: bool | None,
    part_b_matches: bool | None,
    part_b_present: bool,
) -> tuple[int, str, list[str]]:






    warnings: list[str] = []
    a_status = str(assessment.get("part_a_status", "uncertain"))
    b_status = str(assessment.get("part_b_status", "uncertain"))
    error_class = str(assessment.get("error_class", "ambiguous"))

                                                                              
                                                                             
                                                                                 
    if a_status == "uncertain" or b_status == "uncertain" or error_class == "ambiguous":
        warnings.append("semantic_assessment_uncertain")

                                                                            
                                                                              
                                                                                  
    if part_a_equivalent is False:
        if (
            a_status == "computation_error_only"
            and error_class == "computation_error"
            and bool(assessment.get("overall_sequence_correct_both_parts", False))
        ):
            return 1, "computational_error_only_with_correct_sequence", warnings
        return 0, "part_a_missing_or_substantive_error", warnings

    if part_a_equivalent is True:
        if a_status in {"missing", "substantive_error"}:
            return 0, "part_a_missing_or_substantive_error", warnings
        if a_status == "computation_error_only":
            return 1, "computational_error_only_with_correct_sequence", warnings
        if part_b_present and part_b_matches is True and b_status == "correct":
            return 2, "both_parts_correct_and_justified", warnings
        return 1, "part_a_correct_part_b_not_fully_correct", warnings

                                                                               
                                                                                
    warnings.append("part_a_equivalence_unresolved")
    if a_status == "correct":
        if part_b_present and part_b_matches is True and b_status == "correct":
            return 2, "semantic_fallback_both_parts_correct", warnings
        return 1, "semantic_fallback_part_a_correct", warnings
    if a_status == "computation_error_only":
        return 1, "semantic_fallback_computation_error", warnings
    return 0, "semantic_fallback_part_a_not_correct", warnings
# fix
