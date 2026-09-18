from __future__ import annotations

import base64
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

PENDING_DIR = Path(
    os.getenv(
        "MATHCHECK_PENDING_DIR",
        str(Path(tempfile.gettempdir()) / "mathcheck-ai" / "pending_reviews"),
    )
)
MAX_AGE_SECONDS = int(os.getenv("MATHCHECK_PENDING_TTL_SECONDS", "1800"))


def _safe_review_id(review_id: str) -> str:
    value = str(review_id or "").strip()
    if not value.startswith("r-") or not value.replace("-", "").isalnum():
        raise ValueError("invalid_review_id")
    return value


def cleanup_old_pending() -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - MAX_AGE_SECONDS
    for pattern in ("*.jpg", "*.json"):
        for path in PENDING_DIR.glob(pattern):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                pass


def save_pending_image(review_id: str, image_bytes: bytes) -> Path:
    cleanup_old_pending()
    rid = _safe_review_id(review_id)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    path = PENDING_DIR / f"{rid}.jpg"
    path.write_bytes(image_bytes)
    return path


def load_pending_image_b64(review_id: str) -> str | None:
    cleanup_old_pending()
    rid = _safe_review_id(review_id)
    path = PENDING_DIR / f"{rid}.jpg"
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode("ascii")


def save_pending_state(review_id: str, state: dict[str, Any]) -> Path:
    """Persist only safe structured interim state, never base64 image bytes."""
    cleanup_old_pending()
    rid = _safe_review_id(review_id)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    allowed_prefixes = ("solver_",)
    allowed_keys = {
        "reference_answer_part_a",
        "key_checkpoints",
        "task_profile",
        "task_profile_ok",
        "task_title",
        "task_max_score",
    }
    safe = {
        key: value
        for key, value in state.items()
        if key in allowed_keys or key.startswith(allowed_prefixes)
    }
    path = PENDING_DIR / f"{rid}.json"
    path.write_text(json.dumps(safe, ensure_ascii=False), encoding="utf-8")
    return path


def load_pending_state(review_id: str) -> dict[str, Any]:
    cleanup_old_pending()
    rid = _safe_review_id(review_id)
    path = PENDING_DIR / f"{rid}.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def delete_pending(review_id: str) -> None:
    rid = _safe_review_id(review_id)
    for suffix in (".jpg", ".json"):
        path = PENDING_DIR / f"{rid}{suffix}"
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def delete_pending_image(review_id: str) -> None:
    # Backward-compatible alias used by older tests/imports.
    rid = _safe_review_id(review_id)
    path = PENDING_DIR / f"{rid}.jpg"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
