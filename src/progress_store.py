from __future__ import annotations

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


def reset_progress(review_id: str) -> None:
    if not review_id:
        return
    with _LOCK:
        _PROGRESS[review_id] = {
            "review_id": review_id,
            "started_at": time.time(),
            "current_stage": "",
            "stages": {},
        }


def start_stage(review_id: str, stage: str) -> None:
    if not review_id:
        return
    now = time.time()
    with _LOCK:
        item = _PROGRESS.setdefault(
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
    with _LOCK:
        item = _PROGRESS.get(review_id)
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
    with _LOCK:
        item = _PROGRESS.get(review_id)
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
