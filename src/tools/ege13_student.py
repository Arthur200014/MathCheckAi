from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import sympy as sp

from src.tools.solution_steps import split_solution_step_texts

from src.tools.ege13_reference import (
    _dedupe,
    _enumerate_integer_family,
    _equal,
    _extract_part_a_equation,
    _sympify,
    _verify_family_samples,
)


@dataclass
class StudentAnswerExtraction:
    final_answer_found: bool
    final_part_b_roots: list[str]
    source_text: str
    errors: list[str]


def _extract_pi_tokens(text: str) -> tuple[list[str], list[str]]:
    """Extract explicit pi-valued roots from a compact answer fragment."""
    raw = str(text or "")
    patterns = [
        r"[-+]?\s*\\frac\s*\{[^{}]*(?:\\pi|π)[^{}]*\}\s*\{[^{}]+\}",
        r"[-+]?\s*(?:\d+\s*)?(?:\\pi|π)(?:\s*/\s*\d+)?",
    ]
    matches: list[tuple[int, str]] = []
    for pattern in patterns:
        for m in re.finditer(pattern, raw):
            matches.append((m.start(), m.group(0)))
    matches.sort(key=lambda x: x[0])

    values: list[sp.Expr] = []
    errors: list[str] = []
    occupied: list[tuple[int, int]] = []
    for start, token in sorted(matches, key=lambda x: (x[0], -len(x[1]))):
        end = start + len(token)
        if any(not (end <= a or start >= b) for a, b in occupied):
            continue
        try:
            values.append(_sympify(token))
            occupied.append((start, end))
        except Exception as exc:
            errors.append(f"explicit_final_root_parse_failed:{token}:{exc}")
    values = _dedupe(values)
    return [sp.sstr(v) for v in values], errors


# OCR sometimes turns the Cyrillic "б" into latin b, d or the digit 6.
# For d/6 we only accept a marker at the start of a line, so a normal variable
# inside a formula cannot accidentally create part b.
_PART_B_MARKER_RE = re.compile(
    r"(?im)(?:^|\n|\\newline)\s*(?:б|b|d|6)\s*\)"
)
_INLINE_PART_B_MARKER_RE = re.compile(r"(?i)(?:б|b)\s*\)")
_INDEXED_ROOT_RE = re.compile(r"(?i)x_\{?\d+\}?\s*=")


def extract_ege13_explicit_final_answer(transcript: str) -> StudentAnswerExtraction:
    """Lock the student's explicit final answer for part b, if present.

    A common handwritten form is simply ``Ответ: -13π/4; -3π; -2π`` after the
    student already started part b above. In that case requiring another literal
    ``б)`` after the word ``Ответ`` incorrectly makes a completed part b look
    missing, so the compact root list itself is accepted as student-authored data.
    """
    text = str(transcript or "")
    answer_matches = list(re.finditer(r"(?i)(?:ответ|answer)\s*:??", text))
    if not answer_matches:
        return StudentAnswerExtraction(False, [], "", [])

    answer_match = answer_matches[-1]
    tail = text[answer_match.end():]
    b_matches = list(_INLINE_PART_B_MARKER_RE.finditer(tail))
    if b_matches:
        part_b = tail[b_matches[-1].end():].strip()
        roots, errors = _extract_pi_tokens(part_b)
        if not roots:
            errors.append("explicit_answer_part_b_roots_not_parsed")
        return StudentAnswerExtraction(True, roots, part_b, errors)

    # If part b was visibly introduced before the final word "Ответ", a final
    # compact list of angles belongs to that part. Do not guess when x= families
    # or part-a labels are still present in the answer tail.
    before_answer = text[:answer_match.start()]
    roots, errors = _extract_pi_tokens(tail)
    has_visible_part_b = _PART_B_MARKER_RE.search(before_answer) is not None
    tail_has_part_a = re.search(r"(?i)(?:^|\s)(?:а|a)\s*\)", tail) is not None
    tail_has_family = re.search(r"(?i)\bx\s*=", tail) is not None
    if has_visible_part_b and roots and not tail_has_part_a and not tail_has_family:
        return StudentAnswerExtraction(True, roots, tail.strip(), errors)

    return StudentAnswerExtraction(True, [], tail.strip(), ["explicit_answer_part_b_marker_not_found"])


