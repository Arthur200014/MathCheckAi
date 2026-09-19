from __future__ import annotations

import re

from src.tools.ege13_reference import _extract_part_a_equation, _extract_part_b_interval
from src.tools.ege13_task_input import build_ege13_task_statement, normalize_interval_input, validate_task_fields


def _balanced(text: str, left: str, right: str) -> bool:
    depth = 0
    for ch in str(text or ""):
        if ch == left:
            depth += 1
        elif ch == right:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def validate_ege13_input(equation: str, interval: str, transcript: str = "") -> dict:
    eq = str(equation or "").strip()
    iv = normalize_interval_input(interval)
    solution = str(transcript or "").strip()
    issues: list[dict[str, str]] = []

    labels = {
        "task_equation_empty": "Не найдено исходное уравнение.",
        "task_equation_missing_equals": "В исходном уравнении нет знака =.",
        "task_equation_ambiguous_trig_argument": (
            "Неоднозначный аргумент тригонометрической функции. "
            "Например, напиши sin(x+π), если x+π — аргумент, или sin x · (x+π), если это умножение."
        ),
        "part_b_interval_missing": "Не указан интервал пункта б.",
        "part_b_interval_invalid": "Интервал пункта б запиши через ;, например [-3π; -3π/2].",
    }
    for code in validate_task_fields("ege_13", eq, iv):
        field = "interval" if code.startswith("part_b_") else "equation"
        issues.append({"field": field, "code": code, "message": labels.get(code, code)})

    if eq and eq.count("=") != 1:
        issues.append({"field": "equation", "code": "task_equation_multiple_equals", "message": "В поле исходного уравнения должен быть ровно один знак =."})
    if eq and not _balanced(eq, "(", ")"):
        issues.append({"field": "equation", "code": "task_equation_parentheses", "message": "В исходном уравнении не сходятся круглые скобки."})
    if eq and not _balanced(eq, "[", "]"):
        issues.append({"field": "equation", "code": "task_equation_brackets", "message": "В исходном уравнении не сходятся квадратные скобки."})
    if not solution:
        issues.append({"field": "solution", "code": "solution_empty", "message": "Решение ученика не может быть пустым."})

    statement = build_ege13_task_statement(eq, iv) if eq and iv else ""
    structural_codes = {item["code"] for item in issues}
    can_parse_equation = not structural_codes.intersection({
        "task_equation_empty",
        "task_equation_missing_equals",
        "task_equation_multiple_equals",
        "task_equation_parentheses",
        "task_equation_brackets",
        "task_equation_ambiguous_trig_argument",
    })
    can_parse_interval = not any(code.startswith("part_b_") for code in structural_codes)

    if statement and can_parse_equation:
        try:
            residual = _extract_part_a_equation(statement, "x")
            if not re.search(r"\bx\b", str(residual)):
                issues.append({"field": "equation", "code": "task_equation_no_x", "message": "После разбора уравнения не найдена переменная x. Проверь OCR и запись функций."})
        except Exception as exc:
            issues.append({"field": "equation", "code": "task_equation_unparseable", "message": f"Не получилось однозначно прочитать уравнение: {exc}"})

    if statement and can_parse_interval:
        try:
            left, right, _, _ = _extract_part_b_interval(statement)
            if float(left.evalf()) > float(right.evalf()):
                issues.append({"field": "interval", "code": "part_b_interval_reversed", "message": "Левая граница интервала больше правой. Проверь порядок границ."})
        except Exception as exc:
            issues.append({"field": "interval", "code": "part_b_interval_unparseable", "message": f"Не получилось прочитать границы интервала: {exc}"})

    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in issues:
        key = (item["field"], item["code"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return {
        "ok": not unique,
        "issues": unique,
        "normalized_interval": iv,
        "task_statement": statement,
    }
