from __future__ import annotations

from typing import Any

from src.state import ReviewState
from src.tools.ege13_user_report import build_user_report_node as _build_user_report_node


def build_user_report_node(state: ReviewState) -> dict[str, Any]:
    """Keep the student's human-confirmed text byte-for-byte in the final report.

    The base report builder may normalize math spacing for generated comments and
    reference answers.  That is useful there, but the confirmed student solution
    is evidence and must be shown exactly as the human left it in the editor.
    """
    out = _build_user_report_node(state)
    report = out.get("report") if isinstance(out, dict) else None
    if not isinstance(report, dict):
        return out

    confirmed = str(state.get("confirmed_transcript") or state.get("transcript") or "")
    fixed_report = dict(report)
    fixed_report["confirmed_solution_text"] = confirmed.strip()
    return {**out, "report": fixed_report}