@dataclass
class StudentMathVerification:
    part_a_equivalent: bool | None
    part_b_matches: bool | None
    results: list[str]
    errors: list[str]
    student_roots: list[str]


def _enumerate_families(
    families: list[dict[str, str]],
    *,
    left: sp.Expr,
    right: sp.Expr,
) -> tuple[list[sp.Expr], list[str]]:
    values: list[sp.Expr] = []
    errors: list[str] = []
    for family in families:
        expression = str(family.get("expression", "")).strip()
        parameter = str(family.get("parameter", "n")).strip() or "n"
        if not expression:
            errors.append("empty_family_expression")
            continue
        roots, errs = _enumerate_integer_family(
            expression,
            parameter,
            left,
            right,
            left_closed=True,
            right_closed=True,
        )
        values.extend(roots)
        errors.extend(errs)
    return _dedupe(values), errors


def _same_set(a: list[sp.Expr], b: list[sp.Expr]) -> bool:
    return len(a) == len(b) and all(any(_equal(x, y) for y in b) for x in a)


def verify_ege13_student_machine_spec(
    student_spec: dict[str, Any] | None,
    *,
    task_statement: str,
    reference_families: list[dict[str, str]],
    expected_roots: list[str],
) -> StudentMathVerification:
    """Deterministically verify machine claims extracted from the student's work."""
    spec = student_spec if isinstance(student_spec, dict) else {}
    results: list[str] = []
    errors: list[str] = []

    try:
        residual = _extract_part_a_equation(task_statement, "x")
        x = sp.Symbol("x", real=True)
        results.append(f"student_check_equation:{sp.sstr(residual)}")
    except Exception as exc:
        return StudentMathVerification(None, None, results, [f"equation_parse_failed:{exc}"], [])

    raw_families = spec.get("general_solution_families", [])
    student_families: list[dict[str, str]] = []
    if isinstance(raw_families, list):
        for item in raw_families:
            if not isinstance(item, dict):
                errors.append("student_family_not_object")
                continue
            expression = str(item.get("expression", "")).strip()
            parameter = str(item.get("parameter", "n")).strip() or "n"
            if expression:
                student_families.append({"expression": expression, "parameter": parameter})
    elif raw_families:
        errors.append("student_families_not_list")

    part_a_equivalent: bool | None = None
    if student_families and reference_families:
        family_invalid = False
        for family in student_families:
            family_errors = _verify_family_samples(
                residual,
                x,
                family["expression"],
                family["parameter"],
            )
            if family_errors:
                family_invalid = True
                errors.extend("student_" + err for err in family_errors)

        window_left, window_right = -12 * sp.pi, 12 * sp.pi
        student_values, student_enum_errors = _enumerate_families(
            student_families, left=window_left, right=window_right
        )
        reference_values, ref_enum_errors = _enumerate_families(
            reference_families, left=window_left, right=window_right
        )
        errors.extend("student_" + err for err in student_enum_errors)
        errors.extend("reference_" + err for err in ref_enum_errors)

        if not student_enum_errors and not ref_enum_errors:
            same = _same_set(student_values, reference_values)
            part_a_equivalent = bool(same and not family_invalid)
            results.append(
                "student_part_a_periodic_set_equivalence:"
                + ("true" if part_a_equivalent else "false")
            )
    elif not student_families:
        results.append("student_part_a_machine_families_missing")

    selected_raw = spec.get("selected_roots", [])
    if not isinstance(selected_raw, list):
        selected_raw = [selected_raw] if selected_raw else []

    selected_values: list[sp.Expr] = []
    for raw in selected_raw:
        if not str(raw).strip():
            continue
        try:
            selected_values.append(_sympify(str(raw)))
        except Exception as exc:
            errors.append(f"student_selected_root_parse_failed:{raw}:{exc}")
    selected_values = _dedupe(selected_values)
    student_roots = [sp.sstr(v) for v in selected_values]

    expected_values: list[sp.Expr] = []
    expected_parse_failed = False
    for raw in expected_roots:
        try:
            expected_values.append(_sympify(str(raw)))
        except Exception as exc:
            expected_parse_failed = True
            errors.append(f"reference_expected_root_parse_failed:{raw}:{exc}")
    expected_values = _dedupe(expected_values)

    part_b_matches: bool | None
    if expected_parse_failed:
        part_b_matches = None
    elif not selected_values and expected_values:
        part_b_matches = False
        results.append("student_part_b_selected_roots:empty")
    else:
        part_b_matches = _same_set(selected_values, expected_values)
        results.append(
            "student_part_b_roots_match_reference:"
            + ("true" if part_b_matches else "false")
        )

    return StudentMathVerification(
        part_a_equivalent=part_a_equivalent,
        part_b_matches=part_b_matches,
        results=results,
        errors=errors,
        student_roots=student_roots,
    )


