from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import sympy as sp

from src.state import ReviewState
from src.tools.display_math import latex_to_human_text
from src.tools.ege13_reference import _equal, _sympify
from src.tools.ege13_report import render_verified_trig_circle
from src.tools.ege13_student import _extract_student_families_from_text


@dataclass(frozen=True)
class LinearFamily:
    seed: sp.Expr
    period: sp.Expr
    display: str


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


def _linear_parts_raw(expression: str, parameter: str) -> tuple[sp.Expr, sp.Expr] | None:






    symbol = sp.Symbol(parameter, integer=True)
    try:
        expr = sp.expand(_sympify(expression, extra={parameter: symbol}))
    except Exception:
        return None
    coeff = sp.simplify(sp.diff(expr, symbol))
    if symbol in coeff.free_symbols or sp.simplify(sp.diff(expr, symbol, 2)) != 0:
        return None
    period = sp.simplify(abs(coeff))
    if period == 0:
        return None
    seed = sp.simplify(expr.subs(symbol, 0))
    return seed, period


def _display_offset(seed: sp.Expr, period: sp.Expr) -> sp.Expr:

    p = _pi_ratio(period)
    a = _pi_ratio(seed)
    if p is None or a is None or p <= 0:
        return sp.simplify(seed)
    shift = sp.floor(a / p + sp.Rational(1, 2))
    return sp.simplify((a - shift * p) * sp.pi)


def _format_linear_family(expression: str, parameter: str = "n") -> LinearFamily | None:
    parts = _linear_parts_raw(expression, parameter)
    if parts is None:
        return None
    raw_seed, period = parts
    shown_seed = _display_offset(raw_seed, period)
    seed_text = _format_pi_multiple(shown_seed)
    period_text = _format_pi_multiple(period)
    rhs = f"{period_text}n" if shown_seed == 0 else f"{seed_text} + {period_text}n"
    rhs = rhs.replace("+ -", "- ")
    return LinearFamily(seed=raw_seed, period=period, display=f"x = {rhs}, n ∈ ℤ")


def _reference_families(state: ReviewState) -> list[LinearFamily]:
    refs: list[LinearFamily] = []
    for item in list(state.get("reference_verified_families", []) or []):
        if not isinstance(item, dict):
            continue
        expression = str(item.get("expression", "")).strip()
        parameter = str(item.get("parameter", "n")).strip() or "n"
        if not expression:
            continue
        family = _format_linear_family(expression, parameter)
        if family is None:
            continue
        if not any(_equal(family.seed, old.seed) and _equal(family.period, old.period) for old in refs):
            refs.append(family)
    return refs


def _belongs(value: sp.Expr, family: LinearFamily) -> bool:
    quotient = sp.simplify((value - family.seed) / family.period)
    return quotient.is_integer is True


def _family_equivalent(student: LinearFamily, reference: LinearFamily) -> bool:
    return _equal(student.period, reference.period) and _belongs(student.seed, reference)


def _distance_to_family(value: sp.Expr, family: LinearFamily) -> float:

    try:
        q = float(sp.N((value - family.seed) / family.period, 30))
        nearest = round(q)
        return abs(q - nearest) * abs(float(sp.N(family.period / sp.pi, 30)))
    except Exception:
        return 1e9


def _match_reference_family(student: LinearFamily, refs: list[LinearFamily]) -> LinearFamily | None:









    if not refs:
        return None

    seed_matches = [ref for ref in refs if _belongs(student.seed, ref)]
    if seed_matches:
                                                                             
                                                                           
        return min(
            seed_matches,
            key=lambda ref: abs(float(sp.N((student.period - ref.period) / sp.pi, 30))),
        )

    sample_values = [sp.simplify(student.seed + k * student.period) for k in (-2, -1, 0, 1, 2)]

    def score(ref: LinearFamily) -> tuple[int, float]:
        overlap = sum(1 for value in sample_values if _belongs(value, ref))
        return (-overlap, _distance_to_family(student.seed, ref))

    return min(refs, key=score)


def _format_reference_part_a(state: ReviewState) -> str:
    refs = _reference_families(state)
    if refs:
                                                                           
                          
        def order_key(ref: LinearFamily) -> float:
            shown = _display_offset(ref.seed, ref.period)
            try:
                return float(sp.N(shown / sp.pi, 30))
            except Exception:
                return -1e9

        return "\n".join(ref.display for ref in sorted(refs, key=order_key, reverse=True))
    return _human_math(str(state.get("reference_answer_part_a_verified", "")))


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


def _specific_reason(comment: str) -> str:
    raw = _human_math(comment)
    lower = raw.lower()
    if any(word in lower for word in ("знак", "коэффициент", "раскры", "перенос", "арифмет", "вычисл")):
        return raw.rstrip(".") + "."
    if raw and not any(phrase in lower for phrase in ("не подтверж", "содержательн", "не совпадает с проверенным эталоном", "шаг не получил")):
        return raw.rstrip(".") + "."
    return "Неверное преобразование."


