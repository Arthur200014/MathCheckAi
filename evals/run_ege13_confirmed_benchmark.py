"""Benchmark Solver/Grader/Reviewer on human-confirmed EGE-13 transcripts.

This complements run_ege13_benchmark.py:
- raw benchmark starts from the image and therefore includes Vision OCR errors;
- confirmed benchmark skips Vision and uses manual_transcript from the labelled cases.

Only cases with a non-empty manual_transcript are run.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.run_ege13_benchmark import _load_cases, _run_confirmed_pipeline
from src.llm.config import BENCHMARK_VISION_MODELS

DEFAULT_CASES = ROOT / "evals" / "task_13" / "benchmark_cases.json"
DEFAULT_RESULTS = ROOT / "evals" / "results"


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(statistics.mean(values), 4) if values else None


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    return round(sum(bool(row.get(key)) for row in rows) / len(rows), 4)


def _seconds(state: dict[str, Any], name: str) -> float:
    try:
        return round(float(state.get(f"{name}_elapsed_seconds", 0) or 0), 3)
    except (TypeError, ValueError):
        return 0.0


def _run_case(case: dict[str, Any], model: str) -> dict[str, Any]:
    transcript = str(case.get("manual_transcript", "") or "").strip()
    if not transcript:
        return {
            "case_id": case["id"],
            "model": model,
            "expert_score": case.get("expert_score"),
            "ok": False,
            "skipped": True,
            "error": "manual_transcript_missing",
        }

    started = time.perf_counter()
    try:
        result = _run_confirmed_pipeline(case, model, transcript)
        final_score = result.get("final_score")
        expert_score = int(case.get("expert_score", -1))
        score_int = int(final_score) if final_score is not None else None
        manual = bool(result.get("reviewer_manual_review_required", False) or score_int is None)
        return {
            "case_id": case["id"],
            "model": model,
            "expert_score": expert_score,
            "final_score": score_int,
            "score_match": score_int == expert_score if score_int is not None else False,
            "score_abs_error": abs(score_int - expert_score) if score_int is not None else None,
            "ok": score_int is not None,
            "skipped": False,
            "reference_ok": bool(result.get("reference_verification_ok", False)),
            "grader_ok": bool(result.get("grader_ok", False)),
            "reviewer_ok": bool(result.get("reviewer_ok", False)),
            "manual_review": manual,
            "error_class": result.get("reviewer_error_class") or result.get("grader_error_class") or "",
            "solver_seconds": _seconds(result, "solver"),
            "grader_seconds": _seconds(result, "grader"),
            "reviewer_seconds": _seconds(result, "reviewer"),
            "total_seconds": round(time.perf_counter() - started, 3),
            "expert_summary": case.get("expert_summary", ""),
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "error": "",
        }
    except Exception as exc:
        return {
            "case_id": case["id"],
            "model": model,
            "expert_score": case.get("expert_score"),
            "ok": False,
            "skipped": False,
            "total_seconds": round(time.perf_counter() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    used = [row for row in rows if not row.get("skipped")]
    scored = [row for row in used if row.get("final_score") is not None]
    return {
        "cases_with_manual_transcript": len(used),
        "scored_cases": len(scored),
        "score_accuracy": _rate(scored, "score_match"),
        "mean_abs_score_error": _mean(scored, "score_abs_error"),
        "manual_review_rate": _rate(used, "manual_review"),
        "avg_total_seconds": _mean(used, "total_seconds"),
        "avg_solver_seconds": _mean(used, "solver_seconds"),
        "avg_grader_seconds": _mean(used, "grader_seconds"),
        "avg_reviewer_seconds": _mean(used, "reviewer_seconds"),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = [
        "case_id", "model", "expert_score", "final_score", "score_match", "score_abs_error",
        "reference_ok", "grader_ok", "reviewer_ok", "manual_review", "error_class",
        "solver_seconds", "grader_seconds", "reviewer_seconds", "total_seconds", "skipped", "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--models", nargs="*", default=BENCHMARK_VISION_MODELS)
    parser.add_argument("--limit", type=int, default=0, help="0 = все размеченные manual_transcript")
    args = parser.parse_args()

    cases = [case for case in _load_cases(args.cases) if str(case.get("manual_transcript", "") or "").strip()]
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("Нет кейсов с manual_transcript")

    args.results_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    print(f"Human-confirmed кейсов: {len(cases)}; моделей: {len(args.models)}")

    for model in args.models:
        print(f"\n=== {model} ===")
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
            row = _run_case(case, model)
            rows.append(row)
            if row.get("final_score") is not None:
                print(f"score {row['final_score']}/{row['expert_score']}, {row.get('total_seconds', 0):.1f}s")
            else:
                print(f"ERROR: {row.get('error', 'no score')}")

    summaries = {
        model: _summary([row for row in rows if row.get("model") == model])
        for model in args.models
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = args.results_dir / f"ege13-confirmed-benchmark-{stamp}"
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    json_path.write_text(
        json.dumps({"mode": "human_confirmed", "models": args.models, "summaries": summaries, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(csv_path, rows)

    print("\n=== SUMMARY ===")
    for model, summary in summaries.items():
        print(model, json.dumps(summary, ensure_ascii=False))
    print(f"\nJSON: {json_path.relative_to(ROOT)}")
    print(f"CSV:  {csv_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
