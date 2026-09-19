"""Run the same EGE-13 benchmark cases through several local Ollama models.

The benchmark uses expert-labelled cases from benchmark_cases.json. Vision sees
only the cropped handwritten solution. The task equation and interval are fixed
from the expert source so model comparison is not polluted by a leaked printed
answer.

Default models come from src.llm.config.BENCHMARK_VISION_MODELS.

Typical run:
    python evals/prepare_ege13_images.py
    python evals/run_ege13_benchmark.py --limit 3

Final run:
    python evals/run_ege13_benchmark.py

Results are written to evals/results/ as JSON, CSV and Markdown.
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


def _similarity(actual: str, expected: str) -> float | None:
    if not str(expected or "").strip():
        return None
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
        "review_id": f"r-eval-{_slug(str(case['id']))}",
        "trace_id": f"r-eval-{_slug(str(case['id']))}",
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
        "human_confirmation_required": False,
        "human_confirmation_completed": True,
        "transcript_confirmation_source": "eval_ocr",
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
            "case_id": case["id"],
            "model": model,
            "expert_score": case.get("expert_score"),
            "ok": False,
            "error": "missing_images: " + ", ".join(missing),
        }

    started = time.perf_counter()
    try:
        vision = _run_vision(case, model, _image_bytes_for_vision(paths))
        transcript = str(vision.get("transcript", "") or "").strip()
        if not transcript:
            return {
                "case_id": case["id"],
                "model": model,
                "expert_score": case.get("expert_score"),
                "ok": False,
                "vision_ok": False,
                "vision_seconds": _seconds(vision, "vision"),
                "total_seconds": round(time.perf_counter() - started, 3),
                "error": "; ".join(str(x) for x in vision.get("errors", [])) or "empty_vision_transcript",
            }

        result = _run_confirmed_pipeline(case, model, transcript)
        final_score = result.get("final_score")
        expert_score = int(case.get("expert_score", -1))
        score_int = int(final_score) if final_score is not None else None
        manual = bool(result.get("reviewer_manual_review_required", False) or score_int is None)
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
            "reference_ok": bool(result.get("reference_verification_ok", False)),
            "grader_ok": bool(result.get("grader_ok", False)),
            "reviewer_ok": bool(result.get("reviewer_ok", False)),
            "manual_review": manual,
            "error_class": result.get("reviewer_error_class") or result.get("grader_error_class") or "",
            "vision_similarity": _similarity(transcript, str(case.get("manual_transcript", ""))),
            "vision_seconds": _seconds(vision, "vision"),
            "solver_seconds": _seconds(result, "solver"),
            "grader_seconds": _seconds(result, "grader"),
            "reviewer_seconds": _seconds(result, "reviewer"),
            "total_seconds": total,
            "false_error_on_expert_2": bool(expert_score == 2 and (score_int is None or score_int < 2)),
            "positive_score_on_expert_0": bool(expert_score == 0 and score_int is not None and score_int > 0),
            "transcript": transcript,
            "expert_summary": case.get("expert_summary", ""),
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "error": "",
        }
    except Exception as exc:  # benchmark must continue to the next case/model
        return {
            "case_id": case["id"],
            "model": model,
            "expert_score": case.get("expert_score"),
            "ok": False,
            "total_seconds": round(time.perf_counter() - started, 3),
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
    ocr_rows = [row for row in rows if row.get("vision_similarity") is not None]
    return {
        "cases": len(rows),
        "scored_cases": len(scored),
        "score_accuracy": _rate(scored, "score_match"),
        "mean_abs_score_error": _mean(scored, "score_abs_error"),
        "vision_success_rate": _rate(rows, "vision_ok"),
        "reference_success_rate": _rate(rows, "reference_ok"),
        "manual_review_rate": _rate(rows, "manual_review"),
        "mean_vision_similarity": _mean(ocr_rows, "vision_similarity"),
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
        "vision_ok", "reference_ok", "grader_ok", "reviewer_ok", "manual_review", "error_class",
        "vision_similarity", "vision_seconds", "solver_seconds", "grader_seconds", "reviewer_seconds",
        "total_seconds", "false_error_on_expert_2", "positive_score_on_expert_0", "error",
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
        "Score accuracy is exact agreement with the expert score (0/1/2).",
        "`false_error_rate_on_expert_2` is a conservative hallucination proxy: an expert-perfect work received less than 2.",
        "OCR similarity is shown only for cases where `manual_transcript` is filled in benchmark_cases.json.",
        "",
        "| Model | Cases | Score accuracy | Mean abs error | Manual review | OCR similarity | Avg total, s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, summary in summaries.items():
        lines.append(
            "| " + " | ".join(
                [
                    model,
                    _fmt(summary.get("cases")),
                    _fmt(summary.get("score_accuracy")),
                    _fmt(summary.get("mean_abs_score_error")),
                    _fmt(summary.get("manual_review_rate")),
                    _fmt(summary.get("mean_vision_similarity")),
                    _fmt(summary.get("avg_total_seconds")),
                ]
            ) + " |"
        )
    lines.append("")
    lines.append("Full machine-readable metrics are in the matching JSON file.")
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
    if not args.models:
        raise SystemExit("Не указаны модели")

    args.results_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    print(f"Кейсов: {len(cases)}; моделей: {len(args.models)}")

    for model in args.models:
        print(f"\n=== {model} ===")
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
            row = _run_case(case, model, args.data_dir)
            rows.append(row)
            if row.get("final_score") is not None:
                print(f"score {row['final_score']}/{row['expert_score']}, {row.get('total_seconds', 0):.1f}s")
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
        json.dumps({"models": args.models, "summaries": summaries, "rows": rows}, ensure_ascii=False, indent=2),
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
