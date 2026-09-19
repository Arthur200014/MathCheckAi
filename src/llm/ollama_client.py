import http.client
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from src.llm.config import get_ollama_base_url, get_vision_model
from src.observability.runtime import log_llm_call


class OllamaError(RuntimeError):
    """Structured failure from the local Ollama runtime.

    The client always preserves telemetry on failures. In particular, timeout
    errors carry elapsed time and partial streaming progress, so the API never
    reports a misleading ``0 seconds`` failure.
    """

    def __init__(
        self,
        message: str,
        *,
        telemetry: dict[str, Any] | None = None,
        code: str = "OLLAMA_ERROR",
    ):
        super().__init__(message)
        self.telemetry = telemetry or {}
        self.code = code


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _ns_to_seconds(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value) / 1_000_000_000.0, 4)
    except (TypeError, ValueError):
        return None


def _rate(count: Any, duration_ns: Any) -> float | None:
    try:
        count_f = float(count)
        seconds = float(duration_ns) / 1_000_000_000.0
        if seconds <= 0:
            return None
        return round(count_f / seconds, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _env_positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _telemetry_from_raw(
    raw: dict[str, Any],
    *,
    wall_seconds: float,
    model_name: str,
    has_image: bool,
    num_ctx: int | None,
    num_predict: int | None,
    custom_output_cap: bool,
    chunks_received: int = 0,
    output_chars: int = 0,
    total_deadline_seconds: int | None = None,
    idle_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    prompt_count = raw.get("prompt_eval_count")
    prompt_duration = raw.get("prompt_eval_duration")
    eval_count = raw.get("eval_count")
    eval_duration = raw.get("eval_duration")
    return {
        "model": raw.get("model", model_name),
        "wall_seconds": round(wall_seconds, 3),
        "elapsed_seconds": round(wall_seconds, 3),
        "total_seconds": _ns_to_seconds(raw.get("total_duration")),
        "load_seconds": _ns_to_seconds(raw.get("load_duration")),
        "prompt_eval_seconds": _ns_to_seconds(prompt_duration),
        "generation_seconds": _ns_to_seconds(eval_duration),
        "prompt_tokens": prompt_count,
        "output_tokens": eval_count,
        "prompt_tokens_per_second": _rate(prompt_count, prompt_duration),
        "generation_tokens_per_second": _rate(eval_count, eval_duration),
        "done_reason": raw.get("done_reason"),
        "has_image": has_image,
        "num_ctx": num_ctx,
        "num_predict": num_predict if custom_output_cap else None,
        "custom_output_cap": custom_output_cap,
        "transport_mode": "ndjson-stream-prefill-total-deadline-then-idle-timeout",
        "chunks_received": chunks_received,
        "partial_output_chars": output_chars,
        "total_deadline_seconds": total_deadline_seconds,
        "idle_timeout_seconds": idle_timeout_seconds,
    }


def _open_streaming_post(
    *,
    url: str,
    payload: dict[str, Any],
    connect_timeout_seconds: int,
    total_deadline_seconds: float,
    started: float,
):
    """Open Ollama's NDJSON stream with separate connect and runtime deadlines.

    Vision can spend a long time encoding/prefilling an image before the first
    streamed token exists. That phase is bounded by the total request deadline,
    not by the token-to-token idle timeout. The idle timeout starts only after
    streaming has actually begun.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise OllamaError(
            f"Неподдерживаемая схема OLLAMA_BASE_URL: {parsed.scheme}",
            code="OLLAMA_BAD_URL",
        )

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(host, port, timeout=connect_timeout_seconds)

    body = json.dumps(payload).encode("utf-8")
    try:
        conn.request(
            "POST",
            path,
            body=body,
            headers={"Content-Type": "application/json"},
        )
        remaining = total_deadline_seconds - (time.perf_counter() - started)
        if remaining <= 0:
            raise TimeoutError("total deadline reached before response")
        if conn.sock is not None:
            conn.sock.settimeout(max(0.1, remaining))
        response = conn.getresponse()
        return conn, response
    except Exception:
        conn.close()
        raise


def ollama_chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    image_b64: str | None = None,
    model: str | None = None,
    timeout: int | None = None,
    response_schema: dict[str, Any] | None = None,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    use_num_predict_limit: bool = True,
) -> dict[str, Any]:
    """Call local Ollama with bounded NDJSON streaming.

    Reliability rules:
    - connection establishment has a short dedicated timeout;
    - image encoding/prefill may legitimately be slow and is bounded by the
      overall request deadline;
    - once the first stream chunk arrives, token-to-token stalls are bounded by
      the idle timeout;
    - a wall-clock ceiling still prevents a runaway generation from living
      forever.
    """
    base_url = get_ollama_base_url()
    model_name = model or get_vision_model()
    has_image = bool(image_b64)

    connect_timeout = _env_positive_int("OLLAMA_CONNECT_TIMEOUT_SECONDS", 15)
    idle_timeout = _env_positive_int("OLLAMA_IDLE_TIMEOUT_SECONDS", 180)
    default_total = 900
    total_env = "OLLAMA_VISION_TOTAL_TIMEOUT_SECONDS" if has_image else "OLLAMA_TEXT_TOTAL_TIMEOUT_SECONDS"
    total_deadline = float(timeout) if timeout is not None else float(_env_positive_int(total_env, default_total))

    user_message: dict[str, Any] = {"role": "user", "content": user_prompt}
    if image_b64:
        user_message["images"] = [image_b64]

    if num_ctx is None:
        num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

    options: dict[str, Any] = {"temperature": 0, "num_ctx": num_ctx}
    custom_output_cap = bool(use_num_predict_limit)
    effective_num_predict: int | None = None
    if use_num_predict_limit:
        if num_predict is None:
            num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "2048"))
        effective_num_predict = int(num_predict)
        options["num_predict"] = effective_num_predict

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            user_message,
        ],
        "stream": True,
        "think": False,
        "format": response_schema if response_schema is not None else "json",
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "15m"),
        "options": options,
    }

    started = time.perf_counter()
    content_parts: list[str] = []
    chunks_received = 0
    final_raw: dict[str, Any] | None = None

    def partial_telemetry() -> dict[str, Any]:
        elapsed = time.perf_counter() - started
        return {
            "model": model_name,
            "wall_seconds": round(elapsed, 3),
            "elapsed_seconds": round(elapsed, 3),
            "total_seconds": None,
            "load_seconds": None,
            "prompt_eval_seconds": None,
            "generation_seconds": None,
            "prompt_tokens": None,
            "output_tokens": None,
            "prompt_tokens_per_second": None,
            "generation_tokens_per_second": None,
            "done_reason": None,
            "has_image": has_image,
            "num_ctx": num_ctx,
            "num_predict": effective_num_predict if custom_output_cap else None,
            "custom_output_cap": custom_output_cap,
            "transport_mode": "ndjson-stream-prefill-total-deadline-then-idle-timeout",
            "chunks_received": chunks_received,
            "partial_output_chars": sum(len(x) for x in content_parts),
            "total_deadline_seconds": total_deadline,
            "idle_timeout_seconds": idle_timeout,
        }

    conn: http.client.HTTPConnection | http.client.HTTPSConnection | None = None
    try:
        conn, response = _open_streaming_post(
            url=f"{base_url}/api/chat",
            payload=payload,
            connect_timeout_seconds=connect_timeout,
            total_deadline_seconds=total_deadline,
            started=started,
        )

        if response.status >= 400:
            details = response.read().decode("utf-8", errors="replace")
            raise OllamaError(
                f"Ollama HTTP {response.status}: {details}",
                telemetry=partial_telemetry(),
                code="OLLAMA_HTTP_ERROR",
            )

        while True:
            elapsed = time.perf_counter() - started
            remaining = total_deadline - elapsed
            if remaining <= 0:
                t = partial_telemetry()
                raise OllamaError(
                    "OLLAMA_TOTAL_DEADLINE: локальная модель превысила защитный "
                    f"лимит {total_deadline} с. Получено chunks={t['chunks_received']}, "
                    f"chars={t['partial_output_chars']}, elapsed={t['wall_seconds']} с.",
                    telemetry=t,
                    code="OLLAMA_TOTAL_DEADLINE",
                )

            if conn.sock is not None:
                # Before the first chunk the model is still encoding/prefilling
                # the request. That is not a stream stall, so only the total
                # request deadline applies. After streaming starts, the normal
                # token-to-token idle timeout applies.
                read_timeout = remaining if chunks_received == 0 else min(float(idle_timeout), remaining)
                conn.sock.settimeout(max(0.1, read_timeout))

            raw_line = response.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            chunks_received += 1
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OllamaError(
                    f"Ollama вернул повреждённый stream chunk: {line[:500]}",
                    telemetry=partial_telemetry(),
                    code="OLLAMA_BAD_STREAM_CHUNK",
                ) from exc

            if not isinstance(chunk, dict):
                continue
            if chunk.get("error"):
                raise OllamaError(
                    f"Ollama stream error: {chunk.get('error')}",
                    telemetry=partial_telemetry(),
                    code="OLLAMA_STREAM_ERROR",
                )

            piece = chunk.get("message", {}).get("content", "")
            if piece:
                content_parts.append(str(piece))

            if chunk.get("done"):
                final_raw = chunk
                break

    except OllamaError:
        raise
    except (socket.timeout, TimeoutError) as exc:
        t = partial_telemetry()
        elapsed = float(t.get("wall_seconds") or 0)
        if elapsed >= total_deadline - 0.05:
            raise OllamaError(
                "OLLAMA_TOTAL_DEADLINE: локальная модель превысила защитный "
                f"лимит {total_deadline} с. Получено chunks={t['chunks_received']}, "
                f"chars={t['partial_output_chars']}, elapsed={t['wall_seconds']} с.",
                telemetry=t,
                code="OLLAMA_TOTAL_DEADLINE",
            ) from exc
        phase = "prefill" if int(t.get("chunks_received") or 0) == 0 else "stream"
        raise OllamaError(
            "OLLAMA_IDLE_TIMEOUT: локальная Ollama перестала отдавать данные "
            f"на фазе {phase}. Получено chunks={t['chunks_received']}, "
            f"chars={t['partial_output_chars']}, elapsed={t['wall_seconds']} с.",
            telemetry=t,
            code="OLLAMA_IDLE_TIMEOUT",
        ) from exc
    except (ConnectionError, OSError, http.client.HTTPException) as exc:
        raise OllamaError(
            f"OLLAMA_CONNECTION_ERROR: локальная Ollama недоступна: {exc}",
            telemetry=partial_telemetry(),
            code="OLLAMA_CONNECTION_ERROR",
        ) from exc
    finally:
        if conn is not None:
            conn.close()

    elapsed = time.perf_counter() - started
    if final_raw is None:
        raise OllamaError(
            "OLLAMA_STREAM_INCOMPLETE: HTTP-поток завершился без финального done-сообщения.",
            telemetry=partial_telemetry(),
            code="OLLAMA_STREAM_INCOMPLETE",
        )

    telemetry = _telemetry_from_raw(
        final_raw,
        wall_seconds=elapsed,
        model_name=model_name,
        has_image=has_image,
        num_ctx=num_ctx,
        num_predict=effective_num_predict,
        custom_output_cap=custom_output_cap,
        chunks_received=chunks_received,
        output_chars=sum(len(x) for x in content_parts),
        total_deadline_seconds=total_deadline,
        idle_timeout_seconds=idle_timeout,
    )

    try:
        log_llm_call(telemetry)
    except Exception:
        pass

    content = "".join(content_parts)
    if not content:
        raise OllamaError(
            f"Ollama вернул пустой content: {final_raw}",
            telemetry=telemetry,
            code="OLLAMA_EMPTY_CONTENT",
        )

    try:
        parsed = json.loads(_strip_json_fence(content))
    except json.JSONDecodeError as exc:
        preview = content[:1600]
        error_telemetry = dict(telemetry)
        error_telemetry["raw_output_length"] = len(content)
        error_telemetry["raw_output_preview"] = content[:4000]
        raise OllamaError(
            f"Модель вернула невалидный JSON: {preview}",
            telemetry=error_telemetry,
            code="OLLAMA_INVALID_JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise OllamaError(
            "Модель должна вернуть JSON-объект.",
            telemetry=telemetry,
            code="OLLAMA_INVALID_JSON_TYPE",
        )

    parsed["_model"] = telemetry["model"]
    parsed["_elapsed_seconds"] = telemetry["wall_seconds"]
    parsed["_ollama_telemetry"] = telemetry
    parsed["_total_duration"] = final_raw.get("total_duration")
    parsed["_eval_count"] = final_raw.get("eval_count")
    return parsed


def ollama_runtime_info(timeout: int = 5) -> dict[str, Any]:
    """Read lightweight Ollama runtime information for debugging local speed."""
    base_url = get_ollama_base_url()
    out: dict[str, Any] = {"base_url": base_url}
    for key, path in (("version", "/api/version"), ("running_models", "/api/ps")):
        try:
            request = urllib.request.Request(f"{base_url}{path}", method="GET")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                out[key] = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            out[key] = {"error": str(exc)}
    return out
