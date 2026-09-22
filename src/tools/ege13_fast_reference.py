from __future__ import annotations

import time
from typing import Any

import sympy as sp

from src.tools import ege13_reference as _reference_math
from src.tools.ege13_reference import (
    ReferenceVerification,
    _canonicalize_periodic_families,
    _dedupe,
    _enumerate_integer_family,
    _equal,
    _extract_part_a_equation,
    _extract_part_b_interval,
    _format_part_a,
    _in_interval,
    _sympify,
    _verify_family_samples,
)


_reference_math.SAFE_LOCALS.update({
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
})

_TRIG_FUNCS = (sp.sin, sp.cos, sp.tan)


def _center_linear_family(expr: sp.Expr, parameter: sp.Symbol) -> sp.Expr:

    slope = sp.simplify(sp.diff(expr, parameter))
    intercept = sp.simplify(expr.subs(parameter, 0))
    if slope == 0 or parameter in slope.free_symbols:
        return sp.simplify(expr)
    try:
        if float(sp.N(slope)) < 0:
            slope = -slope
    except Exception:
        return sp.simplify(expr)

    period = sp.simplify(abs(slope))
    try:
        centered = sp.simplify(sp.Mod(intercept + period / 2, period) - period / 2)
        if centered.has(sp.Mod):
            centered = intercept
    except Exception:
        centered = intercept
    return sp.simplify(centered + period * parameter)


def _machine_friendly_family(expr: sp.Expr, parameter: sp.Symbol) -> bool:

    if parameter not in expr.free_symbols:
        return False
    other = expr.free_symbols - {parameter}
    if other:
        return False
  
    if expr.has(sp.Mod):
        return False
    return True


def _family_from_angle(
    *,
    angle: sp.Expr,
    angle_period: sp.Expr,
    argument: sp.Expr,
    variable: sp.Symbol,
) -> dict[str, str] | None:

    n = sp.Symbol("n", integer=True)
    slope = sp.simplify(sp.diff(argument, variable))
    intercept = sp.simplify(argument.subs(variable, 0))
    if slope == 0 or variable in slope.free_symbols:
        return None
    if sp.simplify(argument - (slope * variable + intercept)) != 0:
        return None

    expr = sp.simplify((angle - intercept) / slope + (angle_period / slope) * n)
    expr = _center_linear_family(expr, n)
    if not _machine_friendly_family(expr, n):
        return None
    return {"expression": sp.sstr(expr), "parameter": "n"}


def _families_for_trig_value(
    atom: sp.Expr,
    value: sp.Expr,
    variable: sp.Symbol,
) -> tuple[bool, list[dict[str, str]]]:
    fn = atom.func
    argument = atom.args[0]

    if fn in (sp.sin, sp.cos):
        try:
            numeric = float(sp.N(value))
        except Exception:
            return False, []
        if numeric < -1.0 - 1e-10 or numeric > 1.0 + 1e-10:
            return True, []

    if fn == sp.sin:
        alpha = sp.simplify(sp.asin(value))
        candidates = [(alpha, 2 * sp.pi), (sp.pi - alpha, 2 * sp.pi)]
    elif fn == sp.cos:
        alpha = sp.simplify(sp.acos(value))
        candidates = [(alpha, 2 * sp.pi), (-alpha, 2 * sp.pi)]
    elif fn == sp.tan:
        alpha = sp.simplify(sp.atan(value))
        candidates = [(alpha, sp.pi)]
    else:
        return False, []

    families: list[dict[str, str]] = []
    for angle, period in candidates:
        family = _family_from_angle(
            angle=angle,
            angle_period=period,
            argument=argument,
            variable=variable,
        )
        if family is None:
            return False, []
        if family not in families:
            families.append(family)
    return True, families