def _family_corrections(step_text: str, state: ReviewState) -> tuple[str, list[str]]:

    refs = _reference_families(state)
    if not refs:
        return "", []

    parsed, _, _ = _extract_student_families_from_text(step_text)
    corrections: list[str] = []
    saw_period_error = False
    saw_family_error = False

    for item in parsed:
        expression = str(item.get("expression", "")).strip()
        parameter = str(item.get("parameter", "n")).strip() or "n"
        parts = _linear_parts_raw(expression, parameter)
        if parts is None:
            continue
        student = LinearFamily(seed=parts[0], period=parts[1], display="")

        if any(_family_equivalent(student, ref) for ref in refs):
            continue

        match = _match_reference_family(student, refs)
        if match is None:
            continue
        saw_family_error = True
        if _belongs(student.seed, match) and not _equal(student.period, match.period):
            saw_period_error = True
        if match.display not in corrections:
            corrections.append(match.display)

    if not corrections:
        return "", []
    if saw_period_error:
        return "Неверный период в общем решении.", corrections
    if saw_family_error:
        return "Ошибка в общем решении.", corrections
    return "", corrections


def _next_verified_formula(rows: list[dict[str, str]], index: int) -> str:
    for row in rows[index + 1 :]:
        if row.get("status") != "correct":
            continue
        text = str(row.get("text", "")).strip()
        if "=" in text:
            return text
    return ""


def _display_step_checks(state: ReviewState) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in list(state.get("grader_step_assessments", []) or []):
        if not isinstance(raw, dict):
            continue
        rows.append(
            {
                "step_id": str(raw.get("step_id", "")),
                "text": _human_math(str(raw.get("text", ""))),
                "status": str(raw.get("status", "uncertain")).lower(),
                "comment": _human_math(str(raw.get("comment", ""))),
                "correction": "",
            }
        )

    correct_b = _format_reference_part_b(state)
    part_b_present = _part_b_present(state)

    for i, row in enumerate(rows):
        if row["status"] != "incorrect":
            if row["status"] == "correct" and row["comment"].startswith(("Шаг проверен", "Ошибок в этом шаге")):
                row["comment"] = ""
            continue

        reason, corrections = _family_corrections(row["text"], state)
        is_part_b = bool(re.search(r"(?:^|\s)(?:б|b)\s*\)|ответ\s*:", row["text"], re.IGNORECASE))

        if corrections:
            row["comment"] = reason or "Ошибка в общем решении."
            row["correction"] = "\n".join(corrections)
        elif is_part_b and part_b_present and correct_b:
            row["comment"] = "Неверный набор корней пункта б."
            row["correction"] = correct_b
        else:
            row["comment"] = _specific_reason(row["comment"])
                                                                              
                                                                             
            row["correction"] = _next_verified_formula(rows, i)

        if row["correction"]:
            row["comment"] = f"{row['comment']} Правильно: {row['correction']}"

    return rows


def _first_incorrect_reason(step_checks: list[dict[str, str]]) -> str:
    for row in step_checks:
        if row.get("status") == "incorrect":
            return str(row.get("comment", "")).split(" Правильно:", 1)[0].strip()
    return ""


def _friendly_part_a(state: ReviewState, steps: list[dict[str, str]]) -> str:
    status = str(state.get("reviewer_part_a_status") or state.get("grader_part_a_status") or "").strip()
    if state.get("reviewer_part_a_equivalent") is True or status == "correct":
        return "Верно."
    if status == "missing":
        return "Пункт а не выполнен."
    if status == "computation_error_only" or str(state.get("reviewer_error_class") or state.get("grader_error_class")) == "computation_error":
        return "Вычислительная ошибка."
    return _first_incorrect_reason(steps) or "Ошибка в общем решении."


def _friendly_part_b(state: ReviewState, present: bool) -> str:
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


def build_compact_report_node(state: ReviewState) -> dict[str, Any]:

    if state.get("status") != "REVIEWED":
        return {}

    final_score = int(state.get("final_score", 0))
    max_score = int(state.get("max_score", state.get("task_max_score", 2)))
    step_checks = _display_step_checks(state)
    part_b_present = _part_b_present(state)
    part_a_comment = _friendly_part_a(state, step_checks)
    part_b_comment = _friendly_part_b(state, part_b_present)

    if final_score == max_score:
        summary = "Решение верное."
    elif part_a_comment != "Верно.":
        summary = part_a_comment
    elif not part_b_present:
        summary = "Пункт б не выполнен."
    else:
        summary = part_b_comment

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
        "expert_comment": summary,
        "correct_answer_part_a": _format_reference_part_a(state),
        "correct_answer_part_b": _format_reference_part_b(state),
        "student_diagram_status": "NOT_ANALYZED_MVP",
        "student_diagram_comment": "Окружность ученика отдельно не распознаётся; справа показан правильный отбор.",
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
