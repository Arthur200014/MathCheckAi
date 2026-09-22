















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
from src.llm.config import BENCHMARK_VISION_MODELS, get_solver_model
from src.multi_photo_api import _stitch_pages
from src.task_registry import load_task_profile_node
from src.tools.display_math import latex_to_human_text
from src.tools.ege13_task_input import build_ege13_task_statement

DEFAULT_CASES = ROOT / "evals" / "task_13" / "benchmark_cases.json"
DEFAULT_DATA = ROOT / "local_eval_data"
DEFAULT_RESULTS = ROOT / "evals" / "results"
SYSTEM_ENV_KEYS = (
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
        cid = case.get("id")
        if not str(case.get("manual_transcript", "") or "").strip():
            missing.append(f"{cid}: manual_transcript")
        if case.get("expert_score") not in (0, 1, 2):
            missing.append(f"{cid}: expert_score")
        if not isinstance(case.get("expected_key_points"), list):
            missing.append(f"{cid}: expected_key_points")
        if not isinstance(case.get("expected_errors"), list):
            missing.append(f"{cid}: expected_errors")
        if not isinstance(case.get("expected_manual_review"), bool):
            missing.append(f"{cid}: expected_manual_review")
        if not str(case.get("task_equation", "") or "").strip():
            missing.append(f"{cid}: task_equation")
        if not str(case.get("interval", "") or "").strip():
            missing.append(f"{cid}: interval")
        if not case.get("pages"):
            missing.append(f"{cid}: pages")
    if missing:
        raise SystemExit("Ground truth не заполнен полностью:\n- " + "\n- ".join(missing))


def _case_image_paths(case: dict[str, Any], data_dir: Path) -> list[Path]:
    count = len(case.get("pages", []))
    return [data_dir / f"{case['id']}_p{i}.png" for i in range(1, count + 1)]


def _preflight_images(cases: list[dict[str, Any]], data_dir: Path) -> None:

    missing: list[str] = []
    for case in cases:
        for path in _case_image_paths(case, data_dir):
            if not path.exists():
                missing.append(str(path))
    if missing:
        joined = "\n- ".join(missing)
        raise SystemExit(
            "Benchmark images are incomplete. Run `python evals/prepare_ege13_images.py` first.\n- " + joined
        )


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
def _vision_model(model: str):
    old = os.environ.get("OLLAMA_VISION_MODEL")
    try:
        os.environ["OLLAMA_VISION_MODEL"] = model
        yield
    finally:
        if old is None:
            os.environ.pop("OLLAMA_VISION_MODEL", None)
        else:
            os.environ["OLLAMA_VISION_MODEL"] = old


@contextmanager
def _system_model(model: str):
    old = {key: os.environ.get(key) for key in SYSTEM_ENV_KEYS}
    try:
        for key in SYSTEM_ENV_KEYS:
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
    with _vision_model(model):
        return vision_agent(state)


def _run_confirmed_pipeline(case: dict[str, Any], model: str, transcript: str) -> dict[str, Any]:

    equation = str(case.get("task_equation", "")).strip()
    interval = str(case.get("interval", "")).strip()
    statement = build_ege13_task_statement(equation, interval)
    state: dict[str, Any] = {
        "review_id": f"r-eval-system-{_slug(str(case['id']))}-{_slug(model)}",
        "trace_id": f"r-eval-system-{_slug(str(case['id']))}-{_slug(model)}",
        "student_id": "eval",
        "task_type": "ege_13",
        "task_statement": statement,
        "confirmed_task_statement": statement,
        "confirmed_task_equation": equation,
        "confirmed_interval": interval,
        "original_transcript": transcript,
        "confirmed_transcript": transcript,
        "transcript": transcript,
        "transcript_confirmed": True,
        "human_confirmation_required": True,
        "human_confirmation_completed": True,
        "transcript_confirmation_source": "eval_human_ground_truth",
                                                                           
                                                                             
                                                                               
        "image_b64": "",
        "errors": [],
        "warnings": [],
    }

    with _system_model(model):
        state.update(load_task_profile_node(state))
        if not state.get("task_profile_ok"):
            return state

        t = time.perf_counter()
        state.update(solver_agent(state))
        state.setdefault("solver_elapsed_seconds", round(time.perf_counter() - t, 3))

        t = time.perf_counter()
        state.update(reference_verifier_agent(state))
        state["reference_elapsed_seconds"] = round(time.perf_counter() - t, 3)
        state["diagram_elapsed_seconds"] = 0.0
        state["diagram_verification_status"] = "IGNORED_BY_MVP"
        state["diagram_part_b_valid"] = None
        state["diagram_method_used"] = False

        if state.get("reference_verification_ok"):
            t = time.perf_counter()
            state.update(grader_agent(state))
            state.setdefault("grader_elapsed_seconds", round(time.perf_counter() - t, 3))

        t = time.perf_counter()
        state.update(reviewer_agent(state))
        state.setdefault("reviewer_elapsed_seconds", round(time.perf_counter() - t, 3))
    return state


def _seconds(state: dict[str, Any], name: str) -> float:
    try:
        return round(float(state.get(f"{name}_elapsed_seconds", 0) or 0), 3)
    except (TypeError, ValueError):
        return 0.0


def _run_vision_case(case: dict[str, Any], model: str, data_dir: Path) -> dict[str, Any]:
    paths = _case_image_paths(case, data_dir)
    image_bytes = _image_bytes_for_vision(paths)
    manual_transcript = str(case.get("manual_transcript", "") or "").strip()
    started = time.perf_counter()

    try:
        vision = _run_vision(case, model, image_bytes)
        vision_transcript = str(vision.get("transcript", "") or "").strip()
        errors = [str(x) for x in vision.get("errors", []) if str(x)]
        vision_ok = bool(vision_transcript) and not errors
        similarity = _similarity(vision_transcript, manual_transcript) if vision_transcript else None
        return {
            "row_type": "vision",
            "case_id": case["id"],
            "model": model,
            "expert_score": case.get("expert_score"),
            "vision_ok": vision_ok,
            "vision_similarity": similarity,
            "human_edit_required": (
                True if not vision_transcript
                else _normalize_text(vision_transcript) != _normalize_text(manual_transcript)
            ),
            "vision_seconds": _seconds(vision, "vision"),
            "total_seconds": round(time.perf_counter() - started, 3),
            "vision_transcript": vision_transcript,
            "confirmed_transcript": manual_transcript,
            "error": "; ".join(errors) if errors else ("" if vision_transcript else "empty_vision_transcript"),
        }
    except Exception as exc:
        return {
            "row_type": "vision",
            "case_id": case["id"],
            "model": model,
            "expert_score": case.get("expert_score"),
            "vision_ok": False,
            "vision_similarity": None,
            "human_edit_required": True,
            "vision_seconds": 0.0,
            "total_seconds": round(time.perf_counter() - started, 3),
            "vision_transcript": "",
            "confirmed_transcript": manual_transcript,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_system_case(case: dict[str, Any], model: str) -> dict[str, Any]:
    transcript = str(case.get("manual_transcript", "") or "").strip()
    started = time.perf_counter()
    try:
        result = _run_confirmed_pipeline(case, model, transcript)
        final_score = result.get("final_score")
        expert_score = int(case.get("expert_score", -1))
        score_int = int(final_score) if final_score is not None else None
        manual_review = bool(result.get("reviewer_manual_review_required", False) or score_int is None)
        expected_manual_review = bool(case.get("expected_manual_review", False))
        return {
            "row_type": "system",
            "case_id": case["id"],
            "model": model,
            "expert_score": expert_score,
            "final_score": score_int,
            "score_match": score_int == expert_score if score_int is not None else False,
            "score_abs_error": abs(score_int - expert_score) if score_int is not None else None,
            "reference_ok": bool(result.get("reference_verification_ok", False)),
            "diagram_used": False,
            "diagram_status": "IGNORED_BY_MVP",
            "diagram_valid": None,
            "grader_ok": bool(result.get("grader_ok", False)),
            "reviewer_ok": bool(result.get("reviewer_ok", False)),
            "manual_review": manual_review,
            "expected_manual_review": expected_manual_review,
            "manual_review_match": manual_review == expected_manual_review,
            "error_class": result.get("reviewer_error_class") or result.get("grader_error_class") or "",
            "solver_seconds": _seconds(result, "solver"),
            "reference_seconds": _seconds(result, "reference"),
            "diagram_seconds": 0.0,
            "grader_seconds": _seconds(result, "grader"),
            "reviewer_seconds": _seconds(result, "reviewer"),
            "total_seconds": round(time.perf_counter() - started, 3),
            "false_error_on_expert_2": bool(expert_score == 2 and (score_int is None or score_int < 2)),
            "positive_score_on_expert_0": bool(expert_score == 0 and score_int is not None and score_int > 0),
            "confirmed_transcript": transcript,
            "expected_key_points": case.get("expected_key_points", []),
            "expected_errors": case.get("expected_errors", []),
            "expert_summary": case.get("expert_summary", ""),
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "error": "" if score_int is not None else "downstream_no_score",
        }
    except Exception as exc:
        return {
            "row_type": "system",
            "case_id": case["id"],
            "model": model,
            "expert_score": case.get("expert_score"),
            "final_score": None,
            "total_seconds": round(time.perf_counter() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_case(case: dict[str, Any], model: str, data_dir: Path) -> dict[str, Any]:





    vision_row = _run_vision_case(case, model, data_dir)
    system_row = _run_system_case(case, get_solver_model())
    return {**vision_row, **system_row, "model": model, "vision_ok": vision_row.get("vision_ok"),
            "vision_similarity": vision_row.get("vision_similarity"),
            "human_edit_required": vision_row.get("human_edit_required"),
            "vision_seconds": vision_row.get("vision_seconds"),
            "vision_transcript": vision_row.get("vision_transcript", ""),
            "confirmed_transcript": str(case.get("manual_transcript", "") or "").strip()}


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(statistics.mean(values), 4) if values else None


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    return round(sum(bool(row.get(key)) for row in rows) / len(rows), 4)


def _vision_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row.get("vision_ok")]
    return {
        "cases": len(rows),
        "vision_success_rate": _rate(rows, "vision_ok"),
        "valid_json_rate": _rate(rows, "vision_ok"),
        "mean_vision_similarity": _mean(ok_rows, "vision_similarity"),
        "human_correction_rate": _rate(rows, "human_edit_required"),
        "avg_vision_seconds": _mean(rows, "vision_seconds"),
        "avg_total_seconds": _mean(rows, "total_seconds"),
    }


def _system_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row.get("final_score") is not None]
    score2 = [row for row in rows if row.get("expert_score") == 2]
    score0 = [row for row in rows if row.get("expert_score") == 0]
    return {
        "cases": len(rows),
        "scored_cases": len(scored),
        "score_accuracy": _rate(scored, "score_match"),
        "mean_abs_score_error": _mean(scored, "score_abs_error"),
        "reference_success_rate": _rate(rows, "reference_ok"),
        "manual_review_rate": _rate(rows, "manual_review"),
        "manual_review_match_rate": _rate(rows, "manual_review_match"),
        "false_error_rate_on_expert_2": _rate(score2, "false_error_on_expert_2"),
        "positive_score_rate_on_expert_0": _rate(score0, "positive_score_on_expert_0"),
        "avg_total_seconds": _mean(rows, "total_seconds"),
        "avg_solver_seconds": _mean(rows, "solver_seconds"),
        "avg_reference_seconds": _mean(rows, "reference_seconds"),
        "avg_diagram_seconds": 0.0,
        "avg_grader_seconds": _mean(rows, "grader_seconds"),
        "avg_reviewer_seconds": _mean(rows, "reviewer_seconds"),
    }


def _summary_for_model(rows: list[dict[str, Any]]) -> dict[str, Any]:

    return _vision_summary(rows) if rows and rows[0].get("row_type") == "vision" else _system_summary(rows)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = [
        "row_type", "case_id", "model", "expert_score", "final_score", "score_match", "score_abs_error",
        "vision_ok", "vision_similarity", "human_edit_required", "reference_ok", "diagram_used",
        "diagram_status", "diagram_valid", "grader_ok", "reviewer_ok", "manual_review",
        "expected_manual_review", "manual_review_match", "error_class", "vision_seconds",
        "solver_seconds", "reference_seconds", "diagram_seconds", "grader_seconds", "reviewer_seconds",
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


def _write_markdown(
    path: Path,
    vision_summaries: dict[str, dict[str, Any]],
    system_model: str,
    system_summary: dict[str, Any],
) -> None:
    lines = [
        "# EGE-13 benchmark",
        "",
        "Vision and downstream grading are evaluated separately at the mandatory human-confirmation boundary.",
        "The student's trig-circle drawing is ignored by current MVP scope, so diagram latency is always 0.",
        "",
        "## Vision model comparison",
        "",
        "| Model | Cases | Vision success | OCR similarity | Human correction | Avg Vision, s |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, summary in vision_summaries.items():
        lines.append(
            "| " + " | ".join([
                model,
                _fmt(summary.get("cases")),
                _fmt(summary.get("vision_success_rate")),
                _fmt(summary.get("mean_vision_similarity")),
                _fmt(summary.get("human_correction_rate")),
                _fmt(summary.get("avg_vision_seconds")),
            ]) + " |"
        )

    lines += [
        "",
        "## Human-confirmed grading system",
        "",
        f"System model: `{system_model}`",
        "",
        "| Cases | Scored | Score accuracy | MAE | Manual review | Avg total, s |",
        "|---:|---:|---:|---:|---:|---:|",
        "| " + " | ".join([
            _fmt(system_summary.get("cases")),
            _fmt(system_summary.get("scored_cases")),
            _fmt(system_summary.get("score_accuracy")),
            _fmt(system_summary.get("mean_abs_score_error")),
            _fmt(system_summary.get("manual_review_rate")),
            _fmt(system_summary.get("avg_total_seconds")),
        ]) + " |",
        "",
        "Note: expert labels can include visual-circle errors that are intentionally outside the current MVP scope; those are reported as real scope disagreements, not patched away.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--models", nargs="*", default=BENCHMARK_VISION_MODELS, help="Vision models to compare")
    parser.add_argument("--system-model", default=get_solver_model(), help="Fixed model for Solver/Grader/Reviewer")
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

    system_rows: list[dict[str, Any]] = []
    print(f"Кейсов: {len(cases)}")
    print("Eval boundary: Vision is measured separately; grading starts from human-confirmed transcript; circle ignored")
    print(f"\n=== SYSTEM {args.system_model} ===")
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
        row = _run_system_case(case, args.system_model)
        system_rows.append(row)
        if row.get("final_score") is not None:
            print(f"score {row['final_score']}/{row['expert_score']}, {row.get('total_seconds', 0):.1f}s")
        else:
            print(f"ERROR: {row.get('error', 'no score')}")

    vision_rows: list[dict[str, Any]] = []
    for model in args.models:
        print(f"\n=== VISION {model} ===")
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] {case['id']} ...", end=" ", flush=True)
            row = _run_vision_case(case, model, args.data_dir)
            vision_rows.append(row)
            similarity = row.get("vision_similarity")
            ocr_text = f"{similarity:.3f}" if isinstance(similarity, (int, float)) else "FAIL"
            if row.get("vision_ok"):
                print(f"ocr={ocr_text}, {row.get('total_seconds', 0):.1f}s")
            else:
                print(f"VISION FAIL, ocr={ocr_text}, {row.get('total_seconds', 0):.1f}s: {row.get('error', '')}")

    vision_summaries = {
        model: _vision_summary([row for row in vision_rows if row.get("model") == model])
        for model in args.models
    }
    system_summary = _system_summary(system_rows)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = args.results_dir / f"ege13-benchmark-{stamp}"
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    md_path = base.with_suffix(".md")
    all_rows = system_rows + vision_rows

    json_path.write_text(
        json.dumps({
            "method": "Vision models measured on photos; grading system measured once from human-confirmed transcripts; trig circle ignored",
            "vision_models": args.models,
            "system_model": args.system_model,
            "vision_summaries": vision_summaries,
            "system_summary": system_summary,
            "system_rows": system_rows,
            "vision_rows": vision_rows,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(csv_path, all_rows)
    _write_markdown(md_path, vision_summaries, args.system_model, system_summary)

    print("\n=== SYSTEM SUMMARY ===")
    print(args.system_model, json.dumps(system_summary, ensure_ascii=False))
    print("\n=== VISION SUMMARY ===")
    for model, summary in vision_summaries.items():
        print(model, json.dumps(summary, ensure_ascii=False))
    print(f"\nJSON: {json_path.relative_to(ROOT)}")
    print(f"CSV:  {csv_path.relative_to(ROOT)}")
    print(f"MD:   {md_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
# fix
