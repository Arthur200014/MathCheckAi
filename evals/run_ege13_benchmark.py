"""Benchmark MathCheck AI on expert-labelled EGE-13 works.

The primary benchmark follows the real product flow:
1) Vision reads the photo;
2) raw OCR is compared with a human-checked transcript;
3) the human-checked transcript is used as the confirmed editor value;
4) Solver -> deterministic reference verifier -> Grader -> Reviewer;
5) final score is compared with the expert score.

Human editing time is intentionally not included in latency: we compare model/tool
runtime, while still keeping the mandatory human-confirmation boundary.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.grader import grader_agent
from src.agents.reference_verifier import reference_verifier_agent
from src.agents.reviewer import reviewer_agent
from src.agents.solver import solver_agent
from src.agents.vision import vision_agent
from src.llm.config import BENCHMARK_VISION_MODELS
from src.multi_photo_api import _stitch_pages
from src.task_registry import load_task_profile_node
from src.tools.display_math import latex_to_human_text
from src.tools.ege13_task_input import build_ege13_task_statement

DEFAULT_CASES = ROOT / "evals" / "task_13" / "benchmark_cases.json"
DEFAULT_DATA = ROOT / "local_eval_data"
DEFAULT_RESULTS = ROOT / "evals" / "results"
MODEL_ENV_KEYS = (
    "OLLAMA_VISION_MODEL",
    "OLLAMA_SOLVER_MODEL",
    "OLLAMA_GRADER_MODEL",
    "OLLAMA_REVIEWER_MODEL",
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_") or "model"


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"В {path} нет benchmark cases")
    return cases


def _validate_ground_truth(cases: list[dict[str, Any]]) -> None:
    missing: list[str] = []
    for case in cases:
        if not str(case.get("manual_transcript", "") or "").strip():
            missing.append(f"{case.get('id')}: manual_transcript")
        if case.get("expert_score") not in (0, 1, 2):
            missing.append(f"{case.get('id')}: expert_score")
        if not isinstance(case.get("expected_key_points"), list):
            missing.append(f"{case.get('id')}: expected_key_points")
        if not isinstance(case.get("expected_errors"), list):
            missing.append(f"{case.get('id')}: expected_errors")
    if missing:
        raise SystemExit("Ground truth не заполнен полностью:\n- " + "\n- ".join(missing))


def _case_image_paths(case: dict[str, Any], data_dir: Path) -> list[Path]:
    count = len(case.get("pages", []))
    return [data_dir / f"{case['id']}_p{i}.png" for i in range(1, count + 1)]


def _image_bytes_for_vision(paths: list[Path]) -> bytes:
    raw = [path.read_bytes() for path in paths]
    if len(raw) == 1:
        return raw[0]
    stitched, _ = _stitch_pages(raw)
    return stitched


def _normalize_text(value: str) -> str:
    text = latex_to_human_text(str(value or ""))
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("−", "-").replace("·", "*")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _similarity(actual: str, expected: str) -> float:
    return round(SequenceMatcher(None, _normalize_text(actual), _normalize_text(expected)).ratio(), 4)


@contextmanager
def _model_for_all_agents(model: str):
    old = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ[key] = model
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_vision(case: dict[str, Any], model: str, image_bytes: bytes) -> dict[str, Any]:
    state = {
        "review_id": f"r-eval-vision-{_slug(str(case['id']))}-{_slug(model)}",
        "trace_id": f"r-eval-vision-{_slug(str(case['id']))}-{_slug(model)}",
        "student_id": "eval",
        "task_type": "ege_13",
        "task_statement": "",
        "image_b64": base64.b64encode(image_bytes).decode("ascii"),
        "human_confirmation_required": True,
        "human_confirmation_completed": False,
        "errors": [],
        "warnings": [],
    }
    with _model_for_all_agents(model):
        return vision_agent(state)


def _run_confirmed_pipeline(case: dict[str, Any], model: str, transcript: str) -> dict[str, Any]:
    equation = str(case.get("task_equation", "")).strip()
    interval = str(case.get("interval", "")).strip()
    state: dict[str, Any] = {
        "review_id": f"r-eval-{_slug(str(case['id']))}-{_slug(model)}",
        "trace_id": f"r-eval-{_slug(str(case['id']))}-{_slug(model)}",
        "student_id": "eval",
        "task_type": "ege_13",
        "task_statement": build_ege13_task_statement(equation, interval),
        "confirmed_task_statement": build_ege13_task_statement(equation, interval),
        "confirmed_task_equation": equation,
        "confirmed_interval": interval,
        "original_transcript": transcript,
        "confirmed_transcript": transcript,
        "transcript": transcript,
        "transcript_confirmed": True,
        "human_confirmation_required": True,
        "human_confirmation_completed": True,
        "transcript_confirmation_source": "eval_human_ground_truth",
        "errors": [],
        "warnings": [],
    }

    with _model_for_all_agents(model):
        state.update(load_task_profile_node(state))
        if not state.get("task_profile_ok"):
            return state
        state.update(solver_agent(state))
        state.update(reference_verifier_agent(state))
        if state.get("reference_verification_ok"):
            state.update(grader_agent(state))
        state.update(reviewer_agent(state))
    return state


def _seconds(state: dict[str, Any], name: str) -> float:
    try:
        return round(float(state.get(f"{name}_elapsed_seconds", 0) or 0), 3)
    except (TypeError, ValueError):
        return 0.0


def _run_case(case: dict[str, Any], model: str, data_dir: Path) -> dict[str, Any]:
    paths = _case_image_paths(case, data_dir)
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        return {
            "case_id": case["id"], "model": model, "expert_score": case.get("expert_score"),
            "ok": False, "error": "missing_images: " + ", ".join(missing),
        }

    manual_transcript = str(case.get("manual_transcript", "") or "").strip()
    started = time.perf_counter()
    try:
        vision = _run_vision(case, model, _image_bytes_for_vision(paths))
        vision_transcript = str(vision.get("transcript", "") or "").strip()
        if not vision_transcript:
            return {
                "case_id": case["id"], "model": model, "expert_score": case.get("expert_score"),
                "ok": False, "vision_ok": False, "vision_seconds": _seconds(vision, "vision"),
                "total_seconds": round(time.perf_counter() - started, 3),
                "error": "; ".join(str(x) for x in vision.get("errors", [])) or "empty_vision_transcript",
            }

        confirmed_transcript = manual_transcript
        similarity = _similarity(vision_transcript, manual_transcript)
        human_edit_required = _normalize_text(vision_transcript) != _normalize_text(manual_transcript)

        result = _run_confirmed_pipeline(case, model, confirmed_transcript)
        final_score = result.get("final_score")
        expert_score = int(case.get("expert_score", -1))
        score_int = int(final_score) if final_score is not None else None
        manual_review = bool(result.get("reviewer_manual_review_required", False) or score_int is None)
        expected_manual_review = bool(case.get("expected_manual_review", False))
        total = round(time.perf_counter() - started, 3)

        return {
            "case_id": case["id"],
            "model": model,
            "expert_score": expert_score,
            "final_score": score_int,
            "score_match": score_int == expert_score if score_int is not None else False,
            "score_abs_error": abs(score_int - expert_score) if score_int is not None else None,
            "ok": score_int is not None,
            "vision_ok": not bool(vision.get("errors")),
            "vision_similarity": similarity,
            "human_edit_required": human_edit_required,
            "reference_ok": bool(result.get("reference_verification_ok", False)),
            "grader_ok": bool(result.get("grader_ok", False)),
            "reviewer_ok": bool(result.get("reviewer_ok", False)),
            "manual_review": manual_review,
            "expected_manual_review": expected_manual_review,
            "manual_review_match": manual_review == expected_manual_review,
            "error_class": result.get("reviewer_error_class") or result.get("grader_error_class") or "",
            "vision_seconds": _seconds(vision, "vision"),
            "solver_seconds": _seconds(result, "solver"),
            "grader_seconds": _seconds(result, "grader"),
            "reviewer_seconds": _seconds(result, "reviewer"),
            "total_seconds": total,
            "false_error_on_expert_2": bool(expert_score == 2 and (score_int is None or score_int < 2)),
            "positive_score_on_expert_0": bool(expert_score == 0 and score_int is not None and score_int > 0),
            "vision_transcript": vision_transcript,
            "confirmed_transcript": confirmed_transcript,
            "expected_key_points": case.get("expected_key_points", []),
            "expected_errors": case.get("expected_errors", []),
            "expert_summary": case.get("expert_summary", ""),
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "error": "",
        }
    except Exception as exc:
        return {
            "case_id": case["id"], "model": model, "expert_score": case.get("expert_score"),
            "ok": False, "total_seconds": round(time.perf_counter() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(statistics.mean(values), 4) if values else None


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    return round(sum(bool(row.get(key)) for row in rows) / len(rows), 4)


def _summary_for_model(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row.get("final_score") is not None]
    score2 = [row for row in rows if row.get("expert_score") == 2]
    score0 = [row for row in rows if row.get("expert_score") == 0]
    return {
        "cases": len(rows),
        "scored_cases": len(scored),
        "score_accuracy": _rate(scored, "score_match"),
        "mean_abs_score_error": _mean(scored, "score_abs_error"),
        "vision_success_rate": _rate(rows, "vision_ok"),
        "mean_vision_similarity": _mean(rows, "vision_similarity"),
        "human_correction_rate": _rate(rows, "human_edit_required"),
        "reference_success_rate": _rate(rows, "reference_ok"),
        "manual_review_rate": _rate(rows, "manual_review"),
        "manual_review_match_rate": _rate(rows, "manual_review_match"),
        "false_error_rate_on_expert_2": _rate(score2, "false_error_on_expert_2"),
        "positive_score_rate_on_expert_0": _rate(score0, "positive_score_on_expert_0"),
        "avg_total_seconds": _mean(rows, "total_seconds"),
        "avg_vision_seconds": _mean(rows, "vision_seconds"),
        "avg_solver_seconds": _mean(rows, "solver_seconds"),
        "avg_grader_seconds": _mean(rows, "grader_seconds"),
        "avg_reviewer_seconds": _mean(rows, "reviewer_seconds"),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = [
        "case_id", "model", "expert_score", "final_score", "score_match", "score_abs_error",
        "vision_ok", "vision_similarity", "human_edit_required", "reference_ok", "grader_ok",
        "reviewer_ok", "manual_review", "expected_manual_review", "manual_review_match", "error_class",
        "vision_seconds", "solver_seconds", "grader_seconds", "reviewer_seconds", "total_seconds",
        "false_error_on_expert_2", "positive_score_on_expert_0", "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _write_markdown(path: Path, summaries: dict[str, dict[str, Any]]) -> None:
    lines = [
        "# EGE-13 model benchmark",
        "",
        "Primary flow: photo -> Vision measurement -> human-confirmed transcript -> Solver -> verifier -> Grader -> Reviewer.",
        "Human editing time is excluded from latency; model/tool runtime is included.",
        "",
        "| Model | Cases | OCR similarity | Human correction | Score accuracy | Manual-review match | Avg total, s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, summary in summaries.items():
        lines.append(
            "| " + " | ".join([
                model,
                _fmt(summary.get("cases")),
                _fmt(summary.get("mean_vision_similarity")),
                _fmt(summary.get("human_correction_rate")),
                _fmt(summary.get("score_accuracy")),
                _fmt(summary.get("manual_review_match_rate")),
                _fmt(summary.get("avg_total_seconds")),
            ]) + " |"
        )
    lines.append("")
    lines.append("Full per-case data, raw Vision text and confirmed transcripts are in the matching JSON file.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--models", nargs="*", default=BENCHMARK_VISION_MODELS)
    parser.add_argument("--limit", type=int, default=0, help="0 = все кейсы")
    args = parser.parse_args()

    cases = _load_cases(args.cases)
    if args.limit > 0:
        cases = cases[: args.limit]
    _validate_ground_truth(cases)
    if not args.models:
        raise SystemExit("Не указаны модели")

    args.results_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    print(f"Кейсов: {len(cases)}; моделей: {len(args.models)}")
    print("Flow: Vision -> human confirmation (ground truth) -> Solver -> verifier -> Grader -> Reviewer")

    for model in args.models:
        print(f"\n=== {model} ===")
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
            row = _run_case(case, model, args.data_dir)
            rows.append(row)
            if row.get("final_score") is not None:
                print(
                    f"score {row['final_score']}/{row['expert_score']}, "
                    f"ocr={row.get('vision_similarity', 0):.3f}, {row.get('total_seconds', 0):.1f}s"
                )
            else:
                print(f"ERROR: {row.get('error', 'no score')}")

    summaries = {
        model: _summary_for_model([row for row in rows if row.get("model") == model])
        for model in args.models
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = args.results_dir / f"ege13-benchmark-{stamp}"
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    md_path = base.with_suffix(".md")

    json_path.write_text(
        json.dumps({
            "method": "photo -> Vision metric -> human-confirmed ground truth -> downstream agents",
            "models": args.models,
            "summaries": summaries,
            "rows": rows,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(csv_path, rows)
    _write_markdown(md_path, summaries)

    print("\n=== SUMMARY ===")
    for model, summary in summaries.items():
        print(model, json.dumps(summary, ensure_ascii=False))
    print(f"\nJSON: {json_path.relative_to(ROOT)}")
    print(f"CSV:  {csv_path.relative_to(ROOT)}")
    print(f"MD:   {md_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
