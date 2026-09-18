from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OBS_DIR = Path(os.getenv("MATHCHECK_OBS_DIR", str(Path(tempfile.gettempdir()) / "mathcheck-ai" / "observability")))
LOG_PATH = OBS_DIR / "llm_calls.jsonl"
ALERT_PATH = OBS_DIR / "alerts.jsonl"
SLOW_SECONDS = float(os.getenv("MATHCHECK_SLOW_AGENT_SECONDS", "120"))


def log_llm_call(event: dict[str, Any]) -> None:
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    elapsed = float(event.get("elapsed_seconds", 0) or 0)
    if elapsed >= SLOW_SECONDS:
        alert = {**row, "alert": "slow_llm_call", "threshold_seconds": SLOW_SECONDS}
        with ALERT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(alert, ensure_ascii=False) + "\n")


def observability_status() -> dict[str, Any]:
    return {
        "json_logs": str(LOG_PATH),
        "alerts": str(ALERT_PATH),
        "slow_agent_threshold_seconds": SLOW_SECONDS,
    }
