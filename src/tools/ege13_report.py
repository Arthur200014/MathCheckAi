from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import sympy as sp

from src.state import ReviewState
from src.tools.display_math import latex_to_human_text
from src.tools.ege13_reference import _extract_part_b_interval, _equal, _sympify
from src.tools.solution_steps import split_solution_step_texts


REPORT_DIR = Path("/tmp/mathcheck-ai/report-assets")


def extract_solution_steps(transcript: str, *, max_steps: int = 24) -> list[dict[str, str]]:

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
            verdict = {"status": "correct", "comment": "Ошибок в этом шаге не обнаружено."}
        elif sid in checked:
            verdict = {"status": "correct", "comment": "Шаг проверен Grader; ошибок не обнаружено."}
        else:
            verdict = {"status": "uncertain", "comment": "Шаг не получил отдельного подтверждения."}
        result.append(
            {
                "step_id": sid,
                "text": step["text"],
                "status": str(verdict.get("status", "uncertain")),
                "comment": str(verdict.get("comment", "")),
            }
        )

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
            row["comment"] = "По рисунку подтверждена ошибка отбора корней."

    return result


def _latex(expr: sp.Expr) -> str:
    return "$" + sp.latex(sp.simplify(expr)) + "$"


def _human_math(value: str) -> str:

    text = latex_to_human_text(str(value or "")).replace("$", "")
    lines: list[str] = []
    for raw in text.splitlines() or [text]:
        line = re.sub(r"\s+", " ", raw).strip()
        line = re.sub(r"π\s+\(", "π(", line)
        line = re.sub(r"(?<=\d)\s+(?=[nkm]\b)", "", line)
        line = line.replace(" ;", ";").replace(" ,", ",")
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _dedupe_expr(values: list[sp.Expr]) -> list[sp.Expr]:
    out: list[sp.Expr] = []
    for value in values:
        if not any(_equal(value, seen) for seen in out):
            out.append(value)
    return out


def _format_reference_part_a(state: ReviewState) -> str:
    rows: list[str] = []
    families = state.get("reference_verified_families", [])
    if isinstance(families, list):
        for item in families:
            if not isinstance(item, dict):
                continue
            expression = str(item.get("expression", "")).strip()
            parameter = str(item.get("parameter", "n")).strip() or "n"
            if not expression:
                continue
            try:
                symbol = sp.Symbol(parameter, integer=True)
                expr = _sympify(expression, extra={parameter: symbol})
                display = _human_math(sp.latex(sp.simplify(expr)))
            except Exception:
                display = _human_math(expression)
            row = f"x = {display}, {parameter} ∈ ℤ"
            if row not in rows:
                rows.append(row)
    if rows:
        return "\n".join(rows)
    return _human_math(str(state.get("reference_answer_part_a_verified", "")))


def _format_reference_part_b(state: ReviewState) -> str:
    roots: list[str] = []
    for raw in list(state.get("reference_expected_roots", []) or []):
        try:
            roots.append(_human_math(sp.latex(sp.simplify(_sympify(str(raw))))))
        except Exception:
            roots.append(_human_math(str(raw)))
    if roots:
        return "; ".join(roots)
    return _human_math(str(state.get("reference_answer_part_b_verified", "")))


def _display_step_checks(raw_steps: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in raw_steps:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "step_id": str(row.get("step_id", "")),
                "text": _human_math(str(row.get("text", ""))),
                "status": str(row.get("status", "uncertain")),
                "comment": _human_math(str(row.get("comment", ""))),
            }
        )
    return out


def _first_incorrect_comment(step_checks: list[dict[str, str]]) -> str:
    for row in step_checks:
        if str(row.get("status", "")).lower() != "incorrect":
            continue
        comment = str(row.get("comment", "")).strip()
        if not comment:
            continue
                                                                                
        comment = re.sub(r"\s+", " ", comment)
        if len(comment) > 150:
            comment = comment[:147].rstrip() + "…"
        return comment
    return ""


