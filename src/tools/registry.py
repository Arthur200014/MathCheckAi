from __future__ import annotations

from typing import Any, Callable

import sympy as sp

from src.tools.core import load_criteria, load_student_history, save_report, save_review
from src.tools.ege13_fast_reference import verify_ege13_reference_fast
from src.tools.ege13_reference import _equal, _sympify
from src.tools.ege13_report import render_verified_trig_circle


def verify_expression(expr1: str, expr2: str) -> dict[str, Any]:
    try:
        left = _sympify(expr1)
        right = _sympify(expr2)
        equivalent = bool(sp.simplify(left - right) == 0)
        return {"ok": True, "equivalent": equivalent}
    except Exception as exc:
        return {"ok": False, "equivalent": None, "error": str(exc)}


def verify_roots(residual: str, roots: list[str]) -> dict[str, Any]:
    x = sp.Symbol("x", real=True)
    try:
        expr = _sympify(residual)
        checks = []
        for raw in roots:
            root = _sympify(raw)
            value = sp.simplify(expr.subs(x, root))
            checks.append({"root": raw, "valid": bool(value == 0), "residual": str(value)})
        return {"ok": True, "checks": checks, "all_valid": all(c["valid"] for c in checks)}
    except Exception as exc:
        return {"ok": False, "checks": [], "error": str(exc)}


def render_trig_circle(spec: dict[str, Any]) -> str:
    path = render_verified_trig_circle(
        review_id=str(spec.get("review_id", "tool-preview")),
        task_statement=str(spec.get("task_statement", "")),
        expected_roots=[str(x) for x in spec.get("expected_roots", [])],
    )
    return str(path)


REFERENCE_VERIFIERS: dict[str, Callable[..., Any]] = {
    "verify_ege13_reference": verify_ege13_reference_fast,
}

TOOLS: dict[str, Callable[..., Any]] = {
    "load_criteria": load_criteria,
    "verify_expression": verify_expression,
    "verify_roots": verify_roots,
    "render_trig_circle": render_trig_circle,
    "save_review": save_review,
    "load_student_history": load_student_history,
    "save_report": save_report,
}


def run_reference_verifier(name: str, spec: dict[str, Any], *, task_statement: str = ""):
    try:
        verifier = REFERENCE_VERIFIERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown reference verifier: {name}") from exc
    return verifier(spec, task_statement=task_statement)


def get_tool(name: str) -> Callable[..., Any]:
    try:
        return TOOLS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown tool: {name}") from exc
