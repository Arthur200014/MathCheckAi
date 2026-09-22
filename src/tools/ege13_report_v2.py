from __future__ import annotations

import re
from typing import Any

import sympy as sp

from src.state import ReviewState
from src.tools.display_math import latex_to_human_text
from src.tools.ege13_reference import _equal, _sympify
from src.tools.ege13_report import render_verified_trig_circle
from src.tools.ege13_student import _extract_student_families_from_text


def _human_math(value: str) -> str:
    text = latex_to_human_text(str(value or "")).replace("$", "")
    lines: list[str] = []
    for raw in text.splitlines() or [text]:
        line = re.sub(r"\s+", " ", raw).strip()
        line = line.replace(" ;", ";").replace(" ,", ",")
        line = re.sub(r"π\s+\(", "π(", line)
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _pi_ratio(expr: sp.Expr) -> sp.Rational | None:
    ratio = sp.simplify(expr / sp.pi)
    return ratio if isinstance(ratio, sp.Rational) else None


def _format_pi_multiple(expr: sp.Expr) -> str:
    value = sp.simplify(expr)
    ratio = _pi_ratio(value)
    if ratio is None:
        return _human_math(sp.latex(value))
    if ratio == 0:
        return "0"
    sign = "-" if ratio < 0 else ""
    ratio = abs(ratio)
    num, den = int(ratio.p), int(ratio.q)
    if den == 1:
        core = "π" if num == 1 else f"{num}π"
    else:
        numerator = "π" if num == 1 else f"{num}π"
        core = f"{numerator}/{den}"
    return sign + core


def _family_parts(expression: str, parameter: str) -> tuple[sp.Expr, sp.Expr] | None:
    symbol = sp.Symbol(parameter, integer=True)
    try:
        expr = sp.expand(_sympify(expression, extra={parameter: symbol}))
    except Exception:
        return None
    coeff = sp.simplify(sp.diff(expr, symbol))
    if symbol in coeff.free_symbols:
        return None
    if sp.simplify(sp.diff(expr, symbol, 2)) != 0:
        return None
    offset = sp.simplify(expr.subs(symbol, 0))
    period = sp.simplify(abs(coeff))
    if period == 0:
        return None

                                                                             
                                                              
    period_ratio = _pi_ratio(period)
    offset_ratio = _pi_ratio(offset)
    if period_ratio is not None and period_ratio > 0 and offset_ratio is not None:
        shift = sp.floor(offset_ratio / period_ratio + sp.Rational(1, 2))
        offset = sp.simplify((offset_ratio - shift * period_ratio) * sp.pi)
    return offset, period


def _format_family(expression: str, parameter: str = "n") -> tuple[str, sp.Expr | None]:
    parts = _family_parts(expression, parameter)
    if parts is None:
        try:
            symbol = sp.Symbol(parameter, integer=True)
            expr = _sympify(expression, extra={parameter: symbol})
            return f"x = {_human_math(sp.latex(sp.simplify(expr)))}, {parameter} ∈ ℤ", None
        except Exception:
            return f"x = {_human_math(expression)}, {parameter} ∈ ℤ", None

    offset, period = parts
    offset_text = _format_pi_multiple(offset)
    period_text = _format_pi_multiple(period)
    n = "n"                                                                   
    period_term = f"{period_text}{n}"
    if offset == 0:
        rhs = period_term
    else:
        rhs = f"{offset_text} + {period_term}"
    return f"x = {rhs}, {n} ∈ ℤ", offset


