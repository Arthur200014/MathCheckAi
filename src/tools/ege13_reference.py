from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


SAFE_LOCALS: dict[str, Any] = {
    "pi": sp.pi,
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "tg": sp.tan,
    "log": sp.log,
    "exp": sp.exp,
}

_TRANSFORMATIONS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)


@dataclass
class ReferenceVerification:
    ok: bool
    status: str
    results: list[str]
    errors: list[str]
    expected_roots: list[str]
    selected_roots: list[str]
    corrected_answer_part_b: str
    equation_source: str
    verified_families: list[dict[str, str]]
    corrected_answer_part_a: str = ""
    solver_fallback_used: bool = False


def _sympify(expr: str, *, extra: dict[str, Any] | None = None) -> sp.Expr:
                                                                             
                                                                            
                                                      
    return _parse_math_expr(str(expr), extra=extra)


def _extract_braced(text: str, start: int) -> tuple[str, int]:

    if start >= len(text) or text[start] != "{":
        raise ValueError("latex_group_expected")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ValueError("latex_group_unclosed")


def _expand_latex_frac(text: str) -> str:

    while "\\frac" in text:
        idx = text.find("\\frac")
        pos = idx + len("\\frac")
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != "{":
                                                                                    
            break
        num, after_num = _extract_braced(text, pos)
        pos = after_num
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != "{":
            break
        den, after_den = _extract_braced(text, pos)
        replacement = f"(({_expand_latex_frac(num)})/({_expand_latex_frac(den)}))"
        text = text[:idx] + replacement + text[after_den:]
    return text


def _expand_latex_sqrt(text: str) -> str:

    while "\\sqrt" in text:
        idx = text.find("\\sqrt")
        pos = idx + len("\\sqrt")
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos < len(text) and text[pos] == "{":
            body, after = _extract_braced(text, pos)
            text = text[:idx] + f"sqrt({_expand_latex_sqrt(body)})" + text[after:]
        else:
                                                       
            m = re.match(r"([0-9]+(?:[.,][0-9]+)?)", text[pos:])
            if not m:
                break
            body = m.group(1)
            text = text[:idx] + f"sqrt({body})" + text[pos + len(body):]
    return text


