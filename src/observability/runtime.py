from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OBS_DIR = Path(os.getenv("MATHCHECK_OBS_DIR", str(Path(tempfile.gettempdir()) / "mathcheck-ai" / "observability")))
LOG_PATH = OBS_DIR / "llm_calls.jsonl"
ALERT_PATH = OBS_DIR / "alerts.jsonl"
TRACE_PATH = OBS_DIR / "traces.jsonl"
SLOW_SECONDS = float(os.getenv("MATHCHECK_SLOW_AGENT_SECONDS", "120"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    try:
        OBS_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        # Observability must never break the grading flow.
        pass


def log_llm_call(event: dict[str, Any]) -> None:
    row = {"ts": _now_iso(), **event}
    _append_jsonl(LOG_PATH, row)

    elapsed = float(event.get("elapsed_seconds", 0) or 0)
    if elapsed >= SLOW_SECONDS:
        alert = {**row, "alert": "slow_llm_call", "threshold_seconds": SLOW_SECONDS}
        _append_jsonl(ALERT_PATH, alert)


def start_trace_span(*, review_id: str, stage: str) -> dict[str, Any]:
    trace_id = str(review_id or "").strip() or f"trace-{uuid.uuid4().hex}"
    span = {
        "trace_id": trace_id,
        "span_id": uuid.uuid4().hex,
        "stage": str(stage),
        "started_at": _now_iso(),
        "_started_monotonic": time.perf_counter(),
    }
    _append_jsonl(
        TRACE_PATH,
        {
            "event": "span_start",
            "trace_id": span["trace_id"],
            "span_id": span["span_id"],
            "stage": span["stage"],
            "ts": span["started_at"],
        },
    )
    return span


def finish_trace_span(span: dict[str, Any], *, status: str, error: str | None = None) -> None:
    started = float(span.get("_started_monotonic", time.perf_counter()))
    duration = max(0.0, time.perf_counter() - started)
    row: dict[str, Any] = {
        "event": "span_end",
        "trace_id": span.get("trace_id"),
        "span_id": span.get("span_id"),
        "stage": span.get("stage"),
        "ts": _now_iso(),
        "duration_seconds": round(duration, 6),
        "status": str(status),
    }
    if error:
        row["error"] = str(error)[:1000]
    _append_jsonl(TRACE_PATH, row)


def observability_status() -> dict[str, Any]:
    return {
        "json_logs": str(LOG_PATH),
        "traces": str(TRACE_PATH),
        "alerts": str(ALERT_PATH),
        "slow_agent_threshold_seconds": SLOW_SECONDS,
    }
