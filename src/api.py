import base64
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from PIL import Image

from src.graph import post_confirmation_graph, review_graph
from src.llm.config import get_grader_model, get_reviewer_model, get_solver_model, get_vision_model
from src.observability.runtime import observability_status
from src.llm.ollama_client import ollama_runtime_info
from src.pending_store import (
    delete_pending,
    delete_pending_image,
    load_pending_image_b64,
    load_pending_state,
    save_pending_image,
    save_pending_state,
)
from src.task_registry import list_task_profiles
from src.tools.core import load_student_history
from src.tools.ege13_report import report_circle_path
from src.tools.display_math import latex_to_human_text
from src.tools.ege13_task_input import (
    infer_task_statement_draft,
    task_statement_issue_message,
    validate_confirmed_task_statement,
)

app = FastAPI(
    title="MathCheck AI",
    version="0.4.13-stage2.9.7.9-ege13-task-preflight",
    description=(
        "One photo -> Vision extracts task statement + student work -> human edits readable math -> confirms both -> grading. "
        "Vision output is only a draft; confirmed task_statement and confirmed_transcript are the sole grading inputs. "
        "EGE-13 task completeness is validated before Solver/Grader/Reviewer can run."
    ),
)

MAX_IMAGE_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
UI_INDEX_PATH = Path(__file__).resolve().parent.parent / "web" / "index.html"


class ReviewRequest(BaseModel):
    student_id: str = Field(default="student-001")
    task_type: str = Field(default="ege_13")
    task_statement: str = Field(default="Решите уравнение sin(x)=1/2 и выполните отбор корней на промежутке.")


class TranscriptConfirmationRequest(BaseModel):
    review_id: str
    student_id: str = "student-001"
    task_type: str = "ege_13"
    # `task_statement` remains for backward compatibility with older clients.
    task_statement: str = ""
    original_task_statement: str = ""
    confirmed_task_statement: str = Field(
        default="",
        description="Подтверждённое/исправленное человеком условие задания",
    )
    original_transcript: str = ""
    confirmed_transcript: str = Field(description="Подтверждённая или исправленная пользователем транскрипция решения")


def _base_state(student_id: str, task_type: str, task_statement: str) -> dict:
    review_id = f"r-{uuid4().hex[:8]}"
    return {
        "review_id": review_id,
        "trace_id": review_id,
        "student_id": student_id,
        "task_type": task_type,
        "task_statement": task_statement,
        "errors": [],
        "warnings": [],
    }


def _inspect_original_image(image_bytes: bytes) -> dict:
    """Validate the upload without changing a single image byte.

    Stage 2.9.7 intentionally sends the original PNG/JPEG/WEBP bytes to the
    Vision model. No resize, no JPEG conversion, no quality loss.
    """
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
            image_format = str(img.format or "unknown")
            img.verify()
        return {
            "image_width": int(width),
            "image_height": int(height),
            "image_format": image_format,
            "image_original_bytes": len(image_bytes),
            "image_preprocessing": "none-original-bytes",
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать изображение: {exc}") from exc


@app.get("/", include_in_schema=False)
def web_ui():
    """Single-page browser UI for the full photo -> confirm -> grade flow."""
    if not UI_INDEX_PATH.exists():
        raise HTTPException(status_code=500, detail="Веб-интерфейс не найден в сборке.")
    return FileResponse(UI_INDEX_PATH, media_type="text/html; charset=utf-8")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "stage": "2.9.7.9-ege13-task-preflight",
        "ollama_transport": "ndjson-stream-idle-timeout-emergency-ceiling",
        "ollama_connect_timeout_seconds": int(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "15")),
        "ollama_idle_timeout_seconds": int(os.getenv("OLLAMA_IDLE_TIMEOUT_SECONDS", "180")),
        "ollama_vision_total_timeout_seconds": int(os.getenv("OLLAMA_VISION_TOTAL_TIMEOUT_SECONDS", "900")),
        "ollama_text_total_timeout_seconds": int(os.getenv("OLLAMA_TEXT_TOTAL_TIMEOUT_SECONDS", "900")),
        "agents": ["vision", "solver", "grader", "reviewer"],
        "langgraph_four_agent_flow": True,
        "vision_solver_parallel": False,
        "vision_input_image_mode": "original-bytes-no-resize-no-recompression",
        "vision_num_ctx": int(os.getenv("OLLAMA_VISION_NUM_CTX", "16384")),
        "vision_custom_output_cap": False,
        "ollama_phase_telemetry_enabled": True,
        "grader_single_pass": True,
        "reviewer_single_pass": True,
        "grader_custom_output_cap": False,
        "reviewer_custom_output_cap": False,
        "score_source": "deterministic_ege13_rubric",
        "student_evidence_source_locked": True,
        "browser_ui_enabled": True,
        "browser_ui_human_confirmation": True,
        "single_photo_extracts_task_and_solution": True,
        "human_readable_confirmation_editor": True,
        "raw_latex_hidden_in_technical_json": True,
        "photo_human_confirmation_required": True,
        "task_statement_human_confirmation_required": True,
        "task_statement_preflight_required": True,
        "task_statement_fallback_from_visible_leading_equation": True,
        "ocr_confidence_can_auto_accept": False,
        "grading_source": "confirmed_task_statement+confirmed_transcript",
        "review_advisory_blocks_score": False,
        "deterministic_step_overrides": True,
        "student_diagram_vision_enabled": False,
        "reference_circle_renderer_enabled": True,
        "sqlite_memory_enabled": True,
        "vision_model": get_vision_model(),
        "solver_model": get_solver_model(),
        "grader_model": get_grader_model(),
        "reviewer_model": get_reviewer_model(),
        "ollama_keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "15m"),
        "observability": observability_status(),
    }


