from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("MATHCHECK_DATA_DIR", str(PROJECT_ROOT / "data")))
DB_PATH = Path(os.getenv("MATHCHECK_DB_PATH", str(DATA_DIR / "mathcheck.db")))
REPORTS_DIR = Path(os.getenv("MATHCHECK_REPORTS_DIR", str(PROJECT_ROOT / "reports")))


def load_criteria(task_type: str) -> str:
    mapping = {
        "ege_13": PROJECT_ROOT / "criteria" / "task_13.md",
        "ege_15": PROJECT_ROOT / "criteria" / "task_15.md",
    }
    try:
        path = mapping[task_type]
    except KeyError as exc:
        raise ValueError(f"unknown_task_type:{task_type}") from exc
    return path.read_text(encoding="utf-8")


def load_runtime_rubric(task_type: str) -> dict[str, Any]:
    mapping = {
        "ege_13": PROJECT_ROOT / "criteria" / "task_13_rubric.json",
    }
    try:
        path = mapping[task_type]
    except KeyError as exc:
        raise ValueError(f"runtime_rubric_not_available:{task_type}") from exc
    return json.loads(path.read_text(encoding="utf-8"))


def compact_criteria_summary(task_type: str) -> str:
    if task_type != "ege_13":
        return load_criteria(task_type)
    return (
        "ЕГЭ №13, максимум 2. "
        "2 балла: обоснованно верны пункты а и б. "
        "1 балл: пункт а обоснованно верен; либо только локальная вычислительная ошибка при сохранении "
        "верной последовательности обоих пунктов. "
        "0 баллов: не выполнены условия для 1/2. "
        "Содержательная ошибка в простейшем уравнении/ОДЗ/факторизации не считается вычислительной. "
        "В пункте б лишний, потерянный или неверно отобранный корень = root_selection_error. "
        "Допустим любой математически корректный способ отбора."
    )


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            review_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            final_score INTEGER,
            max_score INTEGER,
            status TEXT NOT NULL,
            error_class TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_student ON reviews(student_id, created_at)")
    return conn


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items() if k != "image_b64"}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def save_review(review: dict[str, Any]) -> str:
    review_id = str(review.get("review_id", "")).strip()
    if not review_id:
        raise ValueError("missing_review_id")
    payload = _json_safe(review)
    report = payload.get("report") if isinstance(payload, dict) else None
    summary = ""
    if isinstance(report, dict):
        summary = str(report.get("expert_comment", ""))
    error_class = str(review.get("reviewer_error_class") or review.get("grader_error_class") or "")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO reviews(review_id, student_id, task_type, final_score, max_score, status,
                                error_class, summary, created_at, payload_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(review_id) DO UPDATE SET
                final_score=excluded.final_score,
                max_score=excluded.max_score,
                status=excluded.status,
                error_class=excluded.error_class,
                summary=excluded.summary,
                payload_json=excluded.payload_json
            """,
            (
                review_id,
                str(review.get("student_id", "")),
                str(review.get("task_type", "")),
                review.get("final_score"),
                review.get("max_score"),
                str(review.get("status", "")),
                error_class,
                summary,
                now,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
    return str(DB_PATH)


def load_review(review_id: str) -> dict[str, Any] | None:
    """Load one saved review by id, including the persisted safe payload."""
    rid = str(review_id or "").strip()
    if not rid or not DB_PATH.exists():
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload_json, created_at FROM reviews WHERE review_id=?",
            (rid,),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row["payload_json"]))
    except (TypeError, json.JSONDecodeError):
        payload = {"review_id": rid, "status": "CORRUPT_SAVED_PAYLOAD"}
    if isinstance(payload, dict):
        payload.setdefault("created_at", row["created_at"])
        return payload
    return {"review_id": rid, "created_at": row["created_at"], "payload": payload}


def load_student_history(student_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT review_id, task_type, final_score, max_score, status, error_class, summary, created_at
            FROM reviews WHERE student_id=? ORDER BY created_at DESC LIMIT ?
            """,
            (student_id, max(1, min(int(limit), 50))),
        ).fetchall()
    return [dict(row) for row in rows]


def metrics_summary(*, limit: int = 200) -> dict[str, Any]:
    """Small local metrics snapshot from persisted reviews for demo/defense."""
    if not DB_PATH.exists():
        return {
            "reviews": 0,
            "success_rate": None,
            "error_rate": None,
            "manual_review_rate": None,
            "average_final_score": None,
            "average_agent_seconds": {},
            "status_counts": {},
        }

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT final_score, status, payload_json
            FROM reviews ORDER BY created_at DESC LIMIT ?
            """,
            (max(1, min(int(limit), 1000)),),
        ).fetchall()

    status_counts: dict[str, int] = {}
    scores: list[float] = []
    manual_count = 0
    error_count = 0
    agent_values: dict[str, list[float]] = {name: [] for name in ("vision", "solver", "grader", "reviewer")}

    for row in rows:
        status = str(row["status"] or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        if row["final_score"] is not None:
            scores.append(float(row["final_score"]))
        try:
            payload = json.loads(str(row["payload_json"]))
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if bool(payload.get("reviewer_manual_review_required", False)):
            manual_count += 1
        if payload.get("errors"):
            error_count += 1
        for name in agent_values:
            try:
                value = float(payload.get(f"{name}_elapsed_seconds", 0) or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                agent_values[name].append(value)

    total = len(rows)
    success_count = sum(1 for row in rows if row["final_score"] is not None)
    averages = {
        name: (round(sum(values) / len(values), 3) if values else None)
        for name, values in agent_values.items()
    }
    return {
        "reviews": total,
        "success_rate": round(success_count / total, 4) if total else None,
        "error_rate": round(error_count / total, 4) if total else None,
        "manual_review_rate": round(manual_count / total, 4) if total else None,
        "average_final_score": round(sum(scores) / len(scores), 3) if scores else None,
        "average_agent_seconds": averages,
        "status_counts": status_counts,
        "sample_limit": max(1, min(int(limit), 1000)),
    }


def save_report(review_id: str, report: dict[str, Any]) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in str(review_id) if ch.isalnum() or ch in "-_.")
    path = REPORTS_DIR / f"{safe}.json"
    path.write_text(json.dumps(_json_safe(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
