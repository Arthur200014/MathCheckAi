from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import sympy as sp

from src.state import ReviewState
from src.tools.ege13_reference import _extract_part_b_interval, _equal, _sympify
from src.tools.solution_steps import split_solution_step_texts


REPORT_DIR = Path("/tmp/mathcheck-ai/report-assets")


def extract_solution_steps(transcript: str, *, max_steps: int = 24) -> list[dict[str, str]]:
    """Return stable user-visible step ids from the shared deterministic parser."""
    texts = split_solution_step_texts(transcript, max_steps=max_steps)
    return [{"step_id": f"S{i}", "text": text} for i, text in enumerate(texts, start=1)]


def normalize_step_assessments(
    steps: list[dict[str, str]],
    raw_assessments: Any,
    *,
    explicit_final_answer_mismatch: bool = False,
    diagram_invalid: bool = False,
    sparse_issues: bool = False,
    checked_step_ids: list[str] | None = None,
    deterministic_overrides: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    allowed = {"correct", "incorrect", "uncertain"}
    by_id: dict[str, dict[str, str]] = {}
    if isinstance(raw_assessments, list):
        for item in raw_assessments:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("step_id", "")).strip()
            if not sid:
                continue
            status = str(item.get("status", "uncertain")).strip().lower()
            if status not in allowed:
                status = "uncertain"
            by_id[sid] = {
                "status": status,
                "comment": str(item.get("comment", "")).strip(),
            }

    checked = {str(x).strip() for x in (checked_step_ids or []) if str(x).strip()}
    overrides = deterministic_overrides or {}

    result: list[dict[str, str]] = []
    for step in steps:
        sid = step["step_id"]
        if sid in overrides:
            verdict = overrides[sid]
        elif sid in by_id:
            verdict = by_id[sid]
        elif sparse_issues and checked_step_ids is None:
            # Backward-compatible mode used by old tests/callers.
            verdict = {"status": "correct", "comment": "Ошибок в этом шаге не обнаружено."}
        elif sid in checked:
            verdict = {"status": "correct", "comment": "Шаг проверен Grader; ошибок не обнаружено."}
        else:
            # Absence from a compact LLM response is NOT proof of correctness.
            # This prevents false-green rows when the model silently skipped a step.
            verdict = {"status": "uncertain", "comment": "Шаг не получил отдельного подтверждения."}
        row = {
            "step_id": sid,
            "text": step["text"],
            "status": str(verdict.get("status", "uncertain")),
            "comment": str(verdict.get("comment", "")),
        }
        result.append(row)

    # Deterministic evidence outranks a friendly LLM verdict on the final answer.
    if explicit_final_answer_mismatch:
        candidates = [r for r in result if re.search(r"ответ\s*:|\bб\)|\bb\)", r["text"], re.IGNORECASE)]
        if candidates:
            row = candidates[-1]
            row["status"] = "incorrect"
            row["comment"] = "Итоговый набор корней пункта б не совпадает с проверенным эталоном."

    if diagram_invalid:
        candidates = [r for r in result if re.search(r"окруж|отбор|\bб\)|\bb\)", r["text"], re.IGNORECASE)]
        if candidates:
            row = candidates[-1]
            row["status"] = "incorrect"
            row["comment"] = "По рисунку подтверждена содержательная ошибка отбора корней."

    return result


def _latex(expr: sp.Expr) -> str:
    return "$" + sp.latex(sp.simplify(expr)) + "$"


def _dedupe_expr(values: list[sp.Expr]) -> list[sp.Expr]:
    out: list[sp.Expr] = []
    for value in values:
        if not any(_equal(value, seen) for seen in out):
            out.append(value)
    return out


