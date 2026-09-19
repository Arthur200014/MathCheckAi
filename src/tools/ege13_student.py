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

_SUBSCRIPT_TRANS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_PARAM = r"[A-Za-z][A-Za-z0-9]*"
_MEMBERSHIP = r"(?:\\in|∈|∊)\s*(?:\\mathbb\s*\{\s*Z\s*\}|ℤ|Z)"
_PART_B_RE = re.compile(r"(?im)(?:^|\n|\\newline)\s*(?:б|b|d|6)\s*(?:\)|\.|:|[-—])(?=\s|$)")
_INLINE_B_RE = re.compile(r"(?i)(?:б|b)\s*(?:\)|\.|:)")
_INDEXED_ROOT_RE = re.compile(r"(?i)x(?:_?\{?\d+\}?|\d+)\s*=")
_ENUM_ROOT_RE = re.compile(r"^\s*(?:\(?\d+\)?|[①②③④⑤⑥])\s*(?:[:.)-])?")


def _normalize(text: str) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = value.translate(_SUBSCRIPT_TRANS)
    value = re.sub(r"([A-Za-z])_\{(\d+)\}", r"\1\2", value)
    value = re.sub(r"([A-Za-z])_(\d+)", r"\1\2", value)
    value = re.sub(r"x_\{(\d+)\}", r"x\1", value, flags=re.I)
    value = re.sub(r"x_(\d+)", r"x\1", value, flags=re.I)
    return value


def _split_parts(text: str) -> tuple[str, str, re.Match[str] | None]:
    value = _normalize(text)
    marker = _PART_B_RE.search(value)
    if marker is None:
        marker = re.search(r"(?i)(?:^|[\s.;])(?:б|b)\s*(?:\)|\.|:)(?=\s|$)", value)
    if marker is None:
        return value, "", None
    return value[:marker.start()].strip(), value[marker.end():].strip(), marker


def _membership_matches(text: str) -> list[re.Match[str]]:
    return list(re.finditer(rf"(?P<param>{_PARAM})\s*{_MEMBERSHIP}", text, flags=re.I))


def _parameter_candidates(expr: str) -> list[str]:
    value = _normalize(expr).replace("\\pi", " ").replace("π", " ").replace("pi", " ")
    ignored = {"x", "sin", "cos", "tan", "tg", "ctg", "sqrt", "frac", "log", "text", "begin", "end", "cases", "mathbb", "z"}
    out: list[str] = []
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9]*\b", value):
        if token.lower() not in ignored and token not in out:
            out.append(token)
    return out


def _clean_family_expr(expr: str, parameter: str) -> str:
    text = _normalize(expr).strip().rstrip(" ,;\\")
    text = re.sub(r"(?:\\quad|\\qquad)\s*$", "", text).strip()
    p = re.escape(parameter)
    text = re.sub(r"(?<=[A-Za-z0-9_)])\s*(?=(?:\\pi|π|\bpi\b))", "*", text)
    text = re.sub(rf"(\\pi|π|\bpi\b)\s*(?={p}(?![A-Za-z0-9]))", r"\1*", text)
    text = re.sub(rf"(?<![A-Za-z0-9])({p})\s*(?=(?:\\pi|π|\bpi\b))", r"\1*", text)
    return text


def _contains_periodic_parameter(text: str) -> bool:
    value = _normalize(text)
    if re.search(rf"{_PARAM}\s*{_MEMBERSHIP}", value, flags=re.I):
        return True
    stripped = value.replace("\\pi", "").replace("π", "").replace("pi", "")
    names = re.findall(r"\b[A-Za-z][A-Za-z0-9]*\b", stripped)
    ignored = {"x", "sin", "cos", "tan", "tg", "sqrt", "frac", "text", "answer"}
    return any(name.lower() not in ignored for name in names)


def _pi_token_has_parameter_neighbor(raw: str, start: int, end: int) -> bool:
    left, right = raw[:start].rstrip(), raw[end:].lstrip()
    return bool((left and re.search(r"[A-Za-z0-9_]$", left)) or (right and re.match(r"[A-Za-z_]", right)))