@dataclass
class StudentEvidenceExtraction:
    """Machine-readable facts extracted ONLY from the confirmed student transcript."""

    part_a_present: bool
    part_b_present: bool
    general_solution_families: list[dict[str, str]]
    family_sources: list[str]
    selected_roots: list[str]
    selected_root_sources: list[str]
    explicit_final_answer_used: bool
    source: str
    errors: list[str]

    def machine_spec(self) -> dict[str, Any]:
        return {
            "general_solution_families": [
                {"expression": f["expression"], "parameter": f["parameter"]}
                for f in self.general_solution_families
            ],
            "selected_roots": list(self.selected_roots),
        }


_FAMILY_ASSIGNMENT_RE = re.compile(
    r"(?<![_A-Za-z0-9])x\s*=\s*(?P<expr>.*?)"
    r"(?:[,;]\s*|\\[,;]?\s*)"
    r"(?P<param>[A-Za-z])\s*(?:\\in|∈)\s*(?:\\mathbb\s*\{\s*Z\s*\}|ℤ|Z)",
    re.IGNORECASE | re.DOTALL,
)


def _clean_family_expr(expr: str) -> str:
    text = str(expr or "").strip()
    text = re.sub(r"(?:\\quad|\\qquad)\s*$", "", text).strip()
    text = text.rstrip(" ,;\\")
    # Handwritten/OCR school notation usually omits multiplication: nπ, 2nπ.
    # The generic normalizer would turn nπ into the unknown identifier "npi".
    text = re.sub(r"(?i)([A-Za-z0-9_)])\s*(\\pi|π)", r"\1*\2", text)
    return text


def _strip_trailing_parameter_declaration(expr: str, parameter: str) -> str:
    """Remove a shared trailing ``n ∈ Z`` that OCR joined to the family."""
    pattern = (
        rf"\s*[,;]?\s*{re.escape(parameter)}\s*(?:\\in|∈)\s*"
        r"(?:\\mathbb\s*\{\s*Z\s*\}|ℤ|Z)\s*$"
    )
    return re.sub(pattern, "", str(expr or ""), flags=re.IGNORECASE).strip()


