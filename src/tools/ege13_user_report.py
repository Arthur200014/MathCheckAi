from __future__ import annotations

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
    return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()


def _pi_ratio(expr: sp.Expr) -> sp.Rational | None:
    value = sp.simplify(expr / sp.pi)
    return value if isinstance(value, sp.Rational) else None


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


def _linear_parts(expression: str, parameter: str) -> tuple[sp.Expr, sp.Expr] | None:
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
    return sp.simplify(expr.subs(symbol, 0)), period


def _display_offset(seed: sp.Expr, period: sp.Expr) -> sp.Expr:
    p = _pi_ratio(period)
    a = _pi_ratio(seed)
    if p is None or a is None or p <= 0:
        return sp.simplify(seed)
    shift = sp.floor(a / p + sp.Rational(1, 2))
    return sp.simplify((a - shift * p) * sp.pi)


def _format_family(expression: str, parameter: str = "n") -> LinearFamily | None:
    parts = _linear_parts(expression, parameter)
    if parts is None:
        return None
    seed, period = parts
    shown_seed = _display_offset(seed, period)
    seed_text = _format_pi_multiple(shown_seed)
    period_text = _format_pi_multiple(period)
    rhs = f"{period_text}n" if shown_seed == 0 else f"{seed_text} + {period_text}n"
    rhs = rhs.replace("+ -", "- ")
    return LinearFamily(seed=seed, period=period, display=f"x = {rhs}, n ∈ ℤ")


def _reference_families(state: ReviewState) -> list[LinearFamily]:
    result: list[LinearFamily] = []
    for item in list(state.get("reference_verified_families", []) or []):
        if not isinstance(item, dict):
            continue
        expression = str(item.get("expression", "")).strip()
        parameter = str(item.get("parameter", "n")).strip() or "n"
        family = _format_family(expression, parameter) if expression else None
        if family is None:
            continue
        if not any(_equal(family.seed, old.seed) and _equal(family.period, old.period) for old in result):
            result.append(family)
    return result


def _belongs(value: sp.Expr, family: LinearFamily) -> bool:
    quotient = sp.simplify((value - family.seed) / family.period)
    return quotient.is_integer is True


def _family_equivalent(student: LinearFamily, reference: LinearFamily) -> bool:
    return _equal(student.period, reference.period) and _belongs(student.seed, reference)


def _distance_to_family(value: sp.Expr, family: LinearFamily) -> float:
    try:
        q = float(sp.N((value - family.seed) / family.period, 30))
        return abs(q - round(q)) * abs(float(sp.N(family.period / sp.pi, 30)))
    except Exception:
        return 1e9


def _match_reference_family(student: LinearFamily, refs: list[LinearFamily]) -> LinearFamily | None:
    if not refs:
        return None
    same_seed = [ref for ref in refs if _belongs(student.seed, ref)]
    if same_seed:
        return min(
            same_seed,
            key=lambda ref: abs(float(sp.N((student.period - ref.period) / sp.pi, 30))),
        )
    samples = [sp.simplify(student.seed + k * student.period) for k in (-2, -1, 0, 1, 2)]

    def rank(ref: LinearFamily) -> tuple[int, float]:
        overlap = sum(1 for value in samples if _belongs(value, ref))
        return (-overlap, _distance_to_family(student.seed, ref))

    return min(refs, key=rank)


def _format_reference_part_a(state: ReviewState) -> str:
    refs = _reference_families(state)
    if refs:
        def key(ref: LinearFamily) -> float:
            shown = _display_offset(ref.seed, ref.period)
            try:
                return float(sp.N(shown / sp.pi, 30))
            except Exception:
                return -1e9
        return "\n".join(ref.display for ref in sorted(refs, key=key, reverse=True))
    return _human_math(str(state.get("reference_answer_part_a_verified", "")))


def _parse_roots(values: list[str]) -> list[sp.Expr]:
    out: list[sp.Expr] = []
    for raw in values:
        try:
            value = _sympify(str(raw))
        except Exception:
            continue
        if not any(_equal(value, old) for old in out):
            out.append(value)
    return out


