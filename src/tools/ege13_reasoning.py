from __future__ import annotations

import re

import sympy as sp

from src.tools.ege13_reference import _dedupe, _equal, _extract_part_a_equation, _sympify, _verify_family_samples
from src.tools.ege13_student import _extract_student_families_from_text, _parse_last_rhs_root


_PART_B_MARKER_RE = re.compile(r"(?i)(?:б|b)\s*\)")
_INDEXED_ROOT_RE = re.compile(r"(?i)x_\{?\d+\}?\s*=")


def _equivalent_to_original(candidate: sp.Expr, reference: sp.Expr, x: sp.Symbol) -> bool:
    """Return True only when equivalence is actually proved.

    A failure to prove equivalence is deliberately *not* interpreted as an error:
    a student's line may be a branch/case of a factored equation rather than a
    full equation equivalent to the original one.
    """
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
    """Recognise a valid branch such as sin(x)-1=0 after a product equals zero.

    The important distinction is logical: one branch is not equivalent to the
    original equation by itself, but it can still be a perfectly valid factor
    branch. We mark it correct only when the candidate residual is an actual
    symbolic factor of the verified original residual.
    """
    try:
        ref = sp.factor(sp.trigsimp(sp.expand_trig(reference)))
        cand = sp.factor(sp.trigsimp(sp.expand_trig(candidate)))
        if cand == 0:
            return False
        quotient = sp.cancel(ref / cand)
        denominator = sp.factor(sp.denom(quotient))
        if denominator != 1:
            return False
        # A constant quotient would mean full equivalence; branch mode is for a
        # proper factor only.
        return bool(quotient.has(x))
    except Exception:
        return False


def deterministic_reasoning_overrides_ege13(
    steps: list[dict[str, str]],
    *,
    task_statement: str,
    expected_roots: list[str],
) -> dict[str, dict[str, str]]:
    """High-confidence deterministic annotations for the semantic grader.

    Design rule: this layer may override an LLM only when it has a mathematical
    proof. In particular, "not globally equivalent to the original equation" is
    not proof that a line is wrong, because the line may be one branch of a case
    split. This removes the old false-negative pattern for lines like
    ``sin x - 1 = 0`` and ``2 sin x + sqrt(2) = 0`` after factorisation.
    """
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

        # General-solution families remain a high-confidence deterministic check:
        # every produced value must satisfy the verified original equation.
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

        # Explicit roots in part b can be checked directly against the verified
        # root set. This is a genuine yes/no fact and is safe to override.
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

        # Ordinary equation lines before part b are annotated only if correctness
        # is positively proved. Lack of global equivalence is never turned into a
        # red verdict, because a branch equation is intentionally a subset of the
        # original solution set.
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
            # else: deliberately leave the step to the semantic grader. Absence
            # of proof is not evidence of an error.

    return overrides
