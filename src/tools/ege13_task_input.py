from __future__ import annotations

import re


def _normalized_lines(text: str) -> list[str]:
    raw = str(text or "").replace("\\n", "\n").replace("\\newline", "\n")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _strip_solution_prefix(line: str) -> str:
    text = str(line or "").strip()
    text = re.sub(r"^\s*(?:задание\s*)?(?:№\s*)?13(?:\.\d+)?\s*[:.\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*[аa]\s*(?:\)|\.|:)\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


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
        if any(token in lower for token in ("sin", "cos", "tg", "tan", "\\sin", "\\cos")):
            return candidate, "student_leading_equation"

    # Backward-compatible fallback: if Vision really saw an explicit printed
    # task statement, use its first equation only.
    for line in _normalized_lines(detected_statement)[:8]:
        candidate = _strip_solution_prefix(line)
        if "=" in candidate:
            return candidate, "vision_task_statement"

    return "", "empty"


def extract_interval_draft(transcript: str, detected_statement: str = "") -> tuple[str, str]:
    """Extract a visibly written interval if one exists; otherwise return empty.

    Never infer an interval from roots or from a model's reference solution.
    """
    combined = "\n".join([str(transcript or ""), str(detected_statement or "")])
    normalized = combined.replace("\\left", "").replace("\\right", "")
    # Standard EGE notation: [a; b], (a; b), [a; b), ...
    match = re.search(r"([\[(]\s*[^\]\)\n;]+?\s*;\s*[^\]\)\n;]+?\s*[\])])", normalized)
    if match:
        return match.group(1).strip(), "visible_interval"

    # Tolerate a chained inequality typed by the human / OCR: a <= x <= b.
    match = re.search(
        r"([^\n]+?)\s*(?:<=|≤)\s*x\s*(?:<=|≤)\s*([^\n]+)",
        normalized,
        flags=re.IGNORECASE,
    )
    if match:
        left = match.group(1).strip(" ,.;:")
        right = match.group(2).strip(" ,.;:")
        if left and right:
            return f"[{left}; {right}]", "visible_inequality"

    return "", "empty"


def normalize_interval_input(interval: str) -> str:
    """Normalize a human-friendly interval to bracket form without changing endpoints.

    Accepted examples:
      -3π; -3π/2
      [-3π; -3π/2]
      (-3pi; -3pi/2]
    """
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
    if not iv:
        issues.append("part_b_interval_missing")
    elif not re.fullmatch(r"[\[(]\s*[^\]\)\n;]+?\s*;\s*[^\]\)\n;]+?\s*[\])]", iv):
        issues.append("part_b_interval_invalid")
    return issues


def task_fields_issue_message(issues: list[str]) -> str:
    labels = {
        "task_equation_empty": "не найдено исходное уравнение",
        "task_equation_missing_equals": "в исходном уравнении нет знака =",
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
