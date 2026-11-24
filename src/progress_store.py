from __future__ import annotations

import json
from contextlib import contextmanager
from src.postgres_store import postgres_connection, postgres_enabled
import threading
import time

_LOCK = threading.Lock()
_PROGRESS: dict[str, dict] = {}

_STAGE_LABELS = {
    "vision": "Распознавание фото",
    "preflight": "Проверка введённых данных",
    "solver": "Solver — эталонное решение",
    "verify_reference": "Проверка эталона SymPy",
    "grader": "Grader — проверка решения",
    "reviewer": "Reviewer — контроль результата",
    "build_report": "Сборка отчёта",
    "persist_review": "Сохранение результата",
}


@contextmanager
def _progress_item(review_id: str, *, write: bool = True):
    if not postgres_enabled():
        with _LOCK:
            yield _PROGRESS
        return
    with postgres_connection() as conn:
        if write:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (review_id,))
        row = conn.execute("SELECT payload_json FROM review_progress WHERE review_id=?", (review_id,)).fetchone()
        items = {review_id: json.loads(row["payload_json"])} if row else {}
        yield items
        if write and review_id in items:
            conn.execute(
                "INSERT INTO review_progress(review_id, payload_json) VALUES (?, ?) "
                "ON CONFLICT(review_id) DO UPDATE SET payload_json=excluded.payload_json",
                (review_id, json.dumps(items[review_id], ensure_ascii=False)),
            )


def reset_progress(review_id: str) -> None:
    if not review_id:
        return
    with _progress_item(review_id) as items:
        items[review_id] = {
            "review_id": review_id,
            "started_at": time.time(),
            "current_stage": "",
            "stages": {},
        }


def start_stage(review_id: str, stage: str) -> None:
    if not review_id:
        return
    now = time.time()
    with _progress_item(review_id) as items:
        item = items.setdefault(
            review_id,
            {"review_id": review_id, "started_at": now, "current_stage": "", "stages": {}},
        )
        item["current_stage"] = stage
        item["stages"][stage] = {
            "stage": stage,
            "label": _STAGE_LABELS.get(stage, stage),
            "status": "running",
            "started_at": now,
            "elapsed_seconds": 0.0,
        }


def finish_stage(review_id: str, stage: str, *, status: str = "done") -> None:
    if not review_id:
        return
    now = time.time()
    with _progress_item(review_id) as items:
        item = items.get(review_id)
        if not item:
            return
        row = item.get("stages", {}).get(stage)
        if not row:
            return
        started = float(row.get("started_at") or now)
        row["elapsed_seconds"] = round(max(0.0, now - started), 2)
        row["status"] = status
        row["finished_at"] = now
        if item.get("current_stage") == stage:
            item["current_stage"] = ""


def progress_snapshot(review_id: str) -> dict:
    now = time.time()
    with _progress_item(review_id, write=False) as items:
        item = items.get(review_id)
        if not item:
            return {"review_id": review_id, "current_stage": "", "total_elapsed_seconds": 0.0, "stages": []}
        stages = []
        for row in item.get("stages", {}).values():
            copy = dict(row)
            if copy.get("status") == "running":
                started = float(copy.get("started_at") or now)
                copy["elapsed_seconds"] = round(max(0.0, now - started), 2)
            stages.append(copy)
                                                                                
                                                                          
        total = round(sum(float(row.get("elapsed_seconds") or 0.0) for row in stages), 2)
        return {
            "review_id": review_id,
            "current_stage": item.get("current_stage", ""),
            "total_elapsed_seconds": total,
            "stages": stages,
        }
# fix
