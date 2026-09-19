from __future__ import annotations

import re

import sympy as sp

from src.tools.ege13_reference import _dedupe, _equal, _extract_part_a_equation, _sympify, _verify_family_samples
from src.tools.ege13_student import _extract_pi_tokens, _extract_student_families_from_text, _parse_last_rhs_root


# d)/6) are observed OCR variants of handwritten Cyrillic б).
_PART_B_MARKER_RE = re.compile(r"(?i)^\s*(?:б|b|d|6)\s*\)")
_INDEXED_ROOT_RE = re.compile(r"(?i)x_\{?\d+\}?\s*=")


def _equivalent_to_original(candidate: sp.Expr, reference: sp.Expr, x: sp.Symbol) -> bool:
    """Return True only when equivalence is actually proved."""
    try:
        diff = sp.trigsimp(sp.expand_trig(sp.expand(candidate - reference)))
        if diff == 0:
            return True
    except Exception:
        pass

    try:
        ratio = sp.simplify(sp.trigsimp(candidate / reference))
        return bool(ratio is not None and ratio != 0 and not ratio.has(x))
    except Exception:
        return False


def _is_zero_factor_branch(candidate: sp.Expr, reference: sp.Expr, x: sp.Symbol) -> bool:
    """Recognise a valid branch such as sin(x)-1=0 after a product equals zero."""
    try:
        ref = sp.factor(sp.trigsimp(sp.expand_trig(reference)))
        cand = sp.factor(sp.trigsimp(sp.expand_trig(candidate)))
        if cand == 0:
            return False
        quotient = sp.cancel(ref / cand)
        denominator = sp.factor(sp.denom(quotient))
        if denominator != 1:
            return False
        return bool(quotient.has(x))
    except Exception:
        return False


def _same_values(left: list[sp.Expr], right: list[sp.Expr]) -> bool:
    return len(left) == len(right) and all(any(_equal(a, b) for b in right) for a in left)


def deterministic_reasoning_overrides_ege13(
    steps: list[dict[str, str]],
    *,
    task_statement: str,
    expected_roots: list[str],
) -> dict[str, dict[str, str]]:
    """High-confidence deterministic annotations for the semantic grader."""
    overrides: dict[str, dict[str, str]] = {}

    try:
        reference_residual = _extract_part_a_equation(task_statement, "x")
        x = sp.Symbol("x", real=True)
    except Exception:
        reference_residual = None
        x = sp.Symbol("x", real=True)

    expected_values: list[sp.Expr] = []
    for raw in expected_roots:
        try:
            expected_values.append(_sympify(str(raw)))
        except Exception:
            pass
    expected_values = _dedupe(expected_values)

    in_part_b = False
    for step in steps:
        sid = str(step.get("step_id", "")).strip()
        text = str(step.get("text", "")).strip()
        if not sid or not text:
            continue

        if _PART_B_MARKER_RE.search(text):
            in_part_b = True

        families, _, _ = _extract_student_families_from_text(text)
        if families and reference_residual is not None:
            family_errors: list[str] = []
            for family in families:
                family_errors.extend(
                    _verify_family_samples(
                        reference_residual,
                        x,
                        family["expression"],
                        family["parameter"],
                    )
                )
            if family_errors:
                overrides[sid] = {
                    "status": "incorrect",
                    "comment": "В общем решении есть значения, которые не являются корнями исходного уравнения.",
                }
            else:
                overrides[sid] = {
                    "status": "correct",
                    "comment": "Общее решение проверено подстановкой.",
                }
            continue

        if in_part_b and _INDEXED_ROOT_RE.search(text) and expected_values:
            roots, _ = _parse_last_rhs_root(text)
            parsed: list[sp.Expr] = []
            for raw in roots:
                try:
                    parsed.append(_sympify(raw))
                except Exception:
                    pass
            if parsed:
                ok = all(any(_equal(value, expected) for expected in expected_values) for value in parsed)
                overrides[sid] = {
                    "status": "correct" if ok else "incorrect",
                    "comment": "Корень выбран верно." if ok else "Этот корень не входит в правильный набор пункта б.",
                }
            continue

        # A compact line like "-13π/4; -3π; -2π" is also a real part-b answer.
        # Check the whole list against the verified set instead of letting the LLM
        # call a correct list incomplete by mistake. Interval lines are excluded.
        if in_part_b and expected_values:
            lower = text.lower()
            looks_like_interval = any(token in lower for token in ("[", "]", "≤", "\\le", "<"))
            has_family = re.search(r"(?i)\bx\s*=", text) is not None
            if not looks_like_interval and not has_family:
                roots, _ = _extract_pi_tokens(text)
                parsed: list[sp.Expr] = []
                for raw in roots:
                    try:
                        parsed.append(_sympify(raw))
                    except Exception:
                        pass
                parsed = _dedupe(parsed)
                if len(parsed) >= 2:
                    ok = _same_values(parsed, expected_values)
                    overrides[sid] = {
                        "status": "correct" if ok else "incorrect",
                        "comment": (
                            "Набор корней пункта б совпадает с проверенным."
                            if ok
                            else "Набор корней пункта б не совпадает с проверенным."
                        ),
                    }
                    continue

        if not in_part_b and reference_residual is not None and "=" in text and not families:
            try:
                residual = _extract_part_a_equation(text, "x")
            except Exception:
                continue

            if _equivalent_to_original(residual, reference_residual, x):
                overrides[sid] = {
                    "status": "correct",
                    "comment": "Преобразование сохраняет исходное уравнение.",
                }
            elif _is_zero_factor_branch(residual, reference_residual, x):
                overrides[sid] = {
                    "status": "correct",
                    "comment": "Корректная ветвь после разложения произведения на множители.",
                }

    return overrides