def _extract_student_families_from_text(text: str) -> tuple[list[dict[str, str]], list[str], list[str]]:
    families: list[dict[str, str]] = []
    sources: list[str] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()

    for step in split_solution_step_texts(str(text or ""), max_steps=64):
        positions = [m.start() for m in re.finditer(r"(?i)\bx\s*=", step)]
        for idx, pos in enumerate(positions):
            prefix = step[max(0, pos - 12):pos]
            if re.search(r"(?i)(?:sin|cos|tan|tg)\s*$", prefix):
                continue
            next_pos = positions[idx + 1] if idx + 1 < len(positions) else len(step)
            segment = step[pos:next_pos].strip()
            match = re.match(
                r"(?is)^x\s*=\s*(?P<expr>.*?)"
                r"(?:[,;]\s*|\\[,;]?\s*)"
                r"(?P<param>[A-Za-z])\s*(?:\\in|∈)\s*(?:\\mathbb\s*\{\s*Z\s*\}|ℤ|Z)",
                segment,
            )
            if match:
                expr_text = _clean_family_expr(match.group("expr"))
                parameter = match.group("param").strip()
                source = match.group(0).strip()
            else:
                shared = list(re.finditer(
                    r"(?i)([A-Za-z])\s*(?:\\in|∈)\s*(?:\\mathbb\s*\{\s*Z\s*\}|ℤ|Z)",
                    step,
                ))
                if not shared:
                    continue
                parameter = shared[-1].group(1).strip()
                expr_text = re.sub(r"(?is)^x\s*=\s*", "", segment)
                expr_text = _strip_trailing_parameter_declaration(expr_text, parameter)
                expr_text = _clean_family_expr(expr_text)
                expr_text = re.sub(r"[,;]\s*$", "", expr_text).strip()
                # The parameter can touch pi (nπ), so a word-boundary test is too
                # strict for normal handwritten notation. Check it as a symbol.
                if not re.search(rf"(?i)(?<![A-Za-z]){re.escape(parameter)}(?![A-Za-z])", expr_text):
                    continue
                source = segment.strip()
            if not expr_text:
                continue
            symbol = sp.Symbol(parameter, integer=True)
            try:
                parsed = _sympify(expr_text, extra={parameter: symbol})
                canonical = sp.sstr(sp.simplify(parsed))
            except Exception as exc:
                errors.append(f"student_family_parse_failed:{expr_text}:{exc}")
                continue
            key = (canonical, parameter)
            if key in seen:
                continue
            seen.add(key)
            families.append({
                "expression": canonical,
                "parameter": parameter,
                "source_text": source,
            })
            sources.append(source)
    return families, sources, errors


def _parse_last_rhs_root(step: str) -> tuple[list[str], list[str]]:
    if not _INDEXED_ROOT_RE.search(step):
        return [], []
    rhs = step.rsplit("=", 1)[-1].strip().rstrip(".;,")
    roots, errors = _extract_pi_tokens(rhs)
    return roots, errors


def extract_ege13_student_evidence(transcript: str) -> StudentEvidenceExtraction:
    """Extract student-authored mathematical facts without seeing the reference."""
    text = str(transcript or "")
    errors: list[str] = []
    families, family_sources, family_errors = _extract_student_families_from_text(text)
    errors.extend(family_errors)

    part_a_present = bool(re.search(r"(?i)(?:^|\n|\\newline)\s*(?:а|a)\s*\)", text)) or bool(text.strip())
    b_match = _PART_B_MARKER_RE.search(text)
    part_b_present = b_match is not None

    selected_roots: list[str] = []
    selected_root_sources: list[str] = []
    explicit_used = False

    answer_lock = extract_ege13_explicit_final_answer(text)
    if answer_lock.final_answer_found and answer_lock.final_part_b_roots:
        selected_roots = list(answer_lock.final_part_b_roots)
        selected_root_sources = [answer_lock.source_text]
        explicit_used = True
        part_b_present = True
        errors.extend(answer_lock.errors)
    elif part_b_present:
        tail = text[b_match.start():] if b_match else ""
        steps = split_solution_step_texts(tail, max_steps=48)
        indexed_values: list[str] = []
        indexed_sources: list[str] = []
        for step in steps:
            roots, root_errors = _parse_last_rhs_root(step)
            errors.extend(root_errors)
            if roots:
                indexed_values.extend(roots)
                indexed_sources.append(step)

        if indexed_values:
            values: list[sp.Expr] = []
            for raw in indexed_values:
                try:
                    values.append(_sympify(raw))
                except Exception as exc:
                    errors.append(f"student_part_b_root_parse_failed:{raw}:{exc}")
            values = _dedupe(values)
            selected_roots = [sp.sstr(v) for v in values]
            selected_root_sources = indexed_sources
        else:
            compact_candidate: tuple[list[str], str] | None = None
            for step in steps:
                lower = step.lower()
                if any(token in lower for token in ("\\le", "≤", "<", "[", "]")):
                    continue
                if re.search(r"(?i)(?:^|\s)x\s*=", step):
                    continue
                roots, root_errors = _extract_pi_tokens(step)
                errors.extend(root_errors)
                if roots:
                    compact_candidate = (roots, step)
            if compact_candidate:
                roots, source = compact_candidate
                values = []
                for raw in roots:
                    try:
                        values.append(_sympify(raw))
                    except Exception as exc:
                        errors.append(f"student_part_b_root_parse_failed:{raw}:{exc}")
                values = _dedupe(values)
                selected_roots = [sp.sstr(v) for v in values]
                selected_root_sources = [source]

    return StudentEvidenceExtraction(
        part_a_present=part_a_present,
        part_b_present=part_b_present,
        general_solution_families=families,
        family_sources=family_sources,
        selected_roots=selected_roots,
        selected_root_sources=selected_root_sources,
        explicit_final_answer_used=explicit_used,
        source="confirmed_transcript_only",
        errors=errors,
    )


