from __future__ import annotations

from src.state import ReviewState


def _ignored(prefix: str) -> dict:
    return {
        "diagram_scope_ignored": True,
        f"{prefix}analysis_ok": True,
        f"{prefix}model": "ignored-by-scope",
        f"{prefix}present": False,
        f"{prefix}type": "none",
        f"{prefix}method_used": False,
        f"{prefix}confidence": 1.0,
        f"{prefix}visual_quality": "clear",
        f"{prefix}bbox": {"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0, "confidence": 1.0},
        f"{prefix}center_visible": False,
        f"{prefix}axes_visible": False,
        f"{prefix}points": [],
        f"{prefix}claims": [],
        f"{prefix}arc_marked": False,
        f"{prefix}arc_confidence": 0.0,
        f"{prefix}arc_description": "",
        f"{prefix}uncertain_fragments": [],
        f"{prefix}notes": ["trig_circle_ignored_by_project_scope"],
    }


def diagram_vision_node(state: ReviewState) -> dict:






    return _ignored("diagram_")


def diagram_reinspect_node(state: ReviewState) -> dict:
    out = _ignored("diagram_recheck_")
    out["diagram_reinspection_used"] = False
    return out
