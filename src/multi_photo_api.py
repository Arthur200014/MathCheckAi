from __future__ import annotations

import base64
from io import BytesIO

from fastapi import File, Form, HTTPException, UploadFile
from PIL import Image, ImageOps

from src import api

MAX_PHOTOS = 8
MAX_PAGE_WIDTH = 2200
PAGE_GAP = 28


def _stitch_pages(pages: list[bytes]) -> tuple[bytes, list[dict]]:






    prepared: list[Image.Image] = []
    page_meta: list[dict] = []

    for number, raw in enumerate(pages, start=1):
        try:
            with Image.open(BytesIO(raw)) as opened:
                img = ImageOps.exif_transpose(opened).convert("RGB")
                original_width, original_height = img.size
                if img.width > MAX_PAGE_WIDTH:
                    new_height = max(1, round(img.height * MAX_PAGE_WIDTH / img.width))
                    img = img.resize((MAX_PAGE_WIDTH, new_height), Image.Resampling.LANCZOS)
                prepared.append(img.copy())
                page_meta.append(
                    {
                        "page": number,
                        "original_width": original_width,
                        "original_height": original_height,
                        "vision_width": img.width,
                        "vision_height": img.height,
                    }
                )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Не удалось прочитать фото {number}: {exc}") from exc

    width = max(img.width for img in prepared)
    height = sum(img.height for img in prepared) + PAGE_GAP * (len(prepared) - 1)
    sheet = Image.new("RGB", (width, height), "white")

    y = 0
    for index, img in enumerate(prepared):
        x = (width - img.width) // 2
        sheet.paste(img, (x, y))
        y += img.height
        if index < len(prepared) - 1:
            y += PAGE_GAP

    buffer = BytesIO()
    sheet.save(buffer, format="JPEG", quality=94, subsampling=0, optimize=False)
    return buffer.getvalue(), page_meta


def _finish_photo_result(result: dict, *, review_id: str) -> dict:
    transcript = str(result.get("transcript", "") or "")
    detected_statement = str(result.get("detected_task_statement", "") or "")
    equation, equation_source = api.extract_task_equation_draft(transcript, detected_statement)
    interval, interval_source = api.extract_interval_draft(transcript, detected_statement)

    result["detected_task_equation"] = equation
    result["detected_interval"] = interval
    result["task_equation_draft_source"] = equation_source
    result["interval_draft_source"] = interval_source
    result["display_task_equation"] = api.latex_to_human_text(equation)
    result["display_interval"] = api.latex_to_human_text(interval)
    result["display_transcript"] = api.latex_to_human_text(transcript)

    result.setdefault("detected_task_statement", detected_statement)
    result.setdefault("original_task_statement", detected_statement)
    result["confirmed_task_statement"] = ""
    result["task_statement_confirmation_source"] = "pending_human"

    field_issues = api.validate_task_fields(result.get("task_type", "ege_13"), equation, interval)
    result["task_input_preflight_issues"] = field_issues
    if field_issues:
        existing = list(result.get("task_uncertain_fragments", []) or [])
        hint = "Перед проверкой проверь поля задания: " + api.task_fields_issue_message(field_issues) + "."
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

    result["stage_timings"] = api.progress_snapshot(review_id)
    if result.get("needs_confirmation", False):
        api.save_pending_state(review_id, result)
    else:
        api.delete_pending(review_id)
    return result


@api.app.post("/api/reviews/photos")
async def create_review_from_photos(
    images: list[UploadFile] = File(...),
    student_id: str = Form("student-001"),
    task_type: str = Form("ege_13"),
    task_statement: str = Form(""),
):

    if not images:
        raise HTTPException(status_code=400, detail="Нужно выбрать хотя бы одно фото.")
    if len(images) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Можно загрузить максимум {MAX_PHOTOS} фото одной работы.")

    raw_pages: list[bytes] = []
    names: list[str] = []
    total_original_bytes = 0
    for number, image in enumerate(images, start=1):
        if image.content_type not in api.ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=415, detail=f"Фото {number}: поддерживаются JPEG, PNG и WEBP.")
        data = await image.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"Фото {number} пустое.")
        if len(data) > api.MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail=f"Фото {number} больше 12 МБ.")
                                                            
        api._inspect_original_image(data)
        raw_pages.append(data)
        names.append(image.filename or f"page-{number}")
        total_original_bytes += len(data)

    if len(raw_pages) == 1:
        vision_bytes = raw_pages[0]
        page_meta = []
        preprocessing = "none-original-bytes"
    else:
        vision_bytes, page_meta = _stitch_pages(raw_pages)
        preprocessing = "multi-photo-single-vision-pass-stitch-max-width-2200"

    image_meta = api._inspect_original_image(vision_bytes)
    image_meta["image_preprocessing"] = preprocessing

    initial_state = api._base_state(student_id, task_type, task_statement)
    review_id = initial_state["review_id"]
    api.reset_progress(review_id)
    api.save_pending_image(review_id, vision_bytes)
    initial_state.update(
        {
            "image_b64": base64.b64encode(vision_bytes).decode("ascii"),
            "image_filename": names[0] if len(names) == 1 else f"{len(names)}-pages.jpg",
            "multi_photo_count": len(names),
            "multi_photo_filenames": names,
            "multi_photo_page_meta": page_meta,
            "multi_photo_original_bytes": total_original_bytes,
            "vision_page_order": "top-to-bottom",
            "human_confirmation_required": True,
            "human_confirmation_completed": False,
            "transcript_confirmation_source": "pending_human",
            "task_statement_confirmation_source": "pending_human",
            **image_meta,
        }
    )

    result = api.review_graph.invoke(initial_state)
    result.pop("image_b64", None)
    result["multi_photo_count"] = len(names)
    result["multi_photo_filenames"] = names
    result["multi_photo_page_meta"] = page_meta
    result["multi_photo_original_bytes"] = total_original_bytes
    result["vision_strategy"] = "single_call_all_pages"
    return _finish_photo_result(result, review_id=review_id)
