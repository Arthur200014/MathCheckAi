from __future__ import annotations

import re
from dataclasses import dataclass


def _normalized_lines(text: str) -> list[str]:
    # Order matters: ``\newline`` starts with ``\n``.
    raw = str(text or "").replace(r"\newline", "\n").replace(r"\n", "\n")
    raw = raw.replace(r"\\", "\n")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _strip_solution_prefix(line: str) -> str:
    text = str(line or "").strip()
    text = re.sub(
        r"^\s*(?:задание\s*)?(?:№\s*)?13(?:\.\d+)?\s*[:.\-]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^\s*[аa]\s*(?:\)|\.|:)\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _strip_part_b_prefix(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^\s*(?:ответ\s*:\s*)?(?:б|b)\s*(?:\)|\.|:)\s*", "", value, flags=re.IGNORECASE)
    return value.strip()


def _contains_pi(text: str) -> bool:
    return bool(re.search(r"(?:π|\\pi\b|\bpi\b)", str(text or ""), flags=re.IGNORECASE))


def _contains_integer_parameter(text: str) -> bool:
    return bool(
        re.search(
            r"(?:\b[nkm]\b|[nkm]\s*(?:∈|\\in)\s*(?:ℤ|Z|\\mathbb\s*\{\s*Z\s*\}))",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _normalize_inequality_text(text: str) -> str:
    value = str(text or "")
    value = value.replace(r"\left", "").replace(r"\right", "")
    value = value.replace(r"\leq", "≤").replace(r"\le", "≤")
    value = value.replace("<=", "≤")
    value = value.replace(r"\pi", "π")
    return value


def _strip_operation_note(text: str) -> str:
    """Drop a handwritten operation note after the right boundary.

    Examples: ``-3π/2 /:π``, ``-3π/2 | :π``.  We remove only a trailing
    operation annotation; mathematical division inside the endpoint is kept.
    """
    value = str(text or "").strip()
    value = re.sub(r"\s+(?:/|:|\|)\s*:?\s*(?:π|pi)\s*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+\|\s*.*$", "", value)
    return value.strip(" ,.;:")


@dataclass(frozen=True)
class _ChainCandidate:
    left: str
    middle: str
    right: str
    score: int
    index: int
    after_part_b: bool


def _extract_chained_interval(text: str) -> tuple[str, str]:
    """Recover the task interval from the student's visible part-b selection work.

    This does *not* solve the task or infer bounds from final roots.  It reads a
    bound pair the student actually wrote while substituting a general solution
    into the task interval, e.g. ``-3π ≤ π/2 + 2πn ≤ -3π/2``.

    Selection is structural rather than task-specific:
    - prefer inequalities in the part-b region;
    - prefer the angle-scale line (π/x/family still visible) over inequalities
      obtained after dividing by π;
    - prefer boundary pairs repeated across several solution branches.
    """
    lines = _normalized_lines(_normalize_inequality_text(text))
    candidates: list[_ChainCandidate] = []
    in_part_b = False

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if re.match(r"^\s*(?:ответ\s*:\s*)?(?:б|b)\s*(?:\)|\.|:)", line, flags=re.IGNORECASE):
            in_part_b = True

        candidate_line = _strip_part_b_prefix(line)
        parts = [part.strip() for part in re.split(r"\s*≤\s*", candidate_line)]
        if len(parts) < 3:
            continue
        left, middle = parts[0], parts[1]
        right = _strip_operation_note(parts[2])
        if not left or not middle or not right:
            continue

        score = 0
        if in_part_b:
            score += 8
        if _contains_pi(left):
            score += 4
        if _contains_pi(right):
            score += 4
        if _contains_pi(middle):
            score += 5
        if re.search(r"(?<![A-Za-zА-Яа-я0-9_])x(?![A-Za-zА-Яа-я0-9_])", middle):
            score += 6
        if _contains_integer_parameter(middle):
            score += 3
        if re.search(r"\s+(?:/|:|\|)\s*:?\s*(?:π|pi)\s*$", parts[2], flags=re.IGNORECASE):
            score += 2
        if not (_contains_pi(left) or _contains_pi(right) or _contains_pi(middle)):
            score -= 8

        candidates.append(_ChainCandidate(left, middle, right, score, index, in_part_b))

    if not candidates:
        return "", "empty"

    pair_counts: dict[tuple[str, str], int] = {}
    for item in candidates:
        key = (re.sub(r"\s+", "", item.left), re.sub(r"\s+", "", item.right))
        pair_counts[key] = pair_counts.get(key, 0) + 1

    def rank(item: _ChainCandidate) -> tuple[int, int]:
        key = (re.sub(r"\s+", "", item.left), re.sub(r"\s+", "", item.right))
        repetition_bonus = min(pair_counts.get(key, 1) - 1, 3) * 4
        return item.score + repetition_bonus, -item.index

    best = max(candidates, key=rank)
    if not (
        _contains_pi(best.left)
        or _contains_pi(best.right)
        or _contains_pi(best.middle)
        or re.search(r"(?<![A-Za-zА-Яа-я0-9_])x(?![A-Za-zА-Яа-я0-9_])", best.middle)
    ):
        return "", "empty"

    return f"[{best.left}; {best.right}]", "visible_selection_inequality"


def extract_task_equation_draft(transcript: str, detected_statement: str = "") -> tuple[str, str]:
    """Extract the task equation from the student's visible work.

    Product rule for EGE-13: the uploaded photo normally contains the student's
    solution, not the printed task. Students rewrite the source equation at the
    beginning, so that literal first equation is the primary task-equation draft.

    We never solve, simplify or repair the equation here.
    """
    for line in _normalized_lines(transcript)[:8]:
        candidate = _strip_solution_prefix(line)
        if "=" not in candidate:
            continue
        lower = candidate.lower()
        if any(token in lower for token in ("sin", "cos", "tg", "tan", r"\sin", r"\cos")):
            return candidate, "student_leading_equation"

    for line in _normalized_lines(detected_statement)[:8]:
        candidate = _strip_solution_prefix(line)
        if "=" in candidate:
            return candidate, "vision_task_statement"

    return "", "empty"


def extract_interval_draft(transcript: str, detected_statement: str = "") -> tuple[str, str]:
    """Extract visible interval evidence; never infer it from roots/reference."""
    combined = "\n".join([str(transcript or ""), str(detected_statement or "")])
    normalized = _normalize_inequality_text(combined)

    match = re.search(r"([\[(]\s*[^\]\)\n;]+?\s*;\s*[^\]\)\n;]+?\s*[\])])", normalized)
    if match:
        return match.group(1).strip(), "visible_interval"

    interval, source = _extract_chained_interval(normalized)
    if interval:
        return interval, source

    return "", "empty"


def normalize_interval_input(interval: str) -> str:
    """Normalize a human-friendly interval to bracket form without changing endpoints."""
    text = str(interval or "").strip()
    if not text:
        return ""
    text = text.replace("；", ";")
    if ";" not in text:
        return text
    if text[0] in "[(" and text[-1] in ")]":
        return text
    return f"[{text}]"


def build_ege13_task_statement(equation: str, interval: str) -> str:
    eq = _strip_solution_prefix(str(equation or "").strip())
    iv = normalize_interval_input(interval)
    if not eq or not iv:
        return ""
    return (
        f"а) Решите уравнение {eq}. "
        f"б) Найдите все корни этого уравнения, принадлежащие отрезку {iv}."
    )


def _has_ambiguous_trig_argument(equation: str) -> bool:
    """Catch OCR/user text like ``sin x (x+π)`` before it reaches SymPy.

    Such text is ambiguous: it may mean ``sin(x+π)`` or the product
    ``sin(x) * (x+π)``.  For EGE-13 we require the user to make that explicit.
    """
    text = str(equation or "")
    trig = r"(?:\\?(?:sin|cos|tan|tg|ctg|cot))"
    return bool(re.search(rf"{trig}\s*x\s*\(", text, flags=re.IGNORECASE))


def validate_task_fields(task_type: str, equation: str, interval: str) -> list[str]:
    if str(task_type or "").strip().lower() != "ege_13":
        return []
    issues: list[str] = []
    eq = str(equation or "").strip()
    iv = normalize_interval_input(interval)
    if not eq:
        issues.append("task_equation_empty")
    elif "=" not in eq:
        issues.append("task_equation_missing_equals")
    elif _has_ambiguous_trig_argument(eq):
        issues.append("task_equation_ambiguous_trig_argument")
    if not iv:
        issues.append("part_b_interval_missing")
    elif not re.fullmatch(r"[\[(]\s*[^\]\)\n;]+?\s*;\s*[^\]\)\n;]+?\s*[\])]", iv):
        issues.append("part_b_interval_invalid")
    return issues


def task_fields_issue_message(issues: list[str]) -> str:
    labels = {
        "task_equation_empty": "не найдено исходное уравнение",
        "task_equation_missing_equals": "в исходном уравнении нет знака =",
        "task_equation_ambiguous_trig_argument": (
            "неоднозначно записан аргумент тригонометрической функции: "
            "например, вместо sin x (x+π) укажи sin(x+π), "
            "а если это умножение — sin x · (x+π)"
        ),
        "part_b_interval_missing": "не указан интервал пункта б",
        "part_b_interval_invalid": "интервал пункта б должен быть записан через ;, например [-3π; -3π/2]",
    }
    return "; ".join(labels.get(item, item) for item in issues)


# Backward-compatible helpers retained for old tests/clients.
def infer_task_statement_draft(detected_statement: str, transcript: str) -> tuple[str, str]:
    equation, source = extract_task_equation_draft(transcript, detected_statement)
    interval, _ = extract_interval_draft(transcript, detected_statement)
    if equation and interval:
        return build_ege13_task_statement(equation, interval), source
    if detected_statement.strip():
        return detected_statement.strip(), "vision"
    if equation:
        return equation, source
    return "", "empty"


def validate_confirmed_task_statement(task_type: str, statement: str) -> list[str]:
    text = str(statement or "").strip()
    if not text:
        return ["task_statement_empty"]
    if str(task_type or "").strip().lower() != "ege_13":
        return []
    issues: list[str] = []
    if "=" not in text:
        issues.append("part_a_equation_missing")
    if not re.search(r"[\[(]\s*[^\]\)\n;]+?\s*;\s*[^\]\)\n;]+?\s*[\])]", text):
        issues.append("part_b_interval_missing")
    return issues


def task_statement_issue_message(issues: list[str]) -> str:
    labels = {
        "task_statement_empty": "условие задания пустое",
        "part_a_equation_missing": "не найдено уравнение пункта а",
        "part_b_interval_missing": "не найден интервал пункта б (например [-3π; -3π/2])",
    }
    return "; ".join(labels.get(item, item) for item in issues)
