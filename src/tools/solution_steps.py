from __future__ import annotations

import re


_PART_B_RE = re.compile(r"^(?:\\text\{\s*)?(?:б\)|b\))(?:\s*\})?", re.IGNORECASE)
_ANSWER_RE = re.compile(r"^(?:\\text\{\s*)?ответ\s*:", re.IGNORECASE)


def _normalise_layout(text: str) -> str:
    """Normalise OCR layout markers without changing mathematical content."""
    value = str(text or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")

    # VLMs may emit either actual newlines or LaTeX/newline escape markers.
    value = re.sub(r"\\newline\b", "\n", value)
    value = value.replace("\\n", "\n")

    # Avoid producing fragments such as literal ``\\text{`` when splitting on
    # section markers. Only unwrap the marker itself; leave all other LaTeX as-is.
    value = re.sub(r"\\text\{\s*([бb]\))\s*\}", r"\1", value, flags=re.IGNORECASE)
    value = re.sub(r"\\text\{\s*(Ответ\s*:)\s*\}", r"\1", value, flags=re.IGNORECASE)

    # In compact confirmed transcripts, transformations were historically joined
    # with \quad. Preserve logical "или" as part of the same mathematical step.
    value = re.sub(
        r"\\quad\s*(\\text\{\s*или\s*\}|или)\s*\\quad",
        r" \1 ",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip()


def _split_section_markers(text: str) -> list[str]:
    """Split before part-b / final-answer markers while keeping marker text."""
    marker = re.compile(
        r"(?=(?<![A-Za-zА-Яа-я0-9_])(?:\\text\{\s*)?(?:б\)|b\)|Ответ\s*:|ответ\s*:))",
        re.IGNORECASE,
    )
    return [part.strip() for part in marker.split(text) if part.strip()]


def _split_answer_part_b(text: str) -> list[str]:
    """Keep a) answer and b) answer separately so answer-lock is report-visible."""
    if not _ANSWER_RE.search(text):
        return [text]
    match = re.search(r"(?:;|\\quad|\s)(?=(?:б\)|b\)))", text, flags=re.IGNORECASE)
    if not match:
        return [text]
    left = text[: match.start()].strip(" ;")
    right = text[match.end() :].strip()
    return [part for part in (left, right) if part]


def _split_part_b_calculations(text: str) -> list[str]:
    """Split independent root-selection calculations, not every algebraic semicolon."""
    if not _PART_B_RE.search(text):
        return [text]

    # After the part marker, semicolons usually separate independent selected-root
    # calculations. Avoid splitting parameter clauses like ``k\\in\\mathbb{Z};``.
    chunks: list[str] = []
    start = 0
    for match in re.finditer(r"(?<!\\);", text):
        left_context = text[max(0, match.start() - 32) : match.start()]
        if re.search(r"(?:k|n)\s*\\in\s*\\mathbb\{Z\}\s*$", left_context):
            continue
        chunks.append(text[start : match.start()].strip())
        start = match.end()
    chunks.append(text[start:].strip())
    return [chunk for chunk in chunks if chunk]



def _is_standalone_noise_fragment(text: str) -> bool:
    """Return True for layout/OCR debris that has no independent math meaning.

    The original transcript is never changed; this only prevents tiny fragments
    such as ``\text{unu}`` or a lone connector from becoming separate report rows.
    """
    value = text.strip()
    lower = value.lower()
    if lower in {"или", r"\text{или}", "or", r"\text{or}", "unu", r"\text{unu}"}:
        return True
    m = re.fullmatch(r"\\text\{\s*([^{}]+?)\s*\}", value, flags=re.IGNORECASE)
    if m:
        inner = m.group(1).strip()
        # A text-only fragment between equations is a connector/OCR artefact, not
        # a mathematical transformation. Longer prose remains visible elsewhere.
        if len(inner) <= 16 and not re.search(r"[=<>+\-*/]|\\(?:frac|sin|cos|tan|pi)", inner):
            return True
    return False


def _is_operation_annotation(text: str) -> bool:
    value = text.strip()
    return bool(re.fullmatch(r"/?\s*:\s*(?:\\pi|pi|π)", value, flags=re.IGNORECASE))

def split_solution_step_texts(transcript: str, *, max_steps: int = 24) -> list[str]:
    """Deterministically split an EGE-style solution into meaningful math steps.

    The function never asks an LLM to rewrite the student's work. It only uses
    visible layout / implication / section separators. This makes the report
    granular without introducing an extra model call or changing mathematics.
    """
    text = _normalise_layout(transcript)
    if not text:
        return []

    # First recover explicit lines, arrows and compact \quad-separated transitions.
    rough: list[str] = []
    for line in re.split(r"\n+", text):
        line = line.strip()
        if not line:
            continue

        # Separate major sections before generic \quad splitting.
        for section in _split_section_markers(line):
            if _ANSWER_RE.search(section):
                rough.extend(_split_answer_part_b(section))
                continue

            # A confirmed one-line transcript often uses \quad between successive
            # transformations. Treat those as layout separators. Logical "или"
            # was protected in _normalise_layout.
            pieces = re.split(r"\s*(?:\\Rightarrow|⇒|=>|\\quad)\s*", section)
            rough.extend(piece.strip() for piece in pieces if piece.strip())

    expanded: list[str] = []
    for item in rough:
        if _PART_B_RE.search(item):
            expanded.extend(_split_part_b_calculations(item))
        else:
            expanded.append(item)

    # Clean only whitespace / obvious empty LaTeX marker debris. Preserve the
    # student's actual symbols and wording verbatim otherwise.
    out: list[str] = []
    previous = ""
    for raw in expanded:
        cleaned = re.sub(r"\s+", " ", raw).strip()
        cleaned = re.sub(r"^\\\s+", "", cleaned).strip()
        if cleaned in {r"\text{", "{", "}"} or _is_standalone_noise_fragment(cleaned):
            continue
        if _is_operation_annotation(cleaned):
            # ``/: π`` belongs to the inequality immediately before it. Keeping it
            # there preserves the student's notation without wasting a Grader step.
            if out:
                out[-1] = f"{out[-1]} {cleaned}".strip()
                previous = out[-1]
            continue
        if not cleaned or cleaned == previous:
            continue
        previous = cleaned
        out.append(cleaned)
        if len(out) >= max_steps:
            break
    return out