def render_verified_trig_circle(
    *,
    review_id: str,
    task_statement: str,
    expected_roots: list[str],
) -> Path:
    """Render a clean reference trig circle from verified math, not OCR geometry."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Arc

    left, right, _, _ = _extract_part_b_interval(task_statement)
    roots = _dedupe_expr([_sympify(v) for v in expected_roots])

    left_f = float(sp.N(left, 20))
    right_f = float(sp.N(right, 20))
    span = max(0.0, right_f - left_f)
    start = left_f % (2 * math.pi)

    fig, ax = plt.subplots(figsize=(5.2, 5.2), dpi=160)
    ax.set_aspect("equal")

    # base circle and axes
    circle = plt.Circle((0, 0), 1.0, fill=False, linewidth=1.3, alpha=0.55)
    ax.add_patch(circle)
    ax.axhline(0, linewidth=0.9, alpha=0.75)
    ax.axvline(0, linewidth=0.9, alpha=0.75)
    ax.text(1.16, -0.07, "x", fontsize=10)
    ax.text(0.05, 1.17, "y", fontsize=10)

    # Increasing x on the trig circle means counter-clockwise. For intervals
    # longer than one revolution the full circle is the only honest compact view.
    if span >= 2 * math.pi - 1e-9:
        arc_start_deg, arc_end_deg = 0.0, 360.0
    else:
        arc_start_deg = math.degrees(start)
        arc_end_deg = math.degrees(start + span)
    arc = Arc((0, 0), 2, 2, theta1=arc_start_deg, theta2=arc_end_deg, linewidth=4.0, alpha=0.9)
    ax.add_patch(arc)
    if 0.12 < span < 2 * math.pi - 1e-9:
        arrow_to = start + span * 0.82
        arrow_from = arrow_to - min(0.16, span * 0.12)
        ax.annotate(
            "",
            xy=(math.cos(arrow_to), math.sin(arrow_to)),
            xytext=(math.cos(arrow_from), math.sin(arrow_from)),
            arrowprops={"arrowstyle": "->", "linewidth": 2.0},
            zorder=7,
        )

    def point(expr: sp.Expr) -> tuple[float, float]:
        return float(sp.N(sp.cos(expr), 20)), float(sp.N(sp.sin(expr), 20))

    # Interval endpoints that are not themselves selected roots. If a root is
    # also a boundary (common in EGE-13), draw/label it only once below.
    non_root_boundaries = [
        expr for expr in [left, right]
        if not any(_equal(expr, root) for root in roots)
    ]
    if non_root_boundaries:
        coords = [point(expr) for expr in non_root_boundaries]
        ax.scatter([x for x, _ in coords], [y for _, y in coords], s=42, marker="s", zorder=5)
        for expr, (x, y) in zip(non_root_boundaries, coords):
            scale = 1.18
            ax.text(scale * x, scale * y, _latex(expr), ha="center", va="center", fontsize=10)

    # Verified roots, including roots that coincide with interval boundaries.
    if roots:
        coords = [point(expr) for expr in roots]
        ax.scatter([x for x, _ in coords], [y for _, y in coords], s=55, zorder=6)
        for expr, (x, y) in zip(roots, coords):
            scale = 1.30
            ax.text(scale * x, scale * y, _latex(expr), ha="center", va="center", fontsize=10)

    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-1.55, 1.55)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Правильный отбор корней", fontsize=12)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{review_id}-trig-circle.png"
    fig.savefig(path, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return path


def report_circle_path(review_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "", str(review_id))
    return REPORT_DIR / f"{safe}-trig-circle.png"


def _human_error_reason(error_class: str) -> str:
    return {
        "root_selection_error": "В пункте б допущена ошибка в итоговом отборе корней.",
        "diagram_selection_error": "На окружности подтверждена содержательная ошибка отбора корней.",
        "computation_error": "Есть локальная вычислительная ошибка при в целом правильной схеме решения.",
        "substantive_math_error": "Обнаружена содержательная математическая ошибка в пункте а.",
        "ambiguous": "Часть решения не удалось однозначно проверить автоматически.",
        "none": "Содержательных ошибок не обнаружено.",
    }.get(str(error_class), "Проверка завершена по экспертным критериям.")


def build_compact_report_node(state: ReviewState) -> dict[str, Any]:
    """Build user-facing report without adding another LLM/agent."""
    if state.get("status") != "REVIEWED":
        return {}

    final_score = int(state.get("final_score", 0))
    max_score = int(state.get("max_score", state.get("task_max_score", 2)))
    error_class = str(state.get("reviewer_error_class") or state.get("grader_error_class") or "none")

    step_checks = list(state.get("grader_step_assessments", []))
    a_ok = state.get("reviewer_part_a_equivalent") is True
    b_ok = state.get("reviewer_part_b_roots_match") is True and not state.get("reviewer_diagram_override_applied", False)

    if final_score == max_score:
        expert_comment = "Решение соответствует критериям: существенных математических ошибок не обнаружено."
    else:
        expert_comment = _human_error_reason(error_class)

    part_a_comment = "Пункт а засчитан." if a_ok else "Пункт а не подтверждён как полностью верный."
    if b_ok:
        part_b_comment = "Пункт б засчитан: итоговый набор корней совпадает с проверенным эталоном."
    else:
        part_b_comment = _human_error_reason(error_class)

    circle_url = ""
    circle_error = ""
    if state.get("task_type") == "ege_13" and state.get("reference_verification_ok", False):
        try:
            render_verified_trig_circle(
                review_id=str(state.get("review_id", "review")),
                task_statement=str(state.get("task_statement", "")),
                expected_roots=list(state.get("reference_expected_roots", [])),
            )
            circle_url = f"/api/reviews/{state.get('review_id')}/report-circle"
        except Exception as exc:  # report rendering must never invalidate grading
            circle_error = str(exc)

    diagram_status = "NOT_ANALYZED_MVP"
    student_diagram_comment = (
        "В быстром MVP рукописная окружность не проходит отдельный Vision-pass. "
        "Оценка опирается на подтверждённый текст и математические проверки; ниже строится правильная эталонная окружность."
    )

    report = {
        "title": str(state.get("task_title", "Проверка решения")),
        "score": final_score,
        "max_score": max_score,
        "score_text": f"{final_score}/{max_score}",
        "step_checks": step_checks,
        "part_a_comment": part_a_comment,
        "part_b_comment": part_b_comment,
        "expert_comment": expert_comment,
        "correct_answer_part_a": str(state.get("reference_answer_part_a_verified", "")),
        "correct_answer_part_b": str(state.get("reference_answer_part_b_verified", "")),
        "student_diagram_status": diagram_status,
        "student_diagram_comment": student_diagram_comment,
        "correct_trig_circle_url": circle_url,
        "correct_trig_circle_source": "verified_reference" if circle_url else "",
        "agent_timings_seconds": {
            "vision": float(state.get("vision_elapsed_seconds", 0) or 0),
            "solver": float(state.get("solver_elapsed_seconds", 0) or 0),
            "grader": float(state.get("grader_elapsed_seconds", 0) or 0),
            "reviewer": float(state.get("reviewer_elapsed_seconds", 0) or 0),
        },
    }
    if circle_error:
        report["render_warning"] = f"Не удалось построить окружность для отчёта: {circle_error}"

    return {"report": report, "report_circle_url": circle_url}
