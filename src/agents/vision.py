from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from src.state import ReviewState
from src.llm.ollama_client import OllamaError, ollama_chat_json
from src.tools.solution_steps import split_solution_step_texts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTO_ACCEPT_CONFIDENCE = 0.90
MANUAL_REVIEW_CONFIDENCE = 0.60

VISION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task_statement_latex": {"type": "string"},
        "student_transcript_latex": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "task_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertain_fragments": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        },
        "task_uncertain_fragments": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        },
    },
    "required": [
        "task_statement_latex",
        "student_transcript_latex",
        "confidence",
        "task_confidence",
        "uncertain_fragments",
        "task_uncertain_fragments",
    ],
    "additionalProperties": False,
}


def _load_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _split_transcript_steps(transcript: str, *, max_steps: int = 24) -> list[str]:

    return split_solution_step_texts(transcript, max_steps=max_steps)


def evaluate_transcript_gate(
    transcript: str,
    confidence: float,
    uncertain_fragments: list[str],
    *,
    vision_error: bool = False,
) -> dict:









    clean_uncertain = [str(x).strip() for x in uncertain_fragments if str(x).strip()]

    if vision_error or not transcript.strip():
        return {
            "needs_confirmation": True,
            "transcript_confirmed": False,
            "status": "MANUAL_REVIEW_REQUIRED",
            "uncertain_fragments": clean_uncertain,
        }

    return {
        "needs_confirmation": True,
        "transcript_confirmed": False,
        "status": "NEEDS_TRANSCRIPT_CONFIRMATION",
        "uncertain_fragments": clean_uncertain,
    }


def _detect_suspicious_ocr_fragments(transcript: str) -> list[str]:

    text = str(transcript or "")
    found: list[str] = []
    allowed_text = {"или", "ответ", "и", "где", "при", "корни", "найдём", "найдем"}
    for match in re.finditer(r"\\text\{\s*([^{}]+?)\s*\}", text, flags=re.IGNORECASE):
        inner = match.group(1).strip()
        lower = inner.lower()
        if lower in allowed_text:
            continue
        if re.search(r"[A-Za-z]{2,}", inner):
            found.append(match.group(0))
        elif "�" in inner:
            found.append(match.group(0))

    allowed_latin = {
        "sin", "cos", "tan", "tg", "ctg", "sqrt", "frac", "pi", "text",
        "begin", "end", "cases", "quad", "qquad", "mathbb", "left", "right",
    }
    for raw_line in text.splitlines():
        words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", raw_line)]
        weird = [w for w in words if w not in allowed_latin]
        if len(weird) >= 2:
            fragment = raw_line.strip()
            if fragment:
                found.append(fragment[:180])

    if "�" in text and "�" not in found:
        found.append("�")
    out: list[str] = []
    for item in found:
        if item not in out:
            out.append(item)
    return out[:6]