def _normalize_common_math_text(expr: str) -> str:

    text = str(expr or "")
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    text = text.replace("＝", "=")
    text = text.replace("π", "pi").replace("Π", "pi")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-").replace("‑", "-")
    text = text.replace("·", "*").replace("×", "*").replace("⋅", "*").replace("∙", "*")
    text = text.replace("÷", "/")
    text = text.replace("²", "^2").replace("³", "^3")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)                           

                                                
    text = text.replace("\\left", "").replace("\\right", "")
    text = text.replace("\\cdot", "*").replace("\\times", "*")
    text = text.replace("\\pi", "pi")
    text = text.replace("\\,", " ").replace("\\;", " ").replace("\\!", "")
    for latex_name, plain in (
        ("\\sin", "sin"), ("\\cos", "cos"), ("\\tan", "tan"),
        ("\\tg", "tan"), ("\\ln", "log"), ("\\log", "log"),
    ):
        text = text.replace(latex_name, plain)
    text = _expand_latex_frac(text)
    text = _expand_latex_sqrt(text)
                                           
    text = re.sub(r"log_\{([^{}]+)\}", r"log_\1", text)
    def _latex_power_repl(match: re.Match[str]) -> str:
        body = match.group(1).strip()
        return "^" + body if re.fullmatch(r"[0-9]+", body) else f"^({body})"
    text = re.sub(r"\^\{([^{}]+)\}", _latex_power_repl, text)
                                                                     
    text = text.replace("{", "(").replace("}", ")")

                                                         
    text = re.sub(r"√\s*\(([^()]+)\)", r"sqrt(\1)", text)
    text = re.sub(r"√\s*([0-9]+(?:\.[0-9]+)?)", r"sqrt(\1)", text)

                                                                                
                                                        
    text = re.sub(r"(?i)(sin|cos|tan|tg)(?=x\b)", lambda m: ("tan" if m.group(1).lower() == "tg" else m.group(1).lower()) + " ", text)
    text = re.sub(r"(?i)(sin|cos|tan|tg)(?=\d+x\b)", lambda m: ("tan" if m.group(1).lower() == "tg" else m.group(1).lower()) + " ", text)

    text = re.sub(r"\btg\s*\(", "tan(", text, flags=re.IGNORECASE)
    text = re.sub(r"\btg\b", "tan", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _find_matching_paren(text: str, start: int) -> int:
    if start >= len(text) or text[start] != "(":
        raise ValueError("opening_parenthesis_expected")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unclosed_parenthesis")


def _parenthesize_bare_trig_calls(text: str) -> str:





                                               
    power_pat = re.compile(
        r"(?i)\b(sin|cos|tan)\s*\^\s*([0-9]+)\s*"
        r"([+-]?\s*(?:(?:[0-9]+(?:\.[0-9]+)?(?:\s*[*/]\s*[0-9]+(?:\.[0-9]+)?)?)\s*\*?\s*)?(?:x|pi)(?:\s*/\s*[0-9]+)?)"
    )
    def repl_power(m: re.Match[str]) -> str:
        fn, power, arg = m.group(1).lower(), m.group(2), re.sub(r"\s+", "", m.group(3))
                                                                     
        arg = re.sub(r"(?<=\d)(?=(?:x|pi)\b)", "*", arg)
        return f"({fn}({arg}))^{power}"
    text = power_pat.sub(repl_power, text)

                                                        
    plain_pat = re.compile(
        r"(?i)\b(sin|cos|tan)\s+"
        r"([+-]?\s*(?:(?:[0-9]+(?:\.[0-9]+)?(?:\s*[*/]\s*[0-9]+(?:\.[0-9]+)?)?)\s*\*?\s*)?(?:x|pi)(?:\s*/\s*[0-9]+)?)"
    )
    def repl_plain(m: re.Match[str]) -> str:
        fn, arg = m.group(1).lower(), re.sub(r"\s+", "", m.group(2))
        arg = re.sub(r"(?<=\d)(?=(?:x|pi)\b)", "*", arg)
        return f"{fn}({arg})"
    return plain_pat.sub(repl_plain, text)


def _expand_log_base_calls(text: str) -> str:







    pattern = re.compile(r"log_([^\s\^\(]+|\([^()]+\))(?:\^([0-9]+))?\s*\(", re.IGNORECASE)
    cursor = 0
    while True:
        m = pattern.search(text, cursor)
        if not m:
            break
        open_idx = m.end() - 1
        try:
            close_idx = _find_matching_paren(text, open_idx)
        except ValueError:
            break
        base = m.group(1)
        if base.startswith("(") and base.endswith(")"):
            base = base[1:-1]
        power = int(m.group(2) or "1")
        arg = text[open_idx + 1:close_idx]
        replacement = f"log(({arg}),({base}))"
        if power != 1:
            replacement = f"({replacement})**{power}"
        text = text[:m.start()] + replacement + text[close_idx + 1:]
        cursor = m.start() + len(replacement)
    return text


def _validate_math_identifiers(text: str, *, extra: dict[str, Any] | None = None) -> None:





    allowed = set(SAFE_LOCALS) | {"E"}
    if extra:
        allowed.update(extra.keys())
    identifiers = re.findall(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*", text)
    unknown = sorted({name for name in identifiers if name not in allowed})
    if unknown:
        raise ValueError("unsupported_identifier_in_math_expression:" + ",".join(unknown))


def _parse_math_expr(expr: str, *, extra: dict[str, Any] | None = None) -> sp.Expr:

    text = _normalize_common_math_text(expr)
    text = _parenthesize_bare_trig_calls(text)
    text = _expand_log_base_calls(text)
                                                                          
                                                                   
    text = text.strip(" .;,")
    if not text:
        raise ValueError("empty_math_expression")
    _validate_math_identifiers(text, extra=extra)

    locals_map = dict(SAFE_LOCALS)
    locals_map["E"] = sp.E
    if extra:
        locals_map.update(extra)
    try:
        return parse_expr(
            text,
            local_dict=locals_map,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise ValueError(f"math_expression_parse_failed:{text}:{exc}") from exc


def _split_task_parts(task_statement: str) -> tuple[str, str]:

    text = str(task_statement or "").replace("\u00a0", " ").replace("\u202f", " ").strip()
    if not text:
        raise ValueError("empty_task_statement")

                                                                           
    marker = re.search(r"(?i)(?:^|[\s.;])([бb])\s*(?:\)|\.|:)(?=\s|$)", text)
    if marker:
        return text[:marker.start()].strip(), text[marker.end():].strip()

                                                                          
    marker = re.search(r"(?i)(?:^|[\s.;])[бb]\s+(?=(?:найдите|укажите|отберите)\b)", text)
    if marker:
        return text[:marker.start()].strip(), text[marker.end():].strip()
    return text, ""


def _strip_part_a_instruction(part_a: str) -> str:
    text = part_a.strip()
                                                 
    text = re.sub(r"^\s*(?:задание\s*)?(?:№\s*)?13(?:\.\d+)?\s*[:.\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*[аa]\s*(?:\)|\.|:)\s*", "", text, flags=re.IGNORECASE)
                                                                       
    marker = re.search(
        r"решите\s+(?:данное\s+)?уравнение\s*(?:[:.\-]\s*)?",
        text,
        flags=re.IGNORECASE,
    )
    if marker:
        text = text[marker.end():]
                                                                                
    return text.strip().rstrip(". ")


def _extract_part_a_equation(task_statement: str, variable_name: str) -> sp.Expr:

    part_a, _ = _split_task_parts(task_statement)
    part_a = _strip_part_a_instruction(part_a)
    part_a = part_a.replace("＝", "=")

    if "=" not in part_a:
        raise ValueError("equation_equals_sign_not_found")
    lhs_text, rhs_text = part_a.split("=", 1)

    x = sp.Symbol(variable_name, real=True)
    lhs = _parse_math_expr(lhs_text, extra={variable_name: x})
    rhs = _parse_math_expr(rhs_text, extra={variable_name: x})
    residual = sp.simplify(sp.trigsimp(lhs - rhs))
    if variable_name not in {str(symbol) for symbol in residual.free_symbols}:
        raise ValueError("equation_variable_missing_after_parse")
    return residual


def _split_interval_content(content: str) -> tuple[str, str] | None:
    depth = 0
                                                                             
    for i, ch in enumerate(content):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            return content[:i], content[i + 1:]

                                                                              
                                                                                
    depth = 0
    comma_positions: list[int] = []
    for i, ch in enumerate(content):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            comma_positions.append(i)
    if len(comma_positions) == 1:
        i = comma_positions[0]
        return content[:i], content[i + 1:]
    return None


def _extract_interval_match(part_b: str) -> tuple[str, str, str, str] | None:





    for start, ch in enumerate(part_b):
        if ch not in "[(":
            continue
        closing = "]" if ch == "[" else ")"
        paren_depth = 0
        for end in range(start + 1, len(part_b)):
            cur = part_b[end]
            if cur == "(":
                paren_depth += 1
            elif cur == ")":
                if ch == "(" and paren_depth == 0:
                    content = part_b[start + 1:end]
                    parts = _split_interval_content(content)
                    if parts:
                        return ch, parts[0], parts[1], closing
                    break
                paren_depth = max(0, paren_depth - 1)
            elif cur == closing and ch == "[" and paren_depth == 0:
                content = part_b[start + 1:end]
                parts = _split_interval_content(content)
                if parts:
                    return ch, parts[0], parts[1], closing
                break
    return None


def _extract_part_b_interval(task_statement: str) -> tuple[sp.Expr, sp.Expr, bool, bool]:

    _, part_b = _split_task_parts(task_statement)
    if not part_b:
                                                                                    
        part_b = str(task_statement or "")
                                                                                 
    part_b = _normalize_common_math_text(part_b)

    groups = _extract_interval_match(part_b)
    if not groups:
        raise ValueError("interval_not_found_in_task_statement")

    left_bracket, left_text, right_text, right_bracket = groups
    left = _parse_math_expr(left_text)
    right = _parse_math_expr(right_text)
    if left.free_symbols or right.free_symbols:
        raise ValueError("interval_endpoint_contains_symbols")
    return left, right, left_bracket == "[", right_bracket == "]"


def _equal(a: sp.Expr, b: sp.Expr) -> bool:
    try:
        diff = sp.simplify(sp.trigsimp(a - b))
        if diff == 0:
            return True
        if diff.free_symbols:
            return False
        numeric = complex(sp.N(diff, 30))
        return abs(numeric) < 1e-10
    except Exception:
        return False


def _in_interval(value: sp.Expr, left: sp.Expr, right: sp.Expr, *, left_closed: bool, right_closed: bool) -> bool:
    try:
        v = sp.N(value, 30)
        l = sp.N(left, 30)
        r = sp.N(right, 30)
        lower = bool(v >= l) if left_closed else bool(v > l)
        upper = bool(v <= r) if right_closed else bool(v < r)
        return lower and upper
    except Exception:
        return False


def _dedupe(values: list[sp.Expr]) -> list[sp.Expr]:
    out: list[sp.Expr] = []
    for value in values:
        value = sp.simplify(value)
        if not any(_equal(value, existing) for existing in out):
            out.append(value)
    return sorted(out, key=lambda item: float(sp.N(item)))


def _verify_family_samples(residual: sp.Expr, variable: sp.Symbol, expression: str, parameter: str) -> list[str]:
    p = sp.Symbol(parameter, integer=True)
    try:
        expr = _sympify(expression, extra={parameter: p})
    except Exception as exc:
        return [f"family_parse_failed:{expression}:{exc}"]

    errors: list[str] = []
    for sample in (-3, -2, -1, 0, 1, 2, 3):
        root = sp.simplify(expr.subs(p, sample))
        value = sp.simplify(sp.trigsimp(residual.subs(variable, root)))
        if not _equal(value, sp.Integer(0)):
            errors.append(f"family_root_fails_equation:{expression}:n={sample}:residual={value}")
            break
    return errors


def _enumerate_linear_family(
    expression: str,
    parameter: str,
    left: sp.Expr,
    right: sp.Expr,
    *,
    left_closed: bool,
    right_closed: bool,
) -> tuple[list[sp.Expr], list[str]]:
    p = sp.Symbol(parameter, integer=True)
    try:
        expr = _sympify(expression, extra={parameter: p})
    except Exception as exc:
        return [], [f"family_parse_failed:{expression}:{exc}"]

    slope = sp.simplify(sp.diff(expr, p))
    intercept = sp.simplify(expr.subs(p, 0))
    if p in slope.free_symbols or sp.simplify(expr - (slope * p + intercept)) != 0:
        return [], [f"family_not_linear_in_integer_parameter:{expression}"]
    if slope == 0:
        return [], [f"family_zero_period:{expression}"]

    a = sp.simplify((left - intercept) / slope)
    b = sp.simplify((right - intercept) / slope)
    low_raw, high_raw = (a, b) if float(sp.N(a)) <= float(sp.N(b)) else (b, a)
    low = int(sp.floor(low_raw)) - 1
    high = int(sp.ceiling(high_raw)) + 1
    if high - low > 10000:
        return [], [f"family_range_too_large:{expression}"]

    values: list[sp.Expr] = []
    for n_value in range(low, high + 1):
        root = sp.simplify(expr.subs(p, n_value))
        if _in_interval(root, left, right, left_closed=left_closed, right_closed=right_closed):
            values.append(root)
    return _dedupe(values), []



def _enumerate_integer_family(
    expression: str,
    parameter: str,
    left: sp.Expr,
    right: sp.Expr,
    *,
    left_closed: bool,
    right_closed: bool,
) -> tuple[list[sp.Expr], list[str]]:













    roots, errors = _enumerate_linear_family(
        expression,
        parameter,
        left,
        right,
        left_closed=left_closed,
        right_closed=right_closed,
    )
    if not errors:
        return roots, []

    if not any(err.startswith("family_not_linear_in_integer_parameter:") for err in errors):
        return roots, errors

    p = sp.Symbol(parameter, integer=True)
    try:
        expr = _sympify(expression, extra={parameter: p})
    except Exception as exc:
        return [], [f"family_parse_failed:{expression}:{exc}"]

                                                                              
                                                                       
                                                   
    has_parity_term = any(
        isinstance(power, sp.Pow)
        and _equal(power.base, sp.Integer(-1))
        and p in power.exp.free_symbols
        for power in sp.preorder_traversal(expr)
    )
    if not has_parity_term:
        return [], errors

    q_name = "__q"
    q = sp.Symbol(q_name, integer=True)
    branch_values: list[sp.Expr] = []
    branch_errors: list[str] = []

    for parity, replacement in (("even", 2 * q), ("odd", 2 * q + 1)):
        branch = sp.simplify(expr.subs(p, replacement))
        if p in branch.free_symbols:
            return [], [f"family_parity_split_failed:{expression}"]
        values, errs = _enumerate_linear_family(
            sp.sstr(branch),
            q_name,
            left,
            right,
            left_closed=left_closed,
            right_closed=right_closed,
        )
        if errs:
            branch_errors.extend(f"family_{parity}_branch_{err}" for err in errs)
        branch_values.extend(values)

    if branch_errors:
        return [], branch_errors
    return _dedupe(branch_values), []


def _imageset_to_family(imageset: sp.ImageSet) -> dict[str, str] | None:
    try:
        if imageset.base_set != sp.S.Integers:
            return None
        variables = list(imageset.lamda.variables)
        if len(variables) != 1:
            return None
        source_var = variables[0]
        n = sp.Symbol("n", integer=True)
        expr = sp.simplify(imageset.lamda.expr.subs(source_var, n))
                                                                                    
        slope = sp.simplify(sp.diff(expr, n))
        intercept = sp.simplify(expr.subs(n, 0))
        if n in slope.free_symbols or sp.simplify(expr - (slope * n + intercept)) != 0 or slope == 0:
            return None
        return {"expression": sp.sstr(expr), "parameter": "n"}
    except Exception:
        return None


def _families_from_solution_set(solution_set: sp.Set) -> list[dict[str, str]]:

    items = list(solution_set.args) if isinstance(solution_set, sp.Union) else [solution_set]
    families: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, sp.ImageSet):
            family = _imageset_to_family(item)
            if family:
                families.append(family)
        elif item == sp.S.EmptySet:
            continue
        else:
                                                                                
                                                           
            continue
    return families


def _solve_families_independently(residual: sp.Expr, variable: sp.Symbol) -> tuple[list[dict[str, str]], str]:
    try:
        solution_set = sp.solveset(sp.Eq(residual, 0), variable, domain=sp.S.Reals)
    except Exception as exc:
        return [], f"solveset_error:{exc}"
    families = _families_from_solution_set(solution_set)
    if families:
        return families, f"solveset:{sp.sstr(solution_set)}"
    return [], f"solveset_unsupported_shape:{sp.sstr(solution_set)}"




def _canonicalize_periodic_families(families: list[dict[str, str]]) -> list[dict[str, str]]:









    if len(families) != 2:
        return families
    try:
        n = sp.Symbol("n", integer=True)
        parsed: list[tuple[sp.Expr, sp.Expr]] = []
        for family in families:
            parameter = str(family.get("parameter", "n")) or "n"
            p = sp.Symbol(parameter, integer=True)
            expr = _sympify(family["expression"], extra={parameter: p})
            slope = sp.simplify(sp.diff(expr, p))
            intercept = sp.simplify(expr.subs(p, 0))
            if p in slope.free_symbols or sp.simplify(expr - (slope * p + intercept)) != 0:
                return families
            parsed.append((slope, intercept))

        (s1, a1), (s2, a2) = parsed
        if sp.simplify(s1 - s2) != 0 or s1 == 0:
            return families
        period = sp.simplify(abs(s1))
        half = sp.simplify(period / 2)
        diff = sp.simplify(a2 - a1)
                                                                                
        if not (sp.simplify(abs(diff) - half) == 0 or sp.simplify(sp.Mod(diff, period) - half) == 0):
            return families

        new_period = half
        centered = sp.simplify(sp.Mod(a1 + new_period / 2, new_period) - new_period / 2)
        expr = sp.simplify(centered + new_period * n)
        return [{"expression": sp.sstr(expr), "parameter": "n"}]
    except Exception:
        return families


def _format_part_a(families: list[dict[str, str]]) -> str:
    chunks: list[str] = []
    for family in families:
        parameter = family.get("parameter", "n") or "n"
        p = sp.Symbol(parameter, integer=True)
        try:
            expr = _sympify(family["expression"], extra={parameter: p})
            chunks.append(f"x = {sp.latex(expr)},\\quad {parameter}\\in\\mathbb{{Z}}")
        except Exception:
            chunks.append(f"x = {family.get('expression', '')}, {parameter} in Z")
    return "; ".join(chunks)


def verify_ege13_reference(spec: dict[str, Any] | None, *, task_statement: str = "") -> ReferenceVerification:










    spec = spec if isinstance(spec, dict) else {}
    results: list[str] = []
    discrepancies: list[str] = []

    variable_name = str(spec.get("variable", "x")).strip() or "x"
    x = sp.Symbol(variable_name, real=True)

                                              
    try:
        residual = _extract_part_a_equation(task_statement, variable_name)
        results.append(f"equation_reconstructed_independently:{sp.sstr(residual)}")
    except Exception as exc:
        return ReferenceVerification(
            False,
            "REFERENCE_VERIFICATION_FAILED",
            results,
            [f"task_equation_parse_failed:{exc}"],
            [],
            [],
            "",
            "none",
            [],
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
            [],
            [],
            "",
            "task_statement_independent_parse",
            [],
        )

                                                                             
    deterministic_families, solve_note = _solve_families_independently(residual, x)
    if deterministic_families:
        original_count = len(deterministic_families)
        deterministic_families = _canonicalize_periodic_families(deterministic_families)
        if len(deterministic_families) < original_count:
            results.append("independent_solution_families_canonicalized")
        results.append("independent_sympy_solution_families_available")
        results.append(solve_note)
    else:
        results.append(solve_note)

                                                            
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

                                                                                        
    if deterministic_families:
        authoritative_families = deterministic_families
        fallback_used = not bool(solver_families)
        if not solver_families:
            discrepancies.append("solver_families_missing_or_invalid_used_sympy_fallback")
    elif solver_families:
        authoritative_families = solver_families
        fallback_used = False
        results.append("independent_solveset_unavailable_using_verified_solver_families")
    else:
        return ReferenceVerification(
            False,
            "REFERENCE_VERIFICATION_FAILED",
            results,
            discrepancies + ["no_authoritative_solution_families"],
            [],
            [],
            "",
            "task_statement_independent_parse",
            [],
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
            [],
            [],
            "",
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
        discrepancies.append("solver_machine_spec_unavailable_used_full_sympy_fallback")

    if fallback_used:
        status = "REFERENCE_VERIFIED_SOLVER_FALLBACK"
    elif discrepancies:
        status = "REFERENCE_VERIFIED_WITH_CORRECTION"
    else:
        status = "REFERENCE_VERIFIED"

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
