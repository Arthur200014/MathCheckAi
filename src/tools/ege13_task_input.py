from __future__ import annotations

import re


def _normalized_lines(text: str) -> list[str]:
    raw = str(text or "").replace("\\n", "\n").replace("\\newline", "\n")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def infer_task_statement_draft(detected_statement: str, transcript: str) -> tuple[str, str]:
    """Return a human-editable task draft without inventing unseen task content.

    Vision sometimes puts the visible first line of the task into the student
    transcript instead of task_statement. When that happens we may reuse only a
    literal leading equation as a draft for the human confirmation field.

    Important: this function never invents part b, an interval, or instructions.
    Missing task content must still be supplied by the human before grading.
    """
    detected = str(detected_statement or "").strip()
    if detected:
        return detected, "vision"

    for line in _normalized_lines(transcript)[:5]:
        candidate = line.strip()
        if "=" not in candidate:
            continue
        lower = candidate.lower()
        if not any(token in lower for token in ("sin", "cos", "tg", "tan", "sin", "cos")):
            continue
        if re.match(r"^(?:13\s*[.)]?\s*)?[аa]\s*[).:]?", candidate, flags=re.IGNORECASE):
            return candidate, "transcript_leading_equation"

    return "", "empty"


def validate_confirmed_task_statement(task_type: str, statement: str) -> list[str]:
    """Validate task completeness before any expensive Solver/Grader calls.

    For EGE-13 the confirmed task must contain both an equation for part a and
    an interval for part b. This prevents an LLM from guessing a missing
    interval (for example [0; 2π]) when the human confirmed only the equation.
    """
    text = str(statement or "").strip()
    if not text:
        return ["task_statement_empty"]

    if str(task_type or "").strip().lower() != "ege_13":
        return []

    issues: list[str] = []
    if "=" not in text:
        issues.append("part_a_equation_missing")

    # Russian EGE statements normally use [a; b]. Also tolerate ordinary
    # parentheses/brackets around interval endpoints, but require ';' so trig
    # parentheses such as sin(x+π) cannot be mistaken for an interval.
    interval_pattern = re.compile(
        r"[\[(]\s*[^\]\)\n;]+?\s*;\s*[^\]\)\n;]+?\s*[\])]",
        flags=re.IGNORECASE,
    )
    if not interval_pattern.search(text):
        issues.append("part_b_interval_missing")

    return issues


def task_statement_issue_message(issues: list[str]) -> str:
    labels = {
        "task_statement_empty": "условие задания пустое",
        "part_a_equation_missing": "не найдено уравнение пункта а",
        "part_b_interval_missing": "не найден интервал пункта б (например [-3π; -3π/2])",
    }
    readable = [labels.get(item, item) for item in issues]
    return "; ".join(readable)
