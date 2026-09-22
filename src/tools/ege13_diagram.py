from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

import sympy as sp

from src.tools.ege13_reference import _dedupe, _equal, _sympify


@dataclass
class DiagramVerification:
    status: str
    part_b_valid: bool | None
    method_used: bool
    results: list[str]
    issues: list[str]
    checked_correspondences: int


_NON_MATH_LABELS = {"", "unknown", "none", "?", "x", "point"}


def _norm_id(raw: str) -> str:
    text = str(raw or "").strip().lower().replace("_", "")
    digits = re.findall(r"\d+", text)
    if digits:
        return digits[-1]
    text = re.sub(r"[()\[\]{}\s:]", "", text)
    return text


def _looks_like_point_identifier(text: str, point_id: str = "") -> bool:
    raw = str(text or "").strip().lower().replace("_", "")
    if raw in _NON_MATH_LABELS:
        return True
    if point_id and _norm_id(raw) == _norm_id(point_id):
        return True
    if re.fullmatch(r"(?:x|p|pt|point)\s*\d+", raw):
        return True
    return False


def _position_for_angle(expr: sp.Expr) -> str | None:
    try:
        s = float(sp.N(sp.sin(expr), 20))
        c = float(sp.N(sp.cos(expr), 20))
    except Exception:
        return None
    tol = 1e-8
    if abs(s) <= tol and c > tol:
        return "right"
    if abs(s) <= tol and c < -tol:
        return "left"
    if abs(c) <= tol and s > tol:
        return "top"
    if abs(c) <= tol and s < -tol:
        return "bottom"
    if s > tol and c > tol:
        return "upper_right"
    if s > tol and c < -tol:
        return "upper_left"
    if s < -tol and c < -tol:
        return "lower_left"
    if s < -tol and c > tol:
        return "lower_right"
    return None


def _extract_final_claim_value(raw: str) -> tuple[str | None, list[str]]:






    text = str(raw or "").strip()
    notes: list[str] = []
    if not text:
        return None, notes

    parts = [p.strip() for p in re.split(r"(?:=|＝)", text) if p.strip()]
    if len(parts) == 1:
        return parts[0], notes

    parsed: list[sp.Expr] = []
    for part in parts:
        try:
            parsed.append(_sympify(part))
        except Exception as exc:
            notes.append(f"claim_equality_side_parse_failed:{part}:{exc}")
            return parts[-1], notes

    for left, right in zip(parsed, parsed[1:]):
        if not _equal(left, right):
            notes.append(f"claim_written_equality_false:{sp.sstr(left)}!={sp.sstr(right)}")
    return parts[-1], notes


def _same_root_set(raw_values: list[str], expected_roots: list[str]) -> bool | None:
    try:
        got = _dedupe([_sympify(v) for v in raw_values if str(v).strip()])
        expected = _dedupe([_sympify(v) for v in expected_roots if str(v).strip()])
    except Exception:
        return None
    return len(got) == len(expected) and all(any(_equal(x, y) for y in expected) for x in got)


def _high_conf(value: Any, threshold: float = 0.88) -> bool:
    try:
        return float(value or 0.0) >= threshold
    except Exception:
        return False


def _issue_is_extraction_uncertainty(item: str) -> bool:
    return item.startswith((
        "diagram_claim_without_point:",
        "diagram_point_position_unknown:",
        "diagram_claim_value_unresolved:",
        "diagram_value_label_unresolved:",
        "diagram_value_label_position_unresolved:",
        "claim_equality_side_parse_failed:",
        "diagram_claimed_root_set_not_safely_comparable:",
    ))