def _extract_pi_tokens(text: str) -> tuple[list[str], list[str]]:
    raw = _normalize(text).replace("−", "-")
    patterns = [
        r"[-+]?\s*\\frac\s*\{[^{}]*(?:\\pi|π|\bpi\b)[^{}]*\}\s*\{[^{}]+\}",
        r"[-+]?\s*(?:\d+\s*(?:\*|·)?\s*)?(?:\\pi|π|\bpi\b)(?:\s*/\s*\d+)?",
    ]
    matches: list[tuple[int, int, str]] = []
    for pattern in patterns:
        matches.extend((m.start(), m.end(), m.group(0)) for m in re.finditer(pattern, raw, flags=re.I))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    occupied: list[tuple[int, int]] = []
    values: list[sp.Expr] = []
    errors: list[str] = []
    for start, end, token in matches:
        if any(not (end <= a or start >= b) for a, b in occupied) or _pi_token_has_parameter_neighbor(raw, start, end):
            continue
        try:
            values.append(_sympify(token))
            occupied.append((start, end))
        except Exception as exc:
            errors.append(f"explicit_final_root_parse_failed:{token}:{exc}")
    return [sp.sstr(v) for v in _dedupe(values)], errors


@dataclass
class StudentAnswerExtraction:
    final_answer_found: bool
    final_part_b_roots: list[str]
    source_text: str
    errors: list[str]


def extract_ege13_explicit_final_answer(transcript: str) -> StudentAnswerExtraction:
    text = _normalize(transcript)
    matches = list(re.finditer(r"(?i)(?:ответ|answer)\s*:?", text))
    if not matches:
        return StudentAnswerExtraction(False, [], "", [])
    m = matches[-1]
    tail = text[m.end():]
    b_matches = list(_INLINE_B_RE.finditer(tail))
    if b_matches:
        part_b = tail[b_matches[-1].end():].strip()
        roots, errors = _extract_pi_tokens(part_b)
        if not roots:
            errors.append("explicit_answer_part_b_roots_not_parsed")
        return StudentAnswerExtraction(True, roots, part_b, errors)
    before = text[:m.start()]
    roots, errors = _extract_pi_tokens(tail)
    if _PART_B_RE.search(before) and roots and not _contains_periodic_parameter(tail):
        return StudentAnswerExtraction(True, roots, tail.strip(), errors)
    return StudentAnswerExtraction(True, [], tail.strip(), ["explicit_answer_part_b_marker_not_found"])


@dataclass
class StudentMathVerification:
    part_a_equivalent: bool | None
    part_b_matches: bool | None
    results: list[str]
    errors: list[str]
    student_roots: list[str]


def _same_set(a: list[sp.Expr], b: list[sp.Expr]) -> bool:
    return len(a) == len(b) and all(any(_equal(x, y) for y in b) for x in a)


def _enumerate_families(families: list[dict[str, str]], *, left: sp.Expr, right: sp.Expr) -> tuple[list[sp.Expr], list[str]]:
    values: list[sp.Expr] = []
    errors: list[str] = []
    for family in families:
        expression = str(family.get("expression", "")).strip()
        parameter = str(family.get("parameter", "n")).strip() or "n"
        if not expression:
            errors.append("empty_family_expression")
            continue
        roots, errs = _enumerate_integer_family(expression, parameter, left, right, left_closed=True, right_closed=True)
        values.extend(roots)
        errors.extend(errs)
    return _dedupe(values), errors


def verify_ege13_student_machine_spec(student_spec: dict[str, Any] | None, *, task_statement: str, reference_families: list[dict[str, str]], expected_roots: list[str]) -> StudentMathVerification:
    spec = student_spec if isinstance(student_spec, dict) else {}
    results: list[str] = []
    errors: list[str] = []
    try:
        residual = _extract_part_a_equation(task_statement, "x")
        x = sp.Symbol("x", real=True)
        results.append(f"student_check_equation:{sp.sstr(residual)}")
    except Exception as exc:
        return StudentMathVerification(None, None, results, [f"equation_parse_failed:{exc}"], [])

    student_families: list[dict[str, str]] = []
    raw_families = spec.get("general_solution_families", [])
    if isinstance(raw_families, list):
        for item in raw_families:
            if isinstance(item, dict) and str(item.get("expression", "")).strip():
                student_families.append({"expression": str(item["expression"]).strip(), "parameter": str(item.get("parameter", "n")).strip() or "n"})
            elif not isinstance(item, dict):
                errors.append("student_family_not_object")
    elif raw_families:
        errors.append("student_families_not_list")

    part_a_equivalent: bool | None = None
    if student_families and reference_families:
        invalid = False
        for family in student_families:
            family_errors = _verify_family_samples(residual, x, family["expression"], family["parameter"])
            if family_errors:
                invalid = True
                errors.extend("student_" + err for err in family_errors)
        svals, serr = _enumerate_families(student_families, left=-12 * sp.pi, right=12 * sp.pi)
        rvals, rerr = _enumerate_families(reference_families, left=-12 * sp.pi, right=12 * sp.pi)
        errors.extend("student_" + err for err in serr)
        errors.extend("reference_" + err for err in rerr)
        if not serr and not rerr:
            part_a_equivalent = bool(_same_set(svals, rvals) and not invalid)
            results.append("student_part_a_periodic_set_equivalence:" + str(part_a_equivalent).lower())
    elif not student_families:
        results.append("student_part_a_machine_families_missing")

    selected_values: list[sp.Expr] = []
    selected_raw = spec.get("selected_roots", [])
    if not isinstance(selected_raw, list):
        selected_raw = [selected_raw] if selected_raw else []
    for raw in selected_raw:
        if str(raw).strip():
            try:
                selected_values.append(_sympify(str(raw)))
            except Exception as exc:
                errors.append(f"student_selected_root_parse_failed:{raw}:{exc}")
    selected_values = _dedupe(selected_values)
    expected_values: list[sp.Expr] = []
    expected_bad = False
    for raw in expected_roots:
        try:
            expected_values.append(_sympify(str(raw)))
        except Exception as exc:
            expected_bad = True
            errors.append(f"reference_expected_root_parse_failed:{raw}:{exc}")
    expected_values = _dedupe(expected_values)
    if expected_bad:
        part_b_matches: bool | None = None
    elif not selected_values and expected_values:
        part_b_matches = False
        results.append("student_part_b_selected_roots:empty")
    else:
        part_b_matches = _same_set(selected_values, expected_values)
        results.append("student_part_b_roots_match_reference:" + str(part_b_matches).lower())
    return StudentMathVerification(part_a_equivalent, part_b_matches, results, errors, [sp.sstr(v) for v in selected_values])


