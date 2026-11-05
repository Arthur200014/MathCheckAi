"""Generate explicitly synthetic observability signals without loading Ollama.

Usage:
    docker compose exec mathcheck python -m scripts.demo_observability
    docker compose exec mathcheck python -m scripts.demo_observability --with-error
"""
from __future__ import annotations

import argparse
import os
import time
from uuid import uuid4

from fastapi import FastAPI
from opentelemetry import trace

from src.observability.otel import (
    configure_otel, emit_event, flush_telemetry, record_stage_completion, stage_span,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Send synthetic MathCheckAi spans, metrics, and logs. "
                    "Only --with-error creates an artificial failure."
    )
    parser.add_argument(
        "--with-error", action="store_true",
        help="Additionally produce one intentional error span for teaching purposes.",
    )
    args = parser.parse_args(argv)
    if os.getenv("MATHCHECK_OTEL_ENABLED", "").lower() not in {"true", "1", "yes", "on"}:
        raise SystemExit("MATHCHECK_OTEL_ENABLED must be true")
    configure_otel(FastAPI())
    review_id = f"demo-{uuid4().hex[:8]}"
    with trace.get_tracer("mathcheck.demo").start_as_current_span("demo.review") as root:
        root.set_attribute("mathcheck.demo", True)
        root.set_attribute("mathcheck.demo.mode", "with_error" if args.with_error else "success")
        root.set_attribute("mathcheck.review_id", review_id)
        for real_stage in ("vision", "solver", "verify_reference", "grader", "reviewer", "build_report", "persist_review"):
            # Prefix all synthetic metric labels so dashboard counts stay distinguishable.
            stage = f"demo_{real_stage}"
            started = time.perf_counter()
            with stage_span(stage=stage, review_id=review_id):
                emit_event("demo.stage.started", status="started", stage=stage, review_id=review_id)
                time.sleep(0.12)
                emit_event("demo.stage.finished", status="done", stage=stage, review_id=review_id)
            record_stage_completion(stage=stage, status="done", duration=time.perf_counter() - started)

        if args.with_error:
            # Intentional failure is opt-in. Never mark ordinary demo runs as erroneous.
            started = time.perf_counter()
            try:
                with stage_span(stage="demo_failure", review_id=review_id):
                    emit_event(
                        "demo.failure", status="error", stage="demo_failure", review_id=review_id,
                    )
                    raise RuntimeError("intentional synthetic failure")
            except RuntimeError:
                record_stage_completion(
                    stage="demo_failure", status="error",
                    duration=time.perf_counter() - started,
                )

    flush_telemetry()
    print(
        f"Synthetic telemetry exported. mode={'with_error' if args.with_error else 'success'} "
        f"review_id={review_id} (not a real student review)"
    )


if __name__ == "__main__":
    main()
