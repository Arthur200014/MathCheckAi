from __future__ import annotations

from src.state import ReviewState
from src.tools.ege13_diagram import evidence_signatures, verify_ege13_diagram


def _method_used(state: ReviewState, *, recheck: bool = False) -> bool:
    transcript = str(state.get("confirmed_transcript") or state.get("transcript") or "").lower()
    key = "diagram_recheck_method_used" if recheck else "diagram_method_used"
    return bool(state.get(key, False)) or ("окруж" in transcript)


def _verify_from_state(state: ReviewState, *, recheck: bool = False):
    p = "diagram_recheck_" if recheck else "diagram_"
    return verify_ege13_diagram(
        diagram_present=bool(state.get(f"{p}present", False)),
        diagram_type=str(state.get(f"{p}type", "none")),
        method_used=_method_used(state, recheck=recheck),
        confidence=float(state.get(f"{p}confidence", 0.0) or 0.0),
        points=list(state.get(f"{p}points", [])),
        claims=list(state.get(f"{p}claims", [])),
        uncertain_fragments=list(state.get(f"{p}uncertain_fragments", [])),
        expected_roots=list(state.get("reference_expected_roots", [])),
        arc_marked=state.get(f"{p}arc_marked"),
        arc_confidence=float(state.get(f"{p}arc_confidence", 0.0) or 0.0),
    )


def diagram_verifier_node(state: ReviewState) -> dict:

    if state.get("task_type") != "ege_13" or state.get("diagram_scope_ignored", False):
        return {
            "diagram_method_used": False,
            "diagram_verification_status": "NOT_APPLICABLE",
            "diagram_part_b_valid": None,
            "diagram_verification_results": ["diagram_ignored_by_project_scope"] if state.get("diagram_scope_ignored", False) else [],
            "diagram_verification_issues": [],
            "diagram_checked_correspondences": 0,
            "diagram_reinspection_needed": False,
        }

    v = _verify_from_state(state, recheck=False)
    needs_reinspect = v.status not in {"DIAGRAM_VERIFIED", "NOT_APPLICABLE"}
    return {
        "diagram_method_used": v.method_used,
        "diagram_verification_status": v.status,
        "diagram_part_b_valid": v.part_b_valid,
        "diagram_verification_results": v.results,
        "diagram_verification_issues": v.issues,
        "diagram_checked_correspondences": v.checked_correspondences,
        "diagram_initial_verification_status": v.status,
        "diagram_initial_evidence_signatures": sorted(evidence_signatures(v)),
        "diagram_reinspection_needed": needs_reinspect,
    }


def diagram_final_verifier_node(state: ReviewState) -> dict:





    if state.get("diagram_scope_ignored", False):
        return {
            "diagram_verification_status": "NOT_APPLICABLE",
            "diagram_part_b_valid": None,
            "diagram_verification_results": ["diagram_ignored_by_project_scope"],
            "diagram_verification_issues": [],
            "diagram_checked_correspondences": 0,
            "diagram_cross_pass_confirmed": False,
            "diagram_cross_pass_signatures": [],
            "diagram_manual_review_scope": "",
            "diagram_manual_review_reasons": [],
            "diagram_reinspection_resolved": True,
        }

    first_status = str(state.get("diagram_initial_verification_status", state.get("diagram_verification_status", "DIAGRAM_UNVERIFIED")))
    first_signatures = set(state.get("diagram_initial_evidence_signatures", []))
    second = _verify_from_state(state, recheck=True)
    second_signatures = evidence_signatures(second)

    results = [f"first_pass_status:{first_status}", *list(state.get("diagram_verification_results", []))]
    issues = list(state.get("diagram_verification_issues", []))
    results.append(f"recheck_status:{second.status}")
    results.extend(f"recheck:{x}" for x in second.results)
    issues.extend(f"recheck:{x}" for x in second.issues)

    common_invalid = first_signatures & second_signatures
    if first_status == "DIAGRAM_INVALID" and second.status == "DIAGRAM_INVALID" and common_invalid:
        results.append("cross_pass_invalid_confirmed:" + ",".join(sorted(common_invalid)))
        return {
            "diagram_verification_status": "DIAGRAM_INVALID",
            "diagram_part_b_valid": False,
            "diagram_verification_results": results,
            "diagram_verification_issues": issues,
            "diagram_checked_correspondences": max(int(state.get("diagram_checked_correspondences", 0) or 0), second.checked_correspondences),
            "diagram_cross_pass_confirmed": True,
            "diagram_cross_pass_signatures": sorted(common_invalid),
            "diagram_manual_review_scope": "",
            "diagram_manual_review_reasons": [],
            "diagram_reinspection_resolved": True,
        }

    if first_status not in {"DIAGRAM_INVALID"} and second.status == "DIAGRAM_VERIFIED":
        results.append("reinspection_resolved_to_verified")
        return {
            "diagram_verification_status": "DIAGRAM_VERIFIED",
            "diagram_part_b_valid": True,
            "diagram_verification_results": results,
            "diagram_verification_issues": issues,
            "diagram_checked_correspondences": second.checked_correspondences,
            "diagram_cross_pass_confirmed": False,
            "diagram_cross_pass_signatures": [],
            "diagram_manual_review_scope": "",
            "diagram_manual_review_reasons": [],
            "diagram_reinspection_resolved": True,
        }

    if first_status == "NOT_APPLICABLE" and second.status == "NOT_APPLICABLE":
        return {
            "diagram_verification_status": "NOT_APPLICABLE",
            "diagram_part_b_valid": None,
            "diagram_verification_results": results,
            "diagram_verification_issues": issues,
            "diagram_checked_correspondences": 0,
            "diagram_cross_pass_confirmed": False,
            "diagram_cross_pass_signatures": [],
            "diagram_manual_review_scope": "",
            "diagram_manual_review_reasons": [],
            "diagram_reinspection_resolved": True,
        }

    reasons = []
    if first_status == "DIAGRAM_INVALID" and second.status == "DIAGRAM_VERIFIED":
        reasons.append("visual_passes_conflict_invalid_vs_verified")
    elif first_status == "DIAGRAM_VERIFIED" and second.status == "DIAGRAM_INVALID":
        reasons.append("visual_passes_conflict_verified_vs_invalid")
    elif first_status == "DIAGRAM_INVALID" and second.status == "DIAGRAM_INVALID" and not common_invalid:
        reasons.append("invalid_passes_do_not_confirm_same_error")
    else:
        reasons.append(f"diagram_not_resolved_after_reinspection:{second.status}")
    reasons.extend(str(x) for x in second.issues[:8])

    results.append("diagram_final_unverified_no_automatic_penalty")
    return {
        "diagram_verification_status": "DIAGRAM_UNVERIFIED_AFTER_REINSPECTION",
        "diagram_part_b_valid": None,
        "diagram_verification_results": results,
        "diagram_verification_issues": issues,
        "diagram_checked_correspondences": max(int(state.get("diagram_checked_correspondences", 0) or 0), second.checked_correspondences),
        "diagram_cross_pass_confirmed": False,
        "diagram_cross_pass_signatures": sorted(common_invalid),
        "diagram_manual_review_scope": "",
        "diagram_manual_review_reasons": [],
        "diagram_unverified_reasons": reasons,
        "diagram_reinspection_resolved": False,
    }