def _format_reference_part_b(state: ReviewState) -> str:
    roots = _parse_roots(list(state.get("reference_expected_roots", []) or []))
    if roots:
        return "; ".join(_format_pi_multiple(root) for root in roots)
    return _human_math(str(state.get("reference_answer_part_b_verified", "")))


def _part_b_present(state: ReviewState) -> bool:
    evidence = state.get("grader_student_evidence", {})
    if isinstance(evidence, dict) and "part_b_present" in evidence:
        return bool(evidence.get("part_b_present"))
    return str(state.get("reviewer_part_b_status") or state.get("grader_part_b_status") or "") != "missing"


def _student_families(state: ReviewState) -> list[tuple[LinearFamily, str]]:
    transcript = str(state.get("confirmed_transcript") or state.get("transcript") or "")
    parsed, sources, _ = _extract_student_families_from_text(transcript)
    result: list[tuple[LinearFamily, str]] = []
    for index, item in enumerate(parsed):
        expression = str(item.get("expression", "")).strip()
        parameter = str(item.get("parameter", "n")).strip() or "n"
        family = _format_family(expression, parameter)
        if family is None:
            continue
        source = str(item.get("source_text") or (sources[index] if index < len(sources) else "") or "").strip()
        source = _human_math(source) or family.display
        result.append((family, source))
    return result


def _family_comments(state: ReviewState) -> list[dict[str, str]]:
    refs = _reference_families(state)
    if not refs:
        return []

    comments: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for student, source in _student_families(state):
        if any(_family_equivalent(student, ref) for ref in refs):
            continue
        match = _match_reference_family(student, refs)
        if match is None:
            continue
        key = (source, match.display)
        if key in seen:
            continue
        seen.add(key)

        same_base = _belongs(student.seed, match)
        period_wrong = same_base and not _equal(student.period, match.period)
        if period_wrong:
            title = "Неверный период в общем решении"
            body = (
                f"Для корня {_format_pi_multiple(student.seed)} период записан неверно. "
                "Из-за этого серия содержит лишние значения."
            )
        else:
            title = "Ошибка в общем решении"
            body = "Одна из серий корней записана неверно."

        comments.append(
            {
                "section": "а",
                "title": title,
                "comment": body,
                "student_fragment": source,
                "correction": match.display,
            }
        )
    return comments


def _part_b_comment(state: ReviewState) -> list[dict[str, str]]:
    if not _part_b_present(state) or state.get("grader_part_b_roots_match") is True:
        return []

    student = _parse_roots(list(state.get("grader_student_selected_roots", []) or []))
    expected = _parse_roots(list(state.get("reference_expected_roots", []) or []))
    if not expected:
        return []

    extra = [value for value in student if not any(_equal(value, target) for target in expected)]
    missing = [value for value in expected if not any(_equal(value, target) for target in student)]
    details: list[str] = []
    if extra:
        label = "Лишний корень" if len(extra) == 1 else "Лишние корни"
        details.append(f"{label}: " + "; ".join(_format_pi_multiple(x) for x in extra) + ".")
    if missing:
        label = "Не хватает корня" if len(missing) == 1 else "Не хватает корней"
        details.append(f"{label}: " + "; ".join(_format_pi_multiple(x) for x in missing) + ".")
    if not details:
        details.append("Итоговый набор корней не совпадает с правильным.")

    return [
        {
            "section": "б",
            "title": "Ошибка в отборе корней",
            "comment": " ".join(details),
            "student_fragment": "; ".join(_format_pi_multiple(x) for x in student),
            "correction": "; ".join(_format_pi_multiple(x) for x in expected),
        }
    ]