def _part_b_present(state: ReviewState) -> bool:
    evidence = state.get("grader_student_evidence", {})
    if isinstance(evidence, dict) and "part_b_present" in evidence:
        return bool(evidence.get("part_b_present"))
    return str(state.get("reviewer_part_b_status") or state.get("grader_part_b_status") or "") != "missing"


def _friendly_part_a(state: ReviewState, step_checks: list[dict[str, str]]) -> str:
    status = str(state.get("reviewer_part_a_status") or state.get("grader_part_a_status") or "").strip()
    if state.get("reviewer_part_a_equivalent") is True or status == "correct":
        return "Верно."
    if status == "missing":
        return "Пункт а не выполнен."
    if status == "computation_error_only" or str(state.get("reviewer_error_class") or state.get("grader_error_class")) == "computation_error":
        return "Вычислительная ошибка: ход решения в целом верный."

    specific = _first_incorrect_comment(step_checks)
    math_errors = " ".join(str(x) for x in state.get("grader_student_math_errors", []) or []).lower()
    if "family" in math_errors or "period" in math_errors or "solution" in math_errors:
        return "Ошибка в общем решении." + (f" {specific}" if specific else "")
    if specific:
        return specific
    if status == "substantive_error" or state.get("reviewer_part_a_equivalent") is False:
        return "Неверное преобразование или общее решение."
    return "Нужно проверить пункт а вручную."


def _friendly_part_b(state: ReviewState, *, present: bool) -> str:
    if not present:
        return "Пункт б не выполнялся."
    status = str(state.get("reviewer_part_b_status") or state.get("grader_part_b_status") or "").strip()
    if state.get("reviewer_part_b_roots_match") is True or status == "correct":
        return "Верно."
    if status == "missing":
        return "Пункт б не выполнялся."
    if status == "incorrect" or state.get("reviewer_part_b_roots_match") is False:
        return "Ошибка в отборе корней."
    return "Нужно проверить пункт б вручную."


def _friendly_summary(*, score: int, max_score: int, part_a: str, part_b: str, part_b_present: bool) -> str:
    if score == max_score:
        return "Решение верное."
    if part_a.startswith("Вычислительная ошибка"):
        return "Вычислительная ошибка."
    if part_a != "Верно.":
                                                                               
        if part_a.startswith("Ошибка в общем решении"):
            return "Ошибка в общем решении."
        if part_a.startswith("Неверное преобразование"):
            return "Неверное преобразование."
        return "Ошибка в пункте а."
    if not part_b_present:
        return "Пункт б не выполнен."
    if part_b != "Верно.":
        return "Ошибка в отборе корней."
    return "Проверка завершена."