def deterministic_step_overrides_ege13(
    steps: list[dict[str, str]],
    *,
    task_statement: str,
    expected_roots: list[str],
) -> dict[str, dict[str, str]]:
    """Verify high-risk mathematical steps directly from their text."""
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
        sid = str(step.get("step_id", ""))
        text = str(step.get("text", ""))
        if not sid or not text:
            continue
        if _PART_B_MARKER_RE.search("\n" + text):
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
                    "comment": "Записанное семейство содержит значения, не являющиеся корнями исходного уравнения.",
                }
            else:
                overrides[sid] = {
                    "status": "correct",
                    "comment": "Записанное семейство детерминированно проверено подстановкой.",
                }
            continue

        if in_part_b and _INDEXED_ROOT_RE.search(text) and expected_values:
            roots, _ = _parse_last_rhs_root(text)
            if roots:
                parsed = []
                for raw in roots:
                    try:
                        parsed.append(_sympify(raw))
                    except Exception:
                        pass
                if parsed and all(any(_equal(v, exp) for exp in expected_values) for v in parsed):
                    overrides[sid] = {"status": "correct", "comment": "Корень принадлежит проверенному множеству пункта б."}
                else:
                    overrides[sid] = {"status": "incorrect", "comment": "Указанный корень не совпадает с проверенным множеством пункта б."}
                continue

        if not in_part_b and reference_residual is not None and "=" in text:
            lower = text.lower()
            is_branch = (
                re.search(r"(?i)^\s*\\?sin\s*x\s*=", text) is not None
                or "или" in lower
                or "\\text{или}" in lower
            )
            if not is_branch and not families:
                try:
                    residual = _extract_part_a_equation(text, "x")
                    diff = sp.trigsimp(sp.expand_trig(sp.expand(residual - reference_residual)))
                    if diff == 0:
                        overrides[sid] = {
                            "status": "correct",
                            "comment": "Переход детерминированно эквивалентен исходному уравнению.",
                        }
                    else:
                        ratio = None
                        try:
                            ratio = sp.simplify(sp.trigsimp(residual / reference_residual))
                        except Exception:
                            ratio = None
                        if ratio is not None and not ratio.has(x) and ratio != 0:
                            overrides[sid] = {
                                "status": "correct",
                                "comment": "Переход детерминированно эквивалентен исходному уравнению.",
                            }
                        else:
                            overrides[sid] = {
                                "status": "incorrect",
                                "comment": "Этот переход не эквивалентен исходному уравнению.",
                            }
                except Exception:
                    pass

    return overrides
