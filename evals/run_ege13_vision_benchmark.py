"""Run only the Vision part of the EGE-13 benchmark.

Use this after the human-confirmed grading-system benchmark has already been run.
It reuses the same cases, image preflight, OCR metric and Vision runner as the
main benchmark, but does not call Solver, Grader or Reviewer.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.run_ege13_benchmark import (
    DEFAULT_CASES,
    DEFAULT_DATA,
    DEFAULT_RESULTS,
    _load_cases,
    _preflight_images,
    _run_vision_case,
    _validate_ground_truth,
    _vision_summary,
    _write_csv,
)
from src.llm.config import BENCHMARK_VISION_MODELS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--models", nargs="*", default=BENCHMARK_VISION_MODELS)
    parser.add_argument("--limit", type=int, default=0, help="0 = все кейсы")
    parser.add_argument("--case-id", action="append", default=[], help="запустить только указанный id; можно повторить")
    args = parser.parse_args()

    cases = _load_cases(args.cases)
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if str(case.get("id")) in wanted]
        missing_ids = wanted - {str(case.get("id")) for case in cases}
        if missing_ids:
            raise SystemExit("Не найдены case id: " + ", ".join(sorted(missing_ids)))
    if args.limit > 0:
        cases = cases[: args.limit]

    _validate_ground_truth(cases)
    if not args.models:
        raise SystemExit("Не указаны Vision models")
    _preflight_images(cases, args.data_dir)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    print(f"Кейсов: {len(cases)}")
    print("VISION-only benchmark: photo -> OCR; Solver/Grader/Reviewer are not run")

    for model in args.models:
        print(f"\n=== VISION {model} ===")
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
            row = _run_vision_case(case, model, args.data_dir)
            rows.append(row)
            similarity = row.get("vision_similarity")
            ocr_text = f"{similarity:.3f}" if isinstance(similarity, (int, float)) else "FAIL"
            if row.get("vision_ok"):
                print(f"ocr={ocr_text}, {row.get('total_seconds', 0):.1f}s")
            else:
                print(
                    f"VISION FAIL, ocr={ocr_text}, {row.get('total_seconds', 0):.1f}s: "
                    f"{row.get('error', '')}"
                )

    summaries = {
        model: _vision_summary([row for row in rows if row.get("model") == model])
        for model in args.models
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = args.results_dir / f"ege13-vision-benchmark-{stamp}"
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    md_path = base.with_suffix(".md")

    json_path.write_text(
        json.dumps(
            {
                "method": "Vision-only: photo -> OCR; downstream grading excluded",
                "vision_models": args.models,
                "vision_summaries": summaries,
                "vision_rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_csv(csv_path, rows)

    lines = [
        "# EGE-13 Vision benchmark",
        "",
        "Photo OCR only. Solver, Grader and Reviewer are not run.",
        "",
        "| Model | Cases | Vision success | Valid JSON | OCR similarity | Human correction | Avg Vision, s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, summary in summaries.items():
        lines.append(
            "| "
            + " | ".join(
                [
                    model,
                    str(summary.get("cases")),
                    str(summary.get("vision_success_rate")),
                    str(summary.get("valid_json_rate")),
                    str(summary.get("mean_vision_similarity")),
                    str(summary.get("human_correction_rate")),
                    str(summary.get("avg_vision_seconds")),
                ]
            )
            + " |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== VISION SUMMARY ===")
    for model, summary in summaries.items():
        print(model, json.dumps(summary, ensure_ascii=False))
    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