def _solve_one_trig_atom_factor(
    factor: sp.Expr,
    variable: sp.Symbol,
) -> tuple[bool, list[dict[str, str]]]:
    atoms = sorted(
        [atom for atom in factor.atoms(sp.Function) if atom.func in _TRIG_FUNCS],
        key=sp.sstr,
    )
    if len(atoms) != 1:
        return False, []

    atom = atoms[0]
    u = sp.Symbol("__u", real=True)
    algebraic = sp.simplify(factor.xreplace({atom: u}))
    if variable in algebraic.free_symbols:
        return False, []

    try:
        poly = sp.Poly(algebraic, u)
    except Exception:
        return False, []
    if poly.degree() < 1 or poly.degree() > 4:
        return False, []

    try:
        roots = sp.solve(poly.as_expr(), u)
    except Exception:
        return False, []

    families: list[dict[str, str]] = []
    for root in roots:
        root = sp.simplify(root)
        if root.is_real is False:
            continue
        supported, rows = _families_for_trig_value(atom, root, variable)
        if not supported:
            return False, []
        for row in rows:
            if row not in families:
                families.append(row)
    return True, families


def _solve_half_angle_factor(
    factor: sp.Expr,
    variable: sp.Symbol,
) -> tuple[bool, list[dict[str, str]]]:





    t = sp.Symbol("__t", real=True)
    try:
        expanded = sp.expand_trig(factor.rewrite(sp.sin))
        replaced = expanded.xreplace(
            {
                sp.sin(variable): 2 * t / (1 + t**2),
                sp.cos(variable): (1 - t**2) / (1 + t**2),
            }
        )
    except Exception:
        return False, []

    if variable in replaced.free_symbols:
        return False, []
    if any(atom.args and variable in atom.args[0].free_symbols for atom in replaced.atoms(sp.Function)):
        return False, []

    try:
        numerator = sp.factor(sp.together(replaced).as_numer_denom()[0])
        poly = sp.Poly(numerator, t)
    except Exception:
        return False, []
    if poly.degree() < 1 or poly.degree() > 6:
        return False, []

    try:
        roots = sp.solve(poly.as_expr(), t)
    except Exception:
        return False, []

    n = sp.Symbol("n", integer=True)
    families: list[dict[str, str]] = []
    for root in roots:
        root = sp.simplify(root)
        if root.is_real is False:
            continue
        angle = sp.simplify(sp.trigsimp(2 * sp.atan(root)))
        expr = _center_linear_family(angle + 2 * sp.pi * n, n)
        if not _machine_friendly_family(expr, n):
            return False, []
        row = {"expression": sp.sstr(expr), "parameter": "n"}
        if row not in families:
            families.append(row)

                                                                  
    try:
        at_pi = sp.simplify(sp.trigsimp(factor.subs(variable, sp.pi)))
        if _equal(at_pi, sp.Integer(0)):
            expr = _center_linear_family(sp.pi + 2 * sp.pi * n, n)
            row = {"expression": sp.sstr(expr), "parameter": "n"}
            if row not in families:
                families.append(row)
    except Exception:
        pass

    return True, families


def _fast_exact_trig_families(
    residual: sp.Expr,
    variable: sp.Symbol,
) -> tuple[list[dict[str, str]], str]:

    try:
        transformed = sp.factor(sp.trigsimp(sp.expand_trig(residual)))
    except Exception as exc:
        return [], f"fast_transform_error:{exc}"

    if transformed == 0:
        return [], "fast_transform_identity_unsupported"

    raw_factors = list(transformed.as_ordered_factors()) if isinstance(transformed, sp.Mul) else [transformed]
    families: list[dict[str, str]] = []
    x_factors = 0

    for raw in raw_factors:
        if not raw.has(variable):
            continue
        x_factors += 1
        factor = raw
        if isinstance(raw, sp.Pow) and raw.exp.is_integer and raw.exp.is_positive:
            factor = raw.base

        supported, rows = _solve_one_trig_atom_factor(factor, variable)
        if not supported:
            supported, rows = _solve_half_angle_factor(factor, variable)
        if not supported:
            return [], f"fast_factor_unsupported:{sp.sstr(factor)}"
        for row in rows:
            if row not in families:
                families.append(row)

    if x_factors == 0 or not families:
        return [], f"fast_no_families:{sp.sstr(transformed)}"

                                                                              
    verified: list[dict[str, str]] = []
    for family in families:
        errors = _verify_family_samples(
            residual,
            variable,
            family["expression"],
            family["parameter"],
        )
        if errors:
            return [], "fast_generated_family_failed:" + errors[0]
        verified.append(family)

    verified = _canonicalize_periodic_families(verified)
    return verified, f"fast_exact:{sp.sstr(transformed)}"


