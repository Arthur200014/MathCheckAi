from __future__ import annotations

"""Human-readable display formatting for OCR math drafts.

This module is intentionally presentation-only. It never decides whether the
student's mathematics is correct. The confirmed human-readable text is accepted
by the existing tolerant math parsers (π, √, ∈, ℤ, ≤, ≥, superscripts, etc.).
"""

import re

_SUPERSCRIPTS = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
_SUBSCRIPTS = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")


def _group(text: str, start: int) -> tuple[str, int] | None:

    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
    return None


def _simple_atom(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9π√ℤ]+", value.strip()))


def _inline(text: str) -> str:
    out: list[str] = []
    i = 0
    command_map = {
        r"\Leftrightarrow": "⇔",
        r"\Rightarrow": "⇒",
        r"\rightarrow": "→",
        r"\leftarrow": "←",
        r"\leq": "≤",
        r"\geq": "≥",
        r"\neq": "≠",
        r"\approx": "≈",
        r"\cdot": "·",
        r"\times": "×",
        r"\div": "÷",
        r"\pm": "±",
        r"\infty": "∞",
        r"\in": "∈",
        r"\pi": "π",
        r"\sin": "sin",
        r"\cos": "cos",
        r"\tan": "tan",
        r"\tg": "tg",
        r"\ln": "ln",
        r"\log": "log",
    }
    spacing_commands = (r"\quad", r"\qquad", r"\,", r"\;", r"\:", r"\ ")
    drop_commands = (r"\left", r"\right")

    while i < len(text):
        if text.startswith(r"\mathbb", i):
            pos = i + len(r"\mathbb")
            grp = _group(text, pos)
            if grp:
                body, end = grp
                out.append("ℤ" if body.strip() == "Z" else _inline(body))
                i = end
                continue

        if text.startswith(r"\frac", i):
            pos = i + len(r"\frac")
            while pos < len(text) and text[pos].isspace():
                pos += 1
            first = _group(text, pos)
            if first:
                num_raw, pos2 = first
                while pos2 < len(text) and text[pos2].isspace():
                    pos2 += 1
                second = _group(text, pos2)
                if second:
                    den_raw, end = second
                    num, den = _inline(num_raw).strip(), _inline(den_raw).strip()
                    if not _simple_atom(num):
                        num = f"({num})"
                    if not _simple_atom(den):
                        den = f"({den})"
                    out.append(f"{num}/{den}")
                    i = end
                    continue

        if text.startswith(r"\sqrt", i):
            pos = i + len(r"\sqrt")
            while pos < len(text) and text[pos].isspace():
                pos += 1
            grp = _group(text, pos)
            if grp:
                body_raw, end = grp
                body = _inline(body_raw).strip()
                out.append("√" + (body if _simple_atom(body) else f"({body})"))
                i = end
                continue

        if text.startswith(r"\text", i):
            pos = i + len(r"\text")
            while pos < len(text) and text[pos].isspace():
                pos += 1
            grp = _group(text, pos)
            if grp:
                body, end = grp
                out.append(body)
                i = end
                continue

        if text.startswith(r"\begin{cases}", i):
            out.append("\n")
            i += len(r"\begin{cases}")
            continue
        if text.startswith(r"\end{cases}", i):
            out.append("\n")
            i += len(r"\end{cases}")
            continue

        matched = False
        for command in drop_commands:
            if text.startswith(command, i):
                i += len(command)
                matched = True
                break
        if matched:
            continue
        for command in spacing_commands:
            if text.startswith(command, i):
                out.append(" ")
                i += len(command)
                matched = True
                break
        if matched:
            continue
        for command, replacement in command_map.items():
            if text.startswith(command, i):
                out.append(replacement)
                i += len(command)
                matched = True
                break
        if matched:
            continue

        if text.startswith(r"\{", i):
            out.append("{")
            i += 2
            continue
        if text.startswith(r"\}", i):
            out.append("}")
            i += 2
            continue

        if text[i] == "^" and i + 1 < len(text) and text[i + 1] == "{":
            grp = _group(text, i + 1)
            if grp:
                body, end = grp
                converted = _inline(body).strip()
                if converted and all(c in "0123456789+-=()n" for c in converted):
                    out.append(converted.translate(_SUPERSCRIPTS))
                else:
                    out.append("^(" + converted + ")")
                i = end
                continue

        if text[i] == "_" and i + 1 < len(text) and text[i + 1] == "{":
            grp = _group(text, i + 1)
            if grp:
                body, end = grp
                converted = _inline(body).strip()
                if converted and all(c in "0123456789+-=()" for c in converted):
                    out.append(converted.translate(_SUBSCRIPTS))
                else:
                    out.append("_(" + converted + ")")
                i = end
                continue

        if text[i] in "{}":
            i += 1
            continue

        if text[i] == "~":
            out.append(" ")
            i += 1
            continue

                                                                              
        if text[i] == "\\":
            m = re.match(r"\\([A-Za-z]+)", text[i:])
            if m:
                out.append(m.group(1))
                i += len(m.group(0))
                continue

        out.append(text[i])
        i += 1

    return "".join(out)


def latex_to_human_text(value: str) -> str:

    text = str(value or "")
                                                                          
    text = text.replace(r"\n", "\n")
    text = text.replace(r"\newline", "\n")
                                                     
    text = text.replace("\\\\", "\n")
    text = _inline(text)
                                                                                   
    text = re.sub(r"\^2(?![0-9])", "²", text)
    text = re.sub(r"\^3(?![0-9])", "³", text)
    text = re.sub(r"\b(sin|cos|tan|tg)(?=[0-9xπ√])", r"\1 ", text)
    text = re.sub(r"(?<=[0-9)])(?=(?:sin|cos|tan|tg)\b)", " ", text)
    text = re.sub(r"(?<=√[0-9])(?=(?:sin|cos|tan|tg)\b)", " ", text)
                                                                       
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        line = re.sub(r"^a\)", "а)", line, flags=re.IGNORECASE)
        line = re.sub(r"^b\)", "б)", line, flags=re.IGNORECASE)
        if line:
            lines.append(line)
    return "\n".join(lines).strip()
# fix
