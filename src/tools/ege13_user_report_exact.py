from __future__ import annotations

from typing import Any

from src.state import ReviewState
from src.tools.ege13_user_report import build_user_report_node as _build_user_report_node


def build_user_report_node(state: ReviewState) -> dict[str, Any]:
    """Keep the human-confirmed text exact and suppress disproved report comments."""
    out = _build_user_report_node(state)
    report = out.get("report") if isinstance(out, dict) else None
    if not isinstance(report, dict):
        return out

    confirmed = str(state.get("confirmed_transcript") or state.get("transcript") or "")
    fixed_report = dict(report)
    fixed_report["confirmed_solution_text"] = confirmed.strip()

    # The deterministic checker compares the complete periodic solution set.
    # If it proves part a equivalent, a per-family heuristic must not invent a
    # "wrong period" comment merely because the reference represents the same
    # set as separate even/odd families (for example pi*n vs 2*pi*n and
    # pi*(2*n-1)).
    part_a_equivalent = (
        state.get("reviewer_part_a_equivalent") is True
        or state.get("grader_part_a_equivalent") is True
    )
    if part_a_equivalent:
        comments = fixed_report.get("expert_comments", [])
        if isinstance(comments, list):
            comments = [
                item
                for item in comments
                if not (isinstance(item, dict) and str(item.get("section", "")).strip().lower() in {"а", "a"})
            ]
            fixed_report["expert_comments"] = comments
        fixed_report["part_a_comment"] = "Верно."

        score = state.get("final_score", fixed_report.get("score"))
        max_score = state.get("max_score", fixed_report.get("max_score", 2))
        if score is not None and max_score is not None and int(score) == int(max_score):
            fixed_report["expert_comment"] = "Решение верное."
        elif comments:
            first = comments[0] if isinstance(comments[0], dict) else {}
            fixed_report["expert_comment"] = str(first.get("title") or "В решении есть ошибка") + "."
        elif not bool(fixed_report.get("part_b_present", True)):
            fixed_report["expert_comment"] = "Пункт б не выполнен."

    return {**out, "report": fixed_report}