def verify_ege13_reference_fast(
    spec: dict[str, Any] | None,
    *,
    task_statement: str = "",
) -> ReferenceVerification:







    started = time.perf_counter()
    spec = spec if isinstance(spec, dict) else {}
    results: list[str] = []
    discrepancies: list[str] = []

    variable_name = str(spec.get("variable", "x")).strip() or "x"
    x = sp.Symbol(variable_name, real=True)

    parse_started = time.perf_counter()
    try:
        residual = _extract_part_a_equation(task_statement, variable_name)
        results.append(f"equation_reconstructed_independently:{sp.sstr(residual)}")
    except Exception as exc:
        return ReferenceVerification(
            False,
            "REFERENCE_VERIFICATION_FAILED",
            results,
            [f"task_equation_parse_failed:{exc}"],
            [], [], "", "none", [],
        )

    try:
        left, right, left_closed, right_closed = _extract_part_b_interval(task_statement)
        if float(sp.N(left)) > float(sp.N(right)):
            left, right = right, left
            left_closed, right_closed = right_closed, left_closed
        results.append(
            "interval_reconstructed_independently:"
            f"{sp.sstr(left)};{sp.sstr(right)};closed={left_closed},{right_closed}"
        )
    except Exception as exc:
        return ReferenceVerification(
            False,
            "REFERENCE_VERIFICATION_FAILED",
            results,
            [f"task_interval_parse_failed:{exc}"],
            [], [], "", "task_statement_independent_parse", [],
        )
    results.append(f"timing_parse_seconds:{time.perf_counter() - parse_started:.4f}")

    solve_started = time.perf_counter()
    deterministic_families, solve_note = _fast_exact_trig_families(residual, x)
    results.append(solve_note)
    results.append(f"timing_fast_sympy_seconds:{time.perf_counter() - solve_started:.4f}")
    if deterministic_families:
        results.append("independent_fast_sympy_solution_families_available")

    solver_started = time.perf_counter()
    solver_families_raw = spec.get("general_solution_families", [])
    solver_families: list[dict[str, str]] = []
    if isinstance(solver_families_raw, list):
        for family in solver_families_raw:
            if not isinstance(family, dict):
                discrepancies.append("solver_invalid_family_object")
                continue
            expression = str(family.get("expression", "")).strip()
            parameter = str(family.get("parameter", "n")).strip() or "n"
            if not expression:
                discrepancies.append("solver_empty_family_expression")
                continue
            family_errors = _verify_family_samples(residual, x, expression, parameter)
            if family_errors:
                discrepancies.extend("solver_" + err for err in family_errors)
            else:
                solver_families.append({"expression": expression, "parameter": parameter})
                results.append(f"solver_family_valid_by_samples:{expression}")
    elif solver_families_raw:
        discrepancies.append("solver_general_solution_families_not_list")
    results.append(f"timing_solver_family_check_seconds:{time.perf_counter() - solver_started:.4f}")

    if deterministic_families:
        authoritative_families = deterministic_families
        fallback_used = not bool(solver_families)
        if not solver_families:
            discrepancies.append("solver_families_missing_or_invalid_used_fast_sympy_fallback")
    elif solver_families:
        authoritative_families = solver_families
        fallback_used = False
        discrepancies.append("fast_exact_solver_unsupported_using_verified_solver_families")
    else:
        return ReferenceVerification(
            False,
            "REFERENCE_VERIFICATION_FAILED",
            results,
            discrepancies + ["no_authoritative_solution_families"],
            [], [], "", "task_statement_independent_parse", [],
        )

    part_b = spec.get("part_b", {})
    selected_raw: list[Any] = []
    if isinstance(part_b, dict):
        selected = part_b.get("selected_roots", [])
        selected_raw = selected if isinstance(selected, list) else [selected]
        if part_b.get("has_interval", False):
            try:
                s_left = _sympify(str(part_b.get("interval_left", "")))
                s_right = _sympify(str(part_b.get("interval_right", "")))
                if float(sp.N(s_left)) > float(sp.N(s_right)):
                    s_left, s_right = s_right, s_left
                if not (_equal(s_left, left) and _equal(s_right, right)):
                    discrepancies.append(
                        "solver_interval_mismatch:"
                        f"solver={sp.sstr(s_left)};{sp.sstr(s_right)}:"
                        f"task={sp.sstr(left)};{sp.sstr(right)}"
                    )
            except Exception as exc:
                discrepancies.append(f"solver_interval_unparseable:{exc}")
    elif part_b:
        discrepancies.append("solver_part_b_not_object")

    enumerate_started = time.perf_counter()
    expected_values: list[sp.Expr] = []
    hard_errors: list[str] = []
    for family in authoritative_families:
        roots, family_errors = _enumerate_integer_family(
            family["expression"],
            family["parameter"],
            left,
            right,
            left_closed=left_closed,
            right_closed=right_closed,
        )
        expected_values.extend(roots)
        hard_errors.extend(family_errors)

    if hard_errors:
        return ReferenceVerification(
            False,
            "REFERENCE_VERIFICATION_FAILED",
            results,
            discrepancies + hard_errors,
            [], [], "",
            "task_statement_independent_parse+sympy",
            authoritative_families,
            _format_part_a(authoritative_families),
            fallback_used,
        )

    expected_values = _dedupe(expected_values)
    expected_roots = [sp.sstr(sp.simplify(value)) for value in expected_values]
    results.append(
        "interval_roots_derived_deterministically:"
        + (",".join(expected_roots) if expected_roots else "empty")
    )
    results.append(f"timing_interval_enumeration_seconds:{time.perf_counter() - enumerate_started:.4f}")

    selected_values: list[sp.Expr] = []
    for raw in selected_raw:
        if str(raw).strip() == "":
            continue
        try:
            value = _sympify(str(raw))
        except Exception as exc:
            discrepancies.append(f"solver_selected_root_parse_failed:{raw}:{exc}")
            continue
        selected_values.append(value)
        if not _in_interval(value, left, right, left_closed=left_closed, right_closed=right_closed):
            discrepancies.append(f"solver_selected_root_outside_interval:{sp.sstr(value)}")
        residual_value = sp.simplify(sp.trigsimp(residual.subs(x, value)))
        if not _equal(residual_value, sp.Integer(0)):
            discrepancies.append(
                f"solver_selected_root_fails_equation:{sp.sstr(value)}:residual={sp.sstr(residual_value)}"
            )

    selected_values = _dedupe(selected_values)
    selected_roots = [sp.sstr(sp.simplify(value)) for value in selected_values]
    missing = [value for value in expected_values if not any(_equal(value, selected) for selected in selected_values)]
    extra = [selected for selected in selected_values if not any(_equal(selected, value) for value in expected_values)]
    if missing:
        discrepancies.append("solver_selected_roots_missing:" + ",".join(sp.sstr(v) for v in missing))
    if extra:
        discrepancies.append("solver_selected_roots_extra:" + ",".join(sp.sstr(v) for v in extra))

    corrected_answer_part_a = _format_part_a(authoritative_families)
    corrected_answer_part_b = "; ".join(sp.latex(value) for value in expected_values)

    if not spec:
        fallback_used = True
        discrepancies.append("solver_machine_spec_unavailable_used_fast_sympy_fallback")

    if fallback_used:
        status = "REFERENCE_VERIFIED_SOLVER_FALLBACK"
    elif discrepancies:
        status = "REFERENCE_VERIFIED_WITH_CORRECTION"
    else:
        status = "REFERENCE_VERIFIED"

    results.append(f"timing_reference_total_seconds:{time.perf_counter() - started:.4f}")
    return ReferenceVerification(
        True,
        status,
        results,
        discrepancies,
        expected_roots,
        selected_roots,
        corrected_answer_part_b,
        "task_statement_independent_parse+sympy",
        authoritative_families,
        corrected_answer_part_a,
        fallback_used,
    )
# fix