def _as_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _as_string_list(value: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        value = [] if value is None else [value]
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out[:limit]


def _telemetry_fields(telemetry: dict[str, Any] | None) -> dict[str, Any]:
    t = telemetry or {}
    return {
        "vision_ollama_total_seconds": t.get("total_seconds"),
        "vision_ollama_load_seconds": t.get("load_seconds"),
        "vision_ollama_prompt_eval_seconds": t.get("prompt_eval_seconds"),
        "vision_ollama_generation_seconds": t.get("generation_seconds"),
        "vision_ollama_prompt_tokens": t.get("prompt_tokens"),
        "vision_ollama_output_tokens": t.get("output_tokens"),
        "vision_ollama_prompt_tokens_per_second": t.get("prompt_tokens_per_second"),
        "vision_ollama_generation_tokens_per_second": t.get("generation_tokens_per_second"),
        "vision_ollama_done_reason": t.get("done_reason"),
        "vision_num_ctx": t.get("num_ctx"),
        "vision_num_predict_custom_cap": bool(t.get("custom_output_cap", False)),
    }


def vision_agent(state: ReviewState) -> dict:







    image_b64 = state.get("image_b64")
    statement_hint = state.get("task_statement", "")

    if not image_b64:
        transcript = f"[MOCK transcript — no image] Ученик решает: {statement_hint}"
        return {
            "detected_task_statement": statement_hint,
            "original_task_statement": statement_hint,
            "confirmed_task_statement": statement_hint,
            "task_statement_confidence": 1.0,
            "task_uncertain_fragments": [],
            "task_statement_confirmation_source": "request",
            "transcript": transcript,
            "original_transcript": transcript,
            "confirmed_transcript": transcript,
            "transcript_steps": _split_transcript_steps(transcript),
            "transcript_confidence": 0.99,
            "vision_model": "mock/no-image",
            "needs_confirmation": False,
            "transcript_confirmed": True,
            "status": "TRANSCRIPT_CONFIRMED",
            "uncertain_fragments": [],
        }

    system_prompt = _load_text("prompts/vision_agent.md")
    skill = _load_text("skills/common/transcribe_math_solution.md")
    fallback_hint = statement_hint.strip()
    hint_block = (
        f"\nНеобязательная подсказка API (не копируй её вместо видимого условия):\n{fallback_hint}\n"
        if fallback_hint
        else ""
    )
    user_prompt = f"""
На фотографии может быть одновременно условие задания и решение ученика.
Сделай одну буквальную транскрипцию за один Vision-проход.
Не решай задачу, не исправляй математику и не дописывай отсутствующие шаги.
{hint_block}
Skill:
{skill}

Заполни поля структурированного ответа:
- task_statement_latex: только реально видимое условие; если его нет, пустая строка;
- student_transcript_latex: только реально написанное учеником решение сверху вниз;
- confidence и task_confidence: числа от 0 до 1;
- uncertain_fragments и task_uncertain_fragments: только реально сомнительные места, максимум 6.

Дополнительно:
- русские слова сохраняй кириллицей;
- строку `Ответ:` перепиши буквально;
- не описывай рисунок или тригонометрическую окружность словами;
- не повторяй уже переписанные строки;
- сохраняй знаки, дроби, π, интервалы и параметры k/n максимально буквально.
""".strip()

    vision_ctx = int(os.getenv("OLLAMA_VISION_NUM_CTX", "16384"))
    vision_num_predict = int(os.getenv("OLLAMA_VISION_NUM_PREDICT", "2048"))
    try:
        result = ollama_chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_b64=image_b64,
            response_schema=VISION_RESPONSE_SCHEMA,
            num_ctx=vision_ctx,
            num_predict=vision_num_predict,
            use_num_predict_limit=True,
        )
    except OllamaError as exc:
        telemetry = getattr(exc, "telemetry", {}) or {}
        gate = evaluate_transcript_gate("", 0.0, [str(exc)], vision_error=True)
        return {
            "detected_task_statement": "",
            "original_task_statement": "",
            "confirmed_task_statement": "",
            "task_statement_confidence": 0.0,
            "task_uncertain_fragments": [str(exc)],
            "task_statement_confirmation_source": "pending_human",
            "transcript": "",
            "original_transcript": "",
            "confirmed_transcript": "",
            "transcript_steps": [],
            "transcript_confidence": 0.0,
            "vision_model": str(telemetry.get("model") or "ollama-error"),
            "vision_elapsed_seconds": float(telemetry.get("wall_seconds") or 0),
            "errors": [f"vision:{exc}"],
            **_telemetry_fields(telemetry),
            **gate,
        }

    detected_statement = str(
        result.get("task_statement_latex", result.get("task_statement", "")) or ""
    ).strip()
    transcript = str(
        result.get("student_transcript_latex", result.get("transcript_latex", "")) or ""
    ).strip()

    confidence = _as_confidence(result.get("confidence", 0.0))
    task_confidence = _as_confidence(result.get("task_confidence", confidence))
    uncertain = _as_string_list(result.get("uncertain_fragments", []))
    task_uncertain = _as_string_list(result.get("task_uncertain_fragments", []))

    for item in _detect_suspicious_ocr_fragments(transcript):
        if item not in uncertain:
            uncertain.append(item)
    uncertain = uncertain[:6]

    telemetry = result.get("_ollama_telemetry", {})
    gate = evaluate_transcript_gate(transcript, confidence, uncertain)
    return {
        "detected_task_statement": detected_statement,
        "original_task_statement": detected_statement,
        "confirmed_task_statement": "",
        "task_statement_confidence": task_confidence,
        "task_uncertain_fragments": task_uncertain,
        "task_statement_confirmation_source": "pending_human",
        "transcript": transcript,
        "original_transcript": transcript,
        "confirmed_transcript": "",
        "transcript_steps": _split_transcript_steps(transcript),
        "transcript_confidence": confidence,
        "vision_model": str(result.get("_model", "qwen3-vl")),
        "vision_elapsed_seconds": float(result.get("_elapsed_seconds", 0) or 0),
        **_telemetry_fields(telemetry),
        **gate,
    }
