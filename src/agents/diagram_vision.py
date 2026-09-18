from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from src.llm.config import get_diagram_model
from src.llm.ollama_client import OllamaError, ollama_chat_json
from src.state import ReviewState

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _diagram_schema() -> dict[str, Any]:
    point = {
        "type": "object",
        "properties": {
            "point_id": {"type": "string"},
            "position": {
                "type": "string",
                "enum": [
                    "right", "upper_right", "top", "upper_left", "left",
                    "lower_left", "bottom", "lower_right", "center", "unknown",
                ],
            },
            "value_label": {"type": "string"},
            "role": {
                "type": "string",
                "enum": ["selected_root", "interval_boundary", "helper", "unknown"],
            },
            "marker": {
                "type": "string",
                "enum": ["filled", "open", "cross", "tick", "unknown"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["point_id", "position", "value_label", "role", "marker", "confidence"],
        "additionalProperties": False,
    }
    claim = {
        "type": "object",
        "properties": {
            "point_id": {"type": "string"},
            "value_text": {"type": "string"},
            "source_text": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["point_id", "value_text", "source_text", "confidence"],
        "additionalProperties": False,
    }
    bbox = {
        "type": "object",
        "properties": {
            "x_min": {"type": "integer", "minimum": 0, "maximum": 1000},
            "y_min": {"type": "integer", "minimum": 0, "maximum": 1000},
            "x_max": {"type": "integer", "minimum": 0, "maximum": 1000},
            "y_max": {"type": "integer", "minimum": 0, "maximum": 1000},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["x_min", "y_min", "x_max", "y_max", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "diagram_present": {"type": "boolean"},
            "diagram_type": {
                "type": "string",
                "enum": ["trig_circle", "number_line", "graph", "other", "none"],
            },
            "method_used_for_part_b": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "visual_quality": {
                "type": "string",
                "enum": ["clear", "readable_with_noise", "partial", "poor"],
            },
            "diagram_bbox": bbox,
            "circle_center_visible": {"type": "boolean"},
            "axes_visible": {"type": "boolean"},
            "points": {"type": "array", "items": point},
            "claims": {"type": "array", "items": claim},
            "arc_marked": {"type": "boolean"},
            "arc_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "arc_description": {"type": "string"},
            "uncertain_fragments": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "diagram_present", "diagram_type", "method_used_for_part_b", "confidence",
            "visual_quality", "diagram_bbox", "circle_center_visible", "axes_visible",
            "points", "claims", "arc_marked", "arc_confidence", "arc_description",
            "uncertain_fragments", "notes",
        ],
        "additionalProperties": False,
    }


def _empty(prefix: str, reason: str) -> dict:
    return {
        f"{prefix}analysis_ok": False,
        f"{prefix}model": "no-image" if reason == "original_image_unavailable" else "ollama-error",
        f"{prefix}present": False,
        f"{prefix}type": "none",
        f"{prefix}method_used": False,
        f"{prefix}confidence": 0.0,
        f"{prefix}visual_quality": "poor",
        f"{prefix}bbox": {"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0, "confidence": 0.0},
        f"{prefix}center_visible": False,
        f"{prefix}axes_visible": False,
        f"{prefix}points": [],
        f"{prefix}claims": [],
        f"{prefix}arc_marked": False,
        f"{prefix}arc_confidence": 0.0,
        f"{prefix}arc_description": "",
        f"{prefix}uncertain_fragments": [reason],
        f"{prefix}notes": [],
    }


def _result_to_state(result: dict[str, Any], prefix: str = "diagram_") -> dict:
    return {
        f"{prefix}analysis_ok": True,
        f"{prefix}model": str(result.get("_model", get_diagram_model())),
        f"{prefix}present": bool(result.get("diagram_present", False)),
        f"{prefix}type": str(result.get("diagram_type", "none")),
        f"{prefix}method_used": bool(result.get("method_used_for_part_b", False)),
        f"{prefix}confidence": float(result.get("confidence", 0.0) or 0.0),
        f"{prefix}visual_quality": str(result.get("visual_quality", "poor")),
        f"{prefix}bbox": dict(result.get("diagram_bbox", {}) or {}),
        f"{prefix}center_visible": bool(result.get("circle_center_visible", False)),
        f"{prefix}axes_visible": bool(result.get("axes_visible", False)),
        f"{prefix}points": list(result.get("points", [])),
        f"{prefix}claims": list(result.get("claims", [])),
        f"{prefix}arc_marked": bool(result.get("arc_marked", False)),
        f"{prefix}arc_confidence": float(result.get("arc_confidence", 0.0) or 0.0),
        f"{prefix}arc_description": str(result.get("arc_description", "")),
        f"{prefix}uncertain_fragments": list(result.get("uncertain_fragments", [])),
        f"{prefix}notes": list(result.get("notes", [])),
    }


def _call_diagram_vision(image_b64: str, *, task_statement: str, reinspection: bool = False) -> dict[str, Any]:
    system_prompt = _load("prompts/diagram_vision.md")
    skill = _load("skills/task_13/read_trig_circle.md")
    phase = (
        "SECOND INDEPENDENT INSPECTION. This image may be a zoomed crop. Read it from pixels again; "
        "do not preserve a previous interpretation just for consistency."
        if reinspection
        else "FIRST INSPECTION."
    )
    user_prompt = f"""{phase}

TASK STATEMENT (context only; DO NOT solve it and DO NOT infer the expected roots):
{task_statement}

READING MANUAL:
{skill}

Inspect ONLY the student's visual selection method for part б). Return JSON only.
Copy what is visible. For a point near an axis, prefer `unknown` over an uncertain neighboring quadrant.
For calculations tied to a point id, claims[].value_text must contain the final right-most mathematical value only.
If no diagram is visible, set diagram_present=false and diagram_type='none'.
""".strip()
    return ollama_chat_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_b64=image_b64,
        model=get_diagram_model(),
        response_schema=_diagram_schema(),
        num_ctx=8192,
        num_predict=1900,
    )


def _crop_for_reinspection(image_b64: str, bbox: dict[str, Any]) -> str:
    """Crop and upscale the diagram region. Falls back to the full image."""
    try:
        conf = float(bbox.get("confidence", 0.0) or 0.0)
        x0, y0, x1, y1 = [int(bbox.get(k, 0) or 0) for k in ("x_min", "y_min", "x_max", "y_max")]
        if conf < 0.45 or x1 <= x0 or y1 <= y0:
            return image_b64
        raw = base64.b64decode(image_b64)
        with Image.open(BytesIO(raw)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            w, h = im.size
            left = int(w * x0 / 1000)
            top = int(h * y0 / 1000)
            right = int(w * x1 / 1000)
            bottom = int(h * y1 / 1000)
            # generous padding keeps nearby x1=... claims in frame
            pad_x = max(24, int((right - left) * 0.25))
            pad_y = max(24, int((bottom - top) * 0.25))
            left, top = max(0, left - pad_x), max(0, top - pad_y)
            right, bottom = min(w, right + pad_x), min(h, bottom + pad_y)
            crop = im.crop((left, top, right, bottom))
            if crop.width < 1500 and crop.height < 1500:
                scale = min(3.0, 1600 / max(crop.width, crop.height, 1))
                if scale > 1.05:
                    crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.Resampling.LANCZOS)
            out = BytesIO()
            crop.save(out, format="JPEG", quality=92, optimize=True)
            return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return image_b64


def diagram_vision_node(state: ReviewState) -> dict:
    image_b64 = state.get("image_b64")
    if not image_b64:
        return _empty("diagram_", "original_image_unavailable")
    try:
        result = _call_diagram_vision(
            image_b64,
            task_statement=str(state.get("task_statement", "")),
            reinspection=False,
        )
    except OllamaError as exc:
        out = _empty("diagram_", str(exc))
        out["warnings"] = list(state.get("warnings", [])) + [f"diagram_vision:{exc}"]
        return out
    return _result_to_state(result, "diagram_")


def diagram_reinspect_node(state: ReviewState) -> dict:
    """Automatic second pass used before asking a human to inspect the circle."""
    image_b64 = state.get("image_b64")
    if not image_b64:
        return {
            **_empty("diagram_recheck_", "original_image_unavailable"),
            "diagram_reinspection_used": True,
        }
    zoomed = _crop_for_reinspection(image_b64, dict(state.get("diagram_bbox", {}) or {}))
    try:
        result = _call_diagram_vision(
            zoomed,
            task_statement=str(state.get("task_statement", "")),
            reinspection=True,
        )
    except OllamaError as exc:
        out = _empty("diagram_recheck_", str(exc))
        out.update({
            "diagram_reinspection_used": True,
            "warnings": list(state.get("warnings", [])) + [f"diagram_reinspect:{exc}"],
        })
        return out
    out = _result_to_state(result, "diagram_recheck_")
    out["diagram_reinspection_used"] = True
    return out
