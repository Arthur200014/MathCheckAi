from __future__ import annotations

from typing import Any

from src.state import ReviewState
from src.tools.core import save_report, save_review


def persist_review_node(state: ReviewState) -> dict[str, Any]:
    """Fast deterministic persistence node; not an LLM agent."""
    if state.get("status") != "REVIEWED":
        return {"history_saved": False}
    try:
        report_path = save_report(str(state.get("review_id", "review")), dict(state.get("report", {})))
        db_path = save_review(dict(state))
        return {
            "history_saved": True,
            "history_db_path": db_path,
            "report_json_path": report_path,
        }
    except Exception as exc:
        return {
            "history_saved": False,
            "warnings": list(state.get("warnings", [])) + [f"persistence:{exc}"],
        }
