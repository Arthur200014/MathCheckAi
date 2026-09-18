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
    build_ege13_task_statement,
    extract_interval_draft,
    extract_task_equation_draft,
    normalize_interval_input,
    task_fields_issue_message,
    validate_task_fields,
)

app = FastAPI(
    title="MathCheck AI",
    version="0.4.14-stage2.9.7.10-ege13-equation-interval-input",
    description=(
        "One photo -> Vision transcribes the student's work -> the source equation is extracted from the student's leading line -> "
        "the human confirms equation, part-b interval and student solution -> grading. "
        "No printed task statement is required on the photo."
    ),
)

MAX_IMAGE_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
UI_INDEX_PATH = Path(__file__).resolve().parent.parent / "web" / "index29710.html"


class ReviewRequest(BaseModel):
    student_id: str = Field(default="student-001")
    task_type: str = Field(default="ege_13")
    task_statement: str = Field(default="Решите уравнение sin(x)=1/2 и выполните отбор корней на промежутке.")


class TranscriptConfirmationRequest(BaseModel):
    review_id: str
    student_id: str = "student-001"
    task_type: str = "ege_13"
    confirmed_task_equation: str = ""
    confirmed_interval: str = ""
    task_statement: str = ""
    original_task_statement: str = ""
    confirmed_task_statement: str = ""
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
    if not UI_INDEX_PATH.exists():
        raise HTTPException(status_code=500, detail="Веб-интерфейс не найден в сборке.")
    return FileResponse(UI_INDEX_PATH, media_type="text/html; charset=utf-8")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "stage": "2.9.7.10-ege13-equation-interval-input",
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
        "single_photo_extracts_student_work": True,
        "task_equation_source": "student_leading_equation_then_human_confirmation",
        "part_b_interval_source": "visible_if_present_else_human_input",
        "math_keyboard_shortcuts_enabled": True,
        "human_readable_confirmation_editor": True,
        "raw_latex_hidden_in_technical_json": True,
        "photo_human_confirmation_required": True,
        "ocr_confidence_can_auto_accept": False,
        "grading_source": "confirmed_task_equation+confirmed_interval+confirmed_transcript",
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

    transcript = str(result.get("transcript", "") or "")
    detected_statement = str(result.get("detected_task_statement", "") or "")
    equation, equation_source = extract_task_equation_draft(transcript, detected_statement)
    interval, interval_source = extract_interval_draft(transcript, detected_statement)

    result["detected_task_equation"] = equation
    result["detected_interval"] = interval
    result["task_equation_draft_source"] = equation_source
    result["interval_draft_source"] = interval_source
    result["display_task_equation"] = latex_to_human_text(equation)
    result["display_interval"] = latex_to_human_text(interval)
    result["display_transcript"] = latex_to_human_text(transcript)

    result.setdefault("detected_task_statement", detected_statement)
    result.setdefault("original_task_statement", detected_statement)
    result["confirmed_task_statement"] = ""
    result["task_statement_confirmation_source"] = "pending_human"

    field_issues = validate_task_fields(task_type, equation, interval)
    result["task_input_preflight_issues"] = field_issues
    if field_issues:
        existing = list(result.get("task_uncertain_fragments", []) or [])
        hint = "Перед проверкой проверь поля задания: " + task_fields_issue_message(field_issues) + "."
        if hint not in existing:
            existing.append(hint)
        result["task_uncertain_fragments"] = existing[:6]

    if result.get("human_confirmation_required", False) and transcript.strip():
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
        raise HTTPException(status_code=400, detail="Подтверждённое решение не может быть пустым.")

    equation = payload.confirmed_task_equation.strip()
    interval = normalize_interval_input(payload.confirmed_interval)

    if equation or interval:
        issues = validate_task_fields(payload.task_type, equation, interval)
        if issues:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Данные задания подтверждены не полностью: "
                    + task_fields_issue_message(issues)
                    + ". Solver ещё не запускался."
                ),
            )
        confirmed_statement = build_ege13_task_statement(equation, interval)
    else:
        confirmed_statement = (payload.confirmed_task_statement or payload.task_statement).strip()
        if not confirmed_statement:
            raise HTTPException(status_code=400, detail="Нужно подтвердить исходное уравнение и интервал пункта б.")

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
        "confirmed_task_equation": equation,
        "confirmed_interval": interval,
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