def _fallback_expert_comment(state: ReviewState) -> list[dict[str, str]]:
    error_class = str(state.get("reviewer_error_class") or state.get("grader_error_class") or "")
    if error_class == "computation_error":
        return [{
            "section": "а",
            "title": "Вычислительная ошибка",
            "comment": "В вычислениях есть ошибка, но основной способ решения выбран верно.",
            "student_fragment": "",
            "correction": "",
        }]
    if state.get("grader_part_a_equivalent") is False:
        return [{
            "section": "а",
            "title": "Ошибка в общем решении",
            "comment": "Полученное общее решение не задаёт тот же набор корней, что исходное уравнение.",
            "student_fragment": "",
            "correction": _format_reference_part_a(state),
        }]
    return []


def _expert_comments(state: ReviewState) -> list[dict[str, str]]:
    comments = _family_comments(state)
    comments.extend(_part_b_comment(state))
    if not comments:
        comments.extend(_fallback_expert_comment(state))
    return comments[:4]


def _part_a_summary(state: ReviewState, comments: list[dict[str, str]]) -> str:
    status = str(state.get("reviewer_part_a_status") or state.get("grader_part_a_status") or "")
    if state.get("reviewer_part_a_equivalent") is True or status == "correct":
        return "Верно."
    if status == "missing":
        return "Пункт а не выполнен."
    for item in comments:
        if item.get("section") == "а":
            return str(item.get("title") or "Ошибка в пункте а") + "."
    return "Ошибка в пункте а."


def _part_b_summary(state: ReviewState, comments: list[dict[str, str]]) -> str:
    if not _part_b_present(state):
        return "Пункт б не выполнялся."
    status = str(state.get("reviewer_part_b_status") or state.get("grader_part_b_status") or "")
    if state.get("reviewer_part_b_roots_match") is True or status == "correct":
        return "Верно."
    for item in comments:
        if item.get("section") == "б":
            return str(item.get("title") or "Ошибка в пункте б") + "."
    return "Ошибка в пункте б."


def build_user_report_node(state: ReviewState) -> dict[str, Any]:
    """Build the final user-facing report from confirmed work + verified facts.

    The report intentionally does not expose a green/red verdict for every line.
    The student's confirmed solution is shown as one coherent piece of work, and
    only a small number of concrete expert comments are added next to it.
    """
    if state.get("status") != "REVIEWED":
        return {}

    final_score = int(state.get("final_score", 0))
    max_score = int(state.get("max_score", state.get("task_max_score", 2)))
    confirmed = str(state.get("confirmed_transcript") or state.get("transcript") or "")
    comments = _expert_comments(state)
    part_a = _part_a_summary(state, comments)
    part_b = _part_b_summary(state, comments)

    if final_score == max_score:
        summary = "Решение верное."
    elif comments:
        summary = str(comments[0].get("title") or "В решении есть ошибка") + "."
    elif not _part_b_present(state):
        summary = "Пункт б не выполнен."
    else:
        summary = "В решении есть ошибка."

    circle_url = ""
    circle_error = ""
    if state.get("task_type") == "ege_13" and state.get("reference_verification_ok", False):
        try:
            render_verified_trig_circle(
                review_id=str(state.get("review_id", "review")),
                task_statement=str(state.get("task_statement", "")),
                expected_roots=list(state.get("reference_expected_roots", []) or []),
            )
            circle_url = f"/api/reviews/{state.get('review_id')}/report-circle"
        except Exception as exc:
            circle_error = str(exc)

    report: dict[str, Any] = {
        "title": str(state.get("task_title", "Проверка решения")),
        "score": final_score,
        "max_score": max_score,
        "score_text": f"{final_score}/{max_score}",
        "score_label": "Итоговый балл",
        "status_label": "Проверка завершена",
        "confirmed_solution_text": _human_math(confirmed),
        "expert_comments": comments,
        "part_a_comment": part_a,
        "part_b_comment": part_b,
        "part_b_present": _part_b_present(state),
        "expert_comment": summary,
        "correct_answer_part_a": _format_reference_part_a(state),
        "correct_answer_part_b": _format_reference_part_b(state),
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