def evidence_signatures(verification: DiagramVerification) -> set[str]:

    out: set[str] = set()
    for item in verification.issues:
        m = re.search(r"diagram_point_value_mismatch:id=[^:]+:value=([^:]+):", item)
        if m:
            out.add(f"point_value:{m.group(1).replace(' ', '')}")
            continue
        m = re.search(r"diagram_label_position_mismatch:([^:]+):", item)
        if m:
            out.add(f"direct_label:{m.group(1).replace(' ', '')}")
            continue
        if item.startswith("claim_written_equality_false:"):
            out.add("false_written_equality")
        if item == "diagram_required_arc_missing":
            out.add("missing_arc")
        if item == "diagram_required_boundaries_missing":
            out.add("missing_boundaries")
        if item == "diagram_required_roots_missing":
            out.add("missing_roots")
    if "diagram_claimed_root_set_matches_reference:false" in verification.results:
        out.add("wrong_claimed_root_set")
    return out


def verify_ege13_diagram(
    *,
    diagram_present: bool,
    diagram_type: str,
    method_used: bool,
    confidence: float,
    points: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    uncertain_fragments: list[str],
    expected_roots: list[str],
    arc_marked: bool | None = None,
    arc_confidence: float = 0.0,
) -> DiagramVerification:





    results: list[str] = []
    issues: list[str] = []

    if not method_used and not diagram_present:
        return DiagramVerification("NOT_APPLICABLE", None, False, results, issues, 0)

    if not diagram_present:
        return DiagramVerification(
            "DIAGRAM_EXPECTED_BUT_NOT_VISIBLE", None, bool(method_used), results,
            ["diagram_method_claimed_but_diagram_not_visible"], 0,
        )

    if diagram_type != "trig_circle":
        return DiagramVerification(
            "UNSUPPORTED_DIAGRAM_TYPE", None, True, results,
            [f"unsupported_diagram_type:{diagram_type}"], 0,
        )

    if confidence < 0.70:
        return DiagramVerification(
            "DIAGRAM_LOW_CONFIDENCE", None, True, results,
            [f"diagram_low_confidence:{confidence:.2f}", *[f"uncertain:{x}" for x in uncertain_fragments]], 0,
        )

    by_id: dict[str, dict[str, Any]] = {}
    checked = 0
    claimed_values: list[str] = []
    claimed_value_confidences: list[float] = []
    mismatch_ids: set[str] = set()
    positive_ids: set[str] = set()
    strong_error_codes: set[str] = set()

    for idx, point in enumerate(points):
        pid = _norm_id(point.get("point_id", ""))
        if pid:
            by_id[pid] = point

        value_label = str(point.get("value_label", "")).strip()
        position = str(point.get("position", "unknown"))
        point_conf = point.get("confidence", confidence)
        if _looks_like_point_identifier(value_label, str(point.get("point_id", ""))):
            if value_label:
                results.append(f"diagram_identifier_label_ignored:{value_label}")
            continue
        if not value_label or position == "unknown":
            continue
        try:
            angle = _sympify(value_label)
            expected_pos = _position_for_angle(angle)
        except Exception as exc:
            issues.append(f"diagram_value_label_unresolved:{value_label}:{exc}")
            continue
        if expected_pos is None:
            issues.append(f"diagram_value_label_position_unresolved:{value_label}")
            continue
        checked += 1
        key = pid or f"direct-{idx}"
        results.append(f"diagram_label_position:{value_label}:{position}:expected={expected_pos}")
        if expected_pos != position:
            issues.append(
                f"diagram_label_position_mismatch:{value_label}:drawn={position}:mathematical={expected_pos}"
            )
            if _high_conf(point_conf):
                mismatch_ids.add(key)
        else:
            positive_ids.add(key)

    for claim in claims:
        pid = _norm_id(claim.get("point_id", ""))
        raw_value = str(claim.get("value_text", "")).strip()
        claim_conf = claim.get("confidence", confidence)
        if not pid or not raw_value:
            continue

        final_value, claim_notes = _extract_final_claim_value(raw_value)
        issues.extend(claim_notes)
        if any(x.startswith("claim_written_equality_false:") for x in claim_notes) and _high_conf(claim_conf):
            strong_error_codes.add("false_written_equality")
        if not final_value:
            issues.append(f"diagram_claim_value_unresolved:{pid}:{raw_value}")
            continue
        claimed_values.append(final_value)
        try:
            claimed_value_confidences.append(float(claim_conf or 0.0))
        except Exception:
            claimed_value_confidences.append(0.0)

        point = by_id.get(pid)
        if point is None:
            issues.append(f"diagram_claim_without_point:{pid}:{final_value}")
            continue
        position = str(point.get("position", "unknown"))
        point_conf = point.get("confidence", confidence)
        if position == "unknown":
            issues.append(f"diagram_point_position_unknown:{pid}")
            continue
        try:
            angle = _sympify(final_value)
            expected_pos = _position_for_angle(angle)
        except Exception as exc:
            issues.append(f"diagram_claim_value_unresolved:{pid}:{final_value}:{exc}")
            continue
        if expected_pos is None:
            issues.append(f"diagram_claim_position_unresolved:{pid}:{final_value}")
            continue

        checked += 1
        results.append(f"diagram_claim_position:id={pid}:value={final_value}:drawn={position}:expected={expected_pos}")
        if expected_pos != position:
            issues.append(
                f"diagram_point_value_mismatch:id={pid}:value={final_value}:drawn={position}:mathematical={expected_pos}"
            )
            if _high_conf(point_conf) and _high_conf(claim_conf):
                mismatch_ids.add(pid)
        else:
            positive_ids.add(pid)

    root_set_state: bool | None = None
    if claimed_values and expected_roots:
        complete_high_conf_claim_set = (
            len(claimed_values) == len(expected_roots)
            and len(claimed_value_confidences) == len(claimed_values)
            and all(c >= 0.88 for c in claimed_value_confidences)
            and not uncertain_fragments
        )
        if complete_high_conf_claim_set:
            root_set_state = _same_root_set(claimed_values, expected_roots)
            if root_set_state is True:
                results.append("diagram_claimed_root_set_matches_reference:true")
            elif root_set_state is False:
                results.append("diagram_claimed_root_set_matches_reference:false")
                strong_error_codes.add("wrong_claimed_root_set")
            else:
                issues.append("diagram_claimed_root_set_not_safely_comparable:parse_failed")
        else:
            issues.append(
                f"diagram_claimed_root_set_not_safely_comparable:claims={len(claimed_values)}:expected={len(expected_roots)}"
            )

                                                                                  
                                                                                
                                                                               
    if method_used and confidence >= 0.88 and not uncertain_fragments:
        boundary_points = [p for p in points if p.get("role") == "interval_boundary" and _high_conf(p.get("confidence", confidence))]
        selected_points = [p for p in points if p.get("role") == "selected_root" and _high_conf(p.get("confidence", confidence))]
        if arc_marked is False and _high_conf(arc_confidence):
            issues.append("diagram_required_arc_missing")
            strong_error_codes.add("missing_arc")
                                                                             
                                                                              
                                                                               
                                                                             
                                                                                

                                                                                
                                                                  
    if root_set_state is False or len(mismatch_ids) >= 2 or strong_error_codes:
        if len(mismatch_ids) >= 2:
            results.append(f"diagram_redundant_mismatch_count:{len(mismatch_ids)}")
        if strong_error_codes:
            results.append("diagram_strong_error_codes:" + ",".join(sorted(strong_error_codes)))
        return DiagramVerification("DIAGRAM_INVALID", False, True, results, issues, checked)

    extraction_uncertainty = bool(uncertain_fragments) or any(_issue_is_extraction_uncertainty(x) for x in issues)
    if mismatch_ids or extraction_uncertainty or checked == 0:
        issues.extend(f"uncertain:{x}" for x in uncertain_fragments)
        if mismatch_ids:
            results.append(f"diagram_single_or_nonredundant_mismatch_count:{len(mismatch_ids)}")
        return DiagramVerification("DIAGRAM_UNVERIFIED", None, True, results, issues, checked)

    if len(positive_ids) < 2:
        issues.append(f"diagram_too_few_positive_correspondences:{len(positive_ids)}")
        return DiagramVerification("DIAGRAM_UNVERIFIED", None, True, results, issues, checked)

    return DiagramVerification("DIAGRAM_VERIFIED", True, True, results, issues, checked)
