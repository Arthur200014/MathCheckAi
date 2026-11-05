"""Synthetic telemetry for monitoring demonstrations (never grades student work).

Examples:
  python -m scripts.demo_observability
  python -m scripts.demo_observability --runs 30 --delay 0.12
  python -m scripts.demo_observability --runs 30 --with-error
"""
from __future__ import annotations

import argparse
import os
import time
from uuid import uuid4

from fastapi import FastAPI
from opentelemetry import trace

from src.observability.otel import (
    configure_otel,
    emit_event,
    flush_telemetry,
    record_demo_review,
    record_stage_completion,
    stage_span,
)

STAGES = (
    "vision", "solver", "verify_reference", "grader",
    "reviewer", "build_report", "persist_review",
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Send real OTLP metrics, logs and traces using synthetic stages."
    )
    parser.add_argument(
        "--with-error", action="store_true",
        help="Also generate one intentional error in the LAST demonstration run.",
    )
    parser.add_argument(
        "--runs", type=int, default=1, metavar="N",
        help="Number of synthetic reviews (default 1, max 200).",
    )
    parser.add_argument(
        "--delay", type=float, default=0.12, metavar="SECONDS",
        help="Approximate duration of a simulated stage (default 0.12 seconds).",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.runs <= 200:
        parser.error("--runs must be from 1 to 200")
    if not 0 <= args.delay <= 2:
        parser.error("--delay must be from 0 to 2 seconds")
    if os.getenv("MATHCHECK_OTEL_ENABLED", "").lower() not in {"true", "1", "yes", "on"}:
        raise SystemExit("MATHCHECK_OTEL_ENABLED must be true")
    if not configure_otel(FastAPI()):
        raise SystemExit("OpenTelemetry instrumentation did not start")

    latest_id = ""
    for index in range(args.runs):
        review_id = f"demo-{uuid4().hex[:8]}"
        latest_id = review_id
        intentional_failure = args.with_error and index == args.runs - 1
        with trace.get_tracer("mathcheck.demo").start_as_current_span("demo.review") as root:
            root.set_attribute("mathcheck.demo", True)
            root.set_attribute(
                "mathcheck.demo.mode", "with_error" if intentional_failure else "success"
            )
            root.set_attribute("mathcheck.review_id", review_id)
            for stage_index, real_stage in enumerate(STAGES):
                # Preserve a demo_ prefix so no one mistakes synthetic observations
                # for real model processing or real completed reviews.
                stage = f"demo_{real_stage}"
                started = time.perf_counter()
                with stage_span(stage=stage, review_id=review_id):
                    emit_event("demo.stage.started", status="started", stage=stage, review_id=review_id)
                    multiplier = 0.7 + ((index + stage_index) % 5) * 0.15
                    time.sleep(args.delay * multiplier)
                    emit_event("demo.stage.finished", status="done", stage=stage, review_id=review_id)
                record_stage_completion(
                    stage=stage, status="done", duration=time.perf_counter() - started
                )

            if intentional_failure:
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

        record_demo_review(with_error=intentional_failure)
        if args.runs > 1 and ((index + 1) % 5 == 0 or index == args.runs - 1):
            print(f"Demo reviews: {index + 1}/{args.runs}", flush=True)

    flush_telemetry()
    print(
        f"Synthetic telemetry exported. mode={'with_error' if args.with_error else 'success'} "
        f"review_id={latest_id} runs={args.runs} "
        f"(no real student reviews were created)"
    )


if __name__ == "__main__":
    main()