def _reference_family_rows(state: ReviewState) -> list[str]:
    rows_with_offset: list[tuple[sp.Expr | None, str]] = []
    seen: set[str] = set()
    families = state.get("reference_verified_families", [])
    if isinstance(families, list):
        for item in families:
            if not isinstance(item, dict):
                continue
            expression = str(item.get("expression", "")).strip()
            parameter = str(item.get("parameter", "n")).strip() or "n"
            if not expression:
                continue
            row, offset = _format_family(expression, parameter)
            if row in seen:
                continue
            seen.add(row)
            rows_with_offset.append((offset, row))

    if rows_with_offset:
                                                                           
                                                        
        def key(item: tuple[sp.Expr | None, str]) -> float:
            off = item[0]
            if off is None:
                return -10_000.0
            try:
                return float(sp.N(off / sp.pi, 20))
            except Exception:
                return -10_000.0

        rows_with_offset.sort(key=key, reverse=True)
        return [row for _, row in rows_with_offset]

    fallback = _human_math(str(state.get("reference_answer_part_a_verified", "")))
    return [fallback] if fallback else []


def _format_reference_part_a(state: ReviewState) -> str:
    return "\n".join(_reference_family_rows(state))


def _format_reference_part_b(state: ReviewState) -> str:
    roots: list[sp.Expr] = []
    for raw in list(state.get("reference_expected_roots", []) or []):
        try:
            value = _sympify(str(raw))
        except Exception:
            continue
        if not any(_equal(value, old) for old in roots):
            roots.append(value)
    if roots:
        return "; ".join(_format_pi_multiple(root) for root in roots)
    return _human_math(str(state.get("reference_answer_part_b_verified", "")))


def _part_b_present(state: ReviewState) -> bool:
    evidence = state.get("grader_student_evidence", {})
    if isinstance(evidence, dict) and "part_b_present" in evidence:
        return bool(evidence.get("part_b_present"))
    return str(state.get("reviewer_part_b_status") or state.get("grader_part_b_status") or "") != "missing"


def _specific_reason(comment: str, *, family_error: bool = False, final_roots_error: bool = False) -> str:
    raw = _human_math(comment)
    lower = raw.lower()
    if family_error:
        if "period" in lower or "период" in lower:
            return "Неверный период в общем решении."
        return "Ошибка в общем решении."
    if final_roots_error:
        return "Неверный набор корней пункта б."
    if any(word in lower for word in ("знак", "коэффициент", "раскры", "перенос", "арифмет", "вычисл")):
        return raw.rstrip(".") + "."
    if raw and not any(phrase in lower for phrase in ("не подтверж", "содержательн", "не совпадает с проверенным эталоном", "шаг не получил")):
        return raw.rstrip(".") + "."
    return "Неверное преобразование."


def _matching_reference_family(step_text: str, state: ReviewState) -> str:
    student_families, _, _ = _extract_student_families_from_text(step_text)
    if not student_families:
        return ""

    refs: list[tuple[sp.Expr, sp.Expr, str]] = []
    for item in list(state.get("reference_verified_families", []) or []):
        if not isinstance(item, dict):
            continue
        expr_text = str(item.get("expression", "")).strip()
        param = str(item.get("parameter", "n")).strip() or "n"
        parts = _family_parts(expr_text, param)
        if parts is None:
            continue
        offset, period = parts
        display, _ = _format_family(expr_text, param)
        refs.append((offset, period, display))
    if not refs:
        return ""

    first = student_families[0]
    parts = _family_parts(str(first.get("expression", "")), str(first.get("parameter", "n")) or "n")
    if parts is None:
        return refs[0][2]
    student_offset, _ = parts

                                                                            
    exact: list[str] = []
    for ref_offset, ref_period, display in refs:
        delta = sp.simplify((student_offset - ref_offset) / ref_period)
        if delta.is_integer is True:
            exact.append(display)
    if exact:
        return exact[0]

                                                                   
    def distance(item: tuple[sp.Expr, sp.Expr, str]) -> float:
        ref_offset, _, _ = item
        try:
            return abs(float(sp.N((student_offset - ref_offset) / sp.pi, 20)))
        except Exception:
            return 1e9
    return min(refs, key=distance)[2]


def _next_correct_formula(rows: list[dict[str, str]], index: int) -> str:
    for row in rows[index + 1 :]:
        if row.get("status") != "correct":
            continue
        text = str(row.get("text", "")).strip()
        if "=" in text:
            return text
    return ""