def render_verified_trig_circle(
    *,
    review_id: str,
    task_statement: str,
    expected_roots: list[str],
) -> Path:

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

    bg = "#0F172A"
    panel = "#111827"
    axis = "#64748B"
    muted = "#94A3B8"
    text = "#F8FAFC"
    accent = "#F59E0B"
    good = "#34D399"

    fig, ax = plt.subplots(figsize=(5.0, 5.0), dpi=170)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(panel)
    ax.set_aspect("equal")

    circle = plt.Circle((0, 0), 1.0, fill=False, linewidth=1.6, edgecolor=axis, alpha=0.95)
    ax.add_patch(circle)
    ax.axhline(0, linewidth=0.9, color=axis, alpha=0.75)
    ax.axvline(0, linewidth=0.9, color=axis, alpha=0.75)
    ax.text(1.15, -0.07, "x", fontsize=10, color=muted)
    ax.text(0.05, 1.15, "y", fontsize=10, color=muted)

                                                                                   
    if span >= 2 * math.pi - 1e-9:
        arc_start_deg, arc_end_deg = 0.0, 360.0
    else:
        arc_start_deg = math.degrees(start)
        arc_end_deg = math.degrees(start + span)
    ax.add_patch(
        Arc(
            (0, 0),
            2,
            2,
            theta1=arc_start_deg,
            theta2=arc_end_deg,
            linewidth=7.0,
            color=accent,
            alpha=0.92,
            zorder=3,
        )
    )
    if 0.12 < span < 2 * math.pi - 1e-9:
        arrow_to = start + span * 0.82
        arrow_from = arrow_to - min(0.16, span * 0.12)
        ax.annotate(
            "",
            xy=(math.cos(arrow_to), math.sin(arrow_to)),
            xytext=(math.cos(arrow_from), math.sin(arrow_from)),
            arrowprops={"arrowstyle": "->", "linewidth": 2.0, "color": accent},
            zorder=7,
        )

    def point(expr: sp.Expr) -> tuple[float, float]:
        return float(sp.N(sp.cos(expr), 20)), float(sp.N(sp.sin(expr), 20))

    non_root_boundaries = [expr for expr in [left, right] if not any(_equal(expr, root) for root in roots)]
    if non_root_boundaries:
        coords = [point(expr) for expr in non_root_boundaries]
        ax.scatter(
            [x for x, _ in coords],
            [y for _, y in coords],
            s=48,
            marker="s",
            color=accent,
            edgecolors=bg,
            linewidths=1.0,
            zorder=5,
        )
        for expr, (x, y) in zip(non_root_boundaries, coords):
            ax.text(1.19 * x, 1.19 * y, _latex(expr), ha="center", va="center", fontsize=10, color=text)

    if roots:
        coords = [point(expr) for expr in roots]
        ax.scatter(
            [x for x, _ in coords],
            [y for _, y in coords],
            s=66,
            color=good,
            edgecolors=bg,
            linewidths=1.2,
            zorder=6,
        )
        for expr, (x, y) in zip(roots, coords):
            ax.text(1.31 * x, 1.31 * y, _latex(expr), ha="center", va="center", fontsize=10, color=text)

    interval_label = f"[{_human_math(sp.latex(left))}; {_human_math(sp.latex(right))}]"
    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-1.55, 1.55)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Правильный отбор корней", fontsize=12, color=text, pad=10, fontweight="bold")
    ax.text(
        0.5,
        0.02,
        f"Интервал: {interval_label}",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color=accent,
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{review_id}-trig-circle.png"
    fig.savefig(path, bbox_inches="tight", pad_inches=0.12, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def report_circle_path(review_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "", str(review_id))
    return REPORT_DIR / f"{safe}-trig-circle.png"


def build_compact_report_node(state: ReviewState) -> dict[str, Any]:

    if state.get("status") != "REVIEWED":
        return {}

    final_score = int(state.get("final_score", 0))
    max_score = int(state.get("max_score", state.get("task_max_score", 2)))

    step_checks = _display_step_checks(list(state.get("grader_step_assessments", [])))
    part_b_present = _part_b_present(state)
    part_a_comment = _friendly_part_a(state, step_checks)
    part_b_comment = _friendly_part_b(state, present=part_b_present)
    expert_comment = _friendly_summary(
        score=final_score,
        max_score=max_score,
        part_a=part_a_comment,
        part_b=part_b_comment,
        part_b_present=part_b_present,
    )

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
        except Exception as exc:
            circle_error = str(exc)

    report = {
        "title": str(state.get("task_title", "Проверка решения")),
        "score": final_score,
        "max_score": max_score,
        "score_text": f"{final_score}/{max_score}",
        "score_label": "Итоговый балл",
        "status_label": "Проверка завершена",
        "step_checks": step_checks,
        "part_a_comment": part_a_comment,
        "part_b_comment": part_b_comment,
        "part_b_present": part_b_present,
        "expert_comment": expert_comment,
        "correct_answer_part_a": _format_reference_part_a(state),
        "correct_answer_part_b": _format_reference_part_b(state),
        "student_diagram_status": "NOT_ANALYZED_MVP",
        "student_diagram_comment": "Окружность ученика отдельно не распознаётся; справа показан правильный отбор по подтверждённому условию.",
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
        report["render_warning"] = f"Не удалось построить окружность: {circle_error}"

    return {"report": report, "report_circle_url": circle_url}