@app.get("/api/debug/ollama")
def debug_ollama():
    """Ollama version + currently loaded model memory data.

    Useful when Vision is unexpectedly slow. `/api/ps` commonly exposes
    `size_vram`; together with per-call timings this helps distinguish model
    load, prompt/image evaluation, and token generation bottlenecks.
    """
    return ollama_runtime_info()


@app.get("/api/task-types")
def task_types():
    return {"tasks": list_task_profiles()}


@app.get("/api/reviews/{review_id}/report-circle")
def get_report_circle(review_id: str):
    path = report_circle_path(review_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Окружность для этого review_id не найдена или ещё не построена.")
    return FileResponse(path, media_type="image/png", filename=f"{review_id}-trig-circle.png")


@app.get("/api/students/{student_id}/history")
def student_history(student_id: str, limit: int = 10):
    return {"student_id": student_id, "reviews": load_student_history(student_id, limit=limit)}


@app.post("/api/reviews")
def create_review(payload: ReviewRequest):
    return review_graph.invoke(_base_state(payload.student_id, payload.task_type, payload.task_statement))


@app.post("/api/reviews/photo")
async def create_review_from_photo(
    image: UploadFile = File(...),
    student_id: str = Form("student-001"),
    task_type: str = Form("ege_13"),
    task_statement: str = Form(""),
):
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Поддерживаются JPEG, PNG и WEBP.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Файл изображения пустой.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Изображение больше 12 МБ.")

    image_meta = _inspect_original_image(image_bytes)
    initial_state = _base_state(student_id, task_type, task_statement)
    save_pending_image(initial_state["review_id"], image_bytes)
    initial_state.update(
        {
            "image_b64": base64.b64encode(image_bytes).decode("ascii"),
            "image_filename": image.filename or "solution-image",
            "human_confirmation_required": True,
            "human_confirmation_completed": False,
            "transcript_confirmation_source": "pending_human",
            "task_statement_confirmation_source": "pending_human",
            **image_meta,
        }
    )

    result = review_graph.invoke(initial_state)
    result.pop("image_b64", None)

    # Vision should extract both task and solution. If it leaves the task empty
    # but the first visible student line is literally the task equation, reuse
    # only that visible line as an editable draft. Never invent part b/interval.
    detected_statement = str(result.get("detected_task_statement", "") or "").strip()
    draft_statement, draft_source = infer_task_statement_draft(
        detected_statement,
        str(result.get("transcript", "") or ""),
    )
    if draft_statement and not detected_statement:
        result["detected_task_statement"] = draft_statement
        result["original_task_statement"] = draft_statement
        result["task_statement_draft_source"] = draft_source
    else:
        result.setdefault("detected_task_statement", str(result.get("original_task_statement", "") or ""))
        result.setdefault("original_task_statement", str(result.get("detected_task_statement", "") or ""))
        result["task_statement_draft_source"] = draft_source

    task_issues = validate_confirmed_task_statement(
        task_type,
        str(result.get("detected_task_statement", "") or ""),
    )
    result["task_statement_preflight_issues"] = task_issues
    if task_issues:
        human_hint = task_statement_issue_message(task_issues)
        existing = list(result.get("task_uncertain_fragments", []) or [])
        hint = f"Перед проверкой дополни условие: {human_hint}."
        if hint not in existing:
            existing.append(hint)
        result["task_uncertain_fragments"] = existing[:6]

    result["confirmed_task_statement"] = ""
    result["task_statement_confirmation_source"] = "pending_human"
    result["display_task_statement"] = latex_to_human_text(
        str(result.get("detected_task_statement", "") or "")
    )
    result["display_transcript"] = latex_to_human_text(
        str(result.get("transcript", "") or "")
    )

    # API-level invariant in addition to the graph gate: any non-empty OCR from
    # a photo is only a draft until the human confirmation endpoint is called.
    if result.get("human_confirmation_required", False) and result.get("transcript", "").strip():
        result["needs_confirmation"] = True
        result["transcript_confirmed"] = False
        result["confirmed_transcript"] = ""
        result["status"] = "NEEDS_TRANSCRIPT_CONFIRMATION"
        result["human_confirmation_completed"] = False
        result["transcript_confirmation_source"] = "pending_human"

    if result.get("needs_confirmation", False):
        save_pending_state(initial_state["review_id"], result)
    else:
        delete_pending(initial_state["review_id"])
    return result


@app.post("/api/reviews/confirm-transcript")
def confirm_transcript(payload: TranscriptConfirmationRequest):
    confirmed = payload.confirmed_transcript.strip()
    if not confirmed:
        raise HTTPException(status_code=400, detail="confirmed_transcript не может быть пустым.")

    confirmed_statement = (payload.confirmed_task_statement or payload.task_statement).strip()
    if not confirmed_statement:
        raise HTTPException(status_code=400, detail="Подтверждённое условие задания не может быть пустым.")

    # Hard preflight before any expensive LLM call. Human confirmation is the
    # source of truth, but for EGE-13 it must include both the equation and the
    # part-b interval. We never let Solver guess missing task data.
    task_issues = validate_confirmed_task_statement(payload.task_type, confirmed_statement)
    if task_issues:
        raise HTTPException(
            status_code=422,
            detail=(
                "Условие №13 подтверждено не полностью: "
                + task_statement_issue_message(task_issues)
                + ". Исправь поле «Условие задания» и нажми подтверждение ещё раз. "
                "Solver ещё не запускался."
            ),
        )

    # Image is not needed after OCR confirmation because Diagram Vision is not
    # in the fast four-agent runtime flow. Keep loading it only for compatibility.
    _ = load_pending_image_b64(payload.review_id)
    pending = load_pending_state(payload.review_id)

    original_statement = (
        payload.original_task_statement.strip()
        or str(pending.get("original_task_statement", "") or "").strip()
        or str(pending.get("detected_task_statement", "") or "").strip()
    )
    original_transcript = (
        payload.original_transcript.strip()
        or str(pending.get("original_transcript", "") or "").strip()
        or str(pending.get("transcript", "") or "").strip()
    )

    state = {
        **pending,
        "review_id": payload.review_id,
        "trace_id": payload.review_id,
        "student_id": payload.student_id,
        "task_type": payload.task_type,
        "task_statement": confirmed_statement,
        "detected_task_statement": original_statement,
        "original_task_statement": original_statement,
        "confirmed_task_statement": confirmed_statement,
        "task_statement_confirmation_source": "human",
        "original_transcript": original_transcript,
        "confirmed_transcript": confirmed,
        "transcript": confirmed,
        "transcript_confirmed": True,
        "needs_confirmation": False,
        "human_confirmation_required": False,
        "human_confirmation_completed": True,
        "transcript_confirmation_source": "human",
        "status": "TRANSCRIPT_CONFIRMED",
        "uncertain_fragments": [],
        "task_uncertain_fragments": [],
        "errors": [],
        "warnings": [],
    }
    result = post_confirmation_graph.invoke(state)
    result.pop("image_b64", None)
    delete_pending(payload.review_id)
    return result