@dataclass
class StudentEvidenceExtraction:
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
            "general_solution_families": [{"expression": f["expression"], "parameter": f["parameter"]} for f in self.general_solution_families],
            "selected_roots": list(self.selected_roots),
        }


def _extract_student_families_from_text(text: str) -> tuple[list[dict[str, str]], list[str], list[str]]:
    normalized = _normalize(text)
    families: list[dict[str, str]] = []
    sources: list[str] = []
    errors: list[str] = []
    seen_sets: list[list[sp.Expr]] = []
    for step in split_solution_step_texts(normalized, max_steps=96):
        positions = [m.start() for m in re.finditer(r"(?i)\bx\s*=", step)]
        memberships = _membership_matches(step)
        for idx, pos in enumerate(positions):
            prefix = step[max(0, pos - 12):pos]
            if re.search(r"(?i)(?:sin|cos|tan|tg)\s*$", prefix):
                continue
            end = positions[idx + 1] if idx + 1 < len(positions) else len(step)
            segment = step[pos:end].strip()
            rhs = re.sub(r"(?is)^x\s*=\s*", "", segment, count=1).strip()
            local = _membership_matches(rhs)
            parameter = ""
            expr_text = rhs
            if local:
                parameter = local[0].group("param")
                expr_text = rhs[:local[0].start()].rstrip(" ,;")
            else:
                candidates = _parameter_candidates(rhs)
                for member in memberships:
                    if member.group("param") in candidates:
                        parameter = member.group("param")
                        break
                if not parameter and len(candidates) == 1:
                    parameter = candidates[0]
                if not parameter and len(memberships) == 1:
                    parameter = memberships[0].group("param")
                expr_text = re.split(r"[;\n]", rhs, maxsplit=1)[0].strip(" ,")
            if not parameter or parameter.lower() in {"x", "pi", "sin", "cos", "tan", "tg"}:
                continue
            expr_text = _clean_family_expr(expr_text, parameter)
            symbol = sp.Symbol(parameter, integer=True)
            try:
                parsed = _sympify(expr_text, extra={parameter: symbol})
            except Exception as exc:
                errors.append(f"student_family_parse_failed:{expr_text}:{exc}")
                continue
            if symbol not in parsed.free_symbols:
                continue
            canonical = sp.sstr(sp.simplify(parsed))
            sample_set = _dedupe([sp.simplify(parsed.subs(symbol, i)) for i in range(-6, 7)])
            if any(_same_set(sample_set, old) for old in seen_sets):
                continue
            seen_sets.append(sample_set)
            families.append({"expression": canonical, "parameter": parameter, "source_text": segment})
            sources.append(segment)
    return families, sources, errors


def _parse_result_root(step: str) -> tuple[list[str], list[str]]:
    value = _normalize(step).strip()
    indexed = _INDEXED_ROOT_RE.search(value) is not None
    enumerated = _ENUM_ROOT_RE.search(value) is not None
    direct = re.match(r"(?i)^\s*x(?:\d+)?\s*=", value) is not None and not _contains_periodic_parameter(value)
    if not (indexed or enumerated or direct) or "=" not in value:
        return [], []
    return _extract_pi_tokens(value.rsplit("=", 1)[-1].strip().rstrip(".;,"))