def _display_step_checks(state: ReviewState) -> list[dict[str, str]]:
    raw_steps = list(state.get("grader_step_assessments", []) or [])
    rows: list[dict[str, str]] = []
    for row in raw_steps:
        if not isinstance(row, dict):
            continue
        rows.append({
            "step_id": str(row.get("step_id", "")),
            "text": _human_math(str(row.get("text", ""))),
            "status": str(row.get("status", "uncertain")).lower(),
            "comment": _human_math(str(row.get("comment", ""))),
            "correction": "",
        })

    correct_b = _format_reference_part_b(state)
    correct_a_rows = _reference_family_rows(state)
    part_b_present = _part_b_present(state)

    for i, row in enumerate(rows):
        if row["status"] != "incorrect":
            if row["status"] == "correct" and row["comment"].startswith(("Шаг проверен", "Ошибок в этом шаге")):
                row["comment"] = ""
            continue

        text = row["text"]
        family_correction = _matching_reference_family(text, state)
        is_family = bool(family_correction)
        is_part_b = bool(re.search(r"(?:^|\s)(?:б|b)\s*\)|ответ\s*:", text, re.IGNORECASE))

        if is_family:
            row["comment"] = _specific_reason(row["comment"], family_error=True)
            row["correction"] = family_correction
        elif is_part_b and part_b_present and correct_b:
            row["comment"] = _specific_reason(row["comment"], final_roots_error=True)
            row["correction"] = correct_b
        else:
            row["comment"] = _specific_reason(row["comment"])
            next_formula = _next_correct_formula(rows, i)
            if next_formula:
                row["correction"] = next_formula
            elif correct_a_rows:
                row["correction"] = correct_a_rows[0]

        if row["correction"]:
            row["comment"] = f"{row['comment']} Правильно: {row['correction']}"

    return rows


def _first_incorrect_reason(step_checks: list[dict[str, str]]) -> str:
    for row in step_checks:
        if row.get("status") == "incorrect":
            comment = str(row.get("comment", "")).split(" Правильно:", 1)[0].strip()
            if comment:
                return comment
    return ""


def _friendly_part_a(state: ReviewState, step_checks: list[dict[str, str]]) -> str:
    status = str(state.get("reviewer_part_a_status") or state.get("grader_part_a_status") or "").strip()
    if state.get("reviewer_part_a_equivalent") is True or status == "correct":
        return "Верно."
    if status == "missing":
        return "Пункт а не выполнен."
    if status == "computation_error_only" or str(state.get("reviewer_error_class") or state.get("grader_error_class")) == "computation_error":
        return "Вычислительная ошибка."
    specific = _first_incorrect_reason(step_checks)
    return specific or "Ошибка в общем решении."


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
    return "Нужно проверить пункт б."


def _summary(score: int, max_score: int, part_a: str, part_b: str, part_b_present: bool) -> str:
    if score == max_score:
        return "Решение верное."
    if part_a != "Верно.":
        return part_a
    if not part_b_present:
        return "Пункт б не выполнен."
    if part_b != "Верно.":
        return part_b
    return "Проверка завершена."


def build_compact_report_node(state: ReviewState) -> dict[str, Any]:

    if state.get("status") != "REVIEWED":
        return {}

    final_score = int(state.get("final_score", 0))
    max_score = int(state.get("max_score", state.get("task_max_score", 2)))
    step_checks = _display_step_checks(state)
    part_b_present = _part_b_present(state)
    part_a_comment = _friendly_part_a(state, step_checks)
    part_b_comment = _friendly_part_b(state, present=part_b_present)

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
        "expert_comment": _summary(final_score, max_score, part_a_comment, part_b_comment, part_b_present),
        "correct_answer_part_a": _format_reference_part_a(state),
        "correct_answer_part_b": _format_reference_part_b(state),
        "student_diagram_status": "NOT_ANALYZED_MVP",
        "student_diagram_comment": "Справа показан правильный отбор по подтверждённому условию.",
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
# fix