def _parse_part_b_roots(part_b: str) -> tuple[list[str], list[str], list[str]]:
    values: list[sp.Expr] = []
    sources: list[str] = []
    errors: list[str] = []
    steps = split_solution_step_texts(part_b, max_steps=96)
    for step in steps:
        roots, errs = _parse_result_root(step)
        errors.extend(errs)
        if roots:
            sources.append(step)
            for raw in roots:
                try:
                    values.append(_sympify(raw))
                except Exception as exc:
                    errors.append(f"student_part_b_root_parse_failed:{raw}:{exc}")
    if values:
        return [sp.sstr(v) for v in _dedupe(values)], sources, errors
    compact: tuple[list[str], str] | None = None
    for step in steps:
        if any(t in step.lower() for t in ("\\le", "≤", "<", "[", "]")) or _contains_periodic_parameter(step):
            continue
        roots, errs = _extract_pi_tokens(step)
        errors.extend(errs)
        if roots:
            compact = roots, step
    if compact:
        roots, source = compact
        parsed: list[sp.Expr] = []
        for raw in roots:
            try:
                parsed.append(_sympify(raw))
            except Exception as exc:
                errors.append(f"student_part_b_root_parse_failed:{raw}:{exc}")
        return [sp.sstr(v) for v in _dedupe(parsed)], [source], errors
    return [], [], errors


def extract_ege13_student_evidence(transcript: str) -> StudentEvidenceExtraction:
    text = _normalize(transcript)
    part_a, part_b, marker = _split_parts(text)
    families, family_sources, errors = _extract_student_families_from_text(part_a)
    roots: list[str] = []
    root_sources: list[str] = []
    explicit = False
    locked = extract_ege13_explicit_final_answer(text)
    if locked.final_answer_found and locked.final_part_b_roots:
        roots = list(locked.final_part_b_roots)
        root_sources = [locked.source_text]
        explicit = True
        errors.extend(locked.errors)
        part_b_present = True
    else:
        part_b_present = marker is not None
        if part_b_present:
            roots, root_sources, root_errors = _parse_part_b_roots(part_b)
            errors.extend(root_errors)
    return StudentEvidenceExtraction(bool(part_a.strip()), part_b_present, families, family_sources, roots, root_sources, explicit, "confirmed_transcript_only", errors)


def deterministic_step_overrides_ege13(steps: list[dict[str, str]], *, task_statement: str, expected_roots: list[str]) -> dict[str, dict[str, str]]:
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
        sid, text = str(step.get("step_id", "")), str(step.get("text", ""))
        if not sid or not text:
            continue
        if _PART_B_RE.search("\n" + _normalize(text)):
            in_part_b = True
        families, _, _ = _extract_student_families_from_text(text)
        if families and reference_residual is not None:
            family_errors: list[str] = []
            for family in families:
                family_errors.extend(_verify_family_samples(reference_residual, x, family["expression"], family["parameter"]))
            overrides[sid] = {
                "status": "incorrect" if family_errors else "correct",
                "comment": "Записанное семейство содержит значения, не являющиеся корнями исходного уравнения." if family_errors else "Записанное семейство детерминированно проверено подстановкой.",
            }
            continue
        if in_part_b and expected_values:
            roots, _ = _parse_result_root(text)
            if roots:
                parsed: list[sp.Expr] = []
                for raw in roots:
                    try:
                        parsed.append(_sympify(raw))
                    except Exception:
                        pass
                good = bool(parsed) and all(any(_equal(v, exp) for exp in expected_values) for v in parsed)
                overrides[sid] = {
                    "status": "correct" if good else "incorrect",
                    "comment": "Корень принадлежит проверенному множеству пункта б." if good else "Указанный корень не совпадает с проверенным множеством пункта б.",
                }
                continue
        if not in_part_b and reference_residual is not None and "=" in text and not families:
            lower = text.lower()
            if re.search(r"(?i)^\s*\\?sin\s*x\s*=", text) or "или" in lower or "\\text{или}" in lower:
                continue
            try:
                residual = _extract_part_a_equation(text, "x")
                diff = sp.trigsimp(sp.expand_trig(sp.expand(residual - reference_residual)))
                equivalent = diff == 0
                if not equivalent:
                    try:
                        ratio = sp.simplify(sp.trigsimp(residual / reference_residual))
                        equivalent = ratio is not None and not ratio.has(x) and ratio != 0
                    except Exception:
                        pass
                overrides[sid] = {
                    "status": "correct" if equivalent else "incorrect",
                    "comment": "Переход детерминированно эквивалентен исходному уравнению." if equivalent else "Этот переход не эквивалентен исходному уравнению.",
                }
            except Exception:
                pass
    return overrides
