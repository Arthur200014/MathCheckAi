from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_PARTS = {".git", ".venv", "venv", "data", "reports", "__pycache__"}
TEXT_NAMES = {"Dockerfile", ".env.example", ".gitignore", ".dockerignore"}
TEXT_SUFFIXES = {".sh", ".yml", ".yaml", ".toml"}


def _docstring_spans(source: str) -> list[tuple[int, int, int, int, bool]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    spans: list[tuple[int, int, int, int, bool]] = []
    containers = [tree]
    containers.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    for container in containers:
        body = getattr(container, "body", None) or []
        if not body:
            continue
        first = body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and hasattr(first, "end_lineno")
            and hasattr(first, "end_col_offset")
        ):
            continue
        replace_with_pass = not isinstance(container, ast.Module) and len(body) == 1
        spans.append(
            (
                int(first.lineno),
                int(first.end_lineno),
                int(first.col_offset),
                int(first.end_col_offset),
                replace_with_pass,
            )
        )
    return sorted(spans, reverse=True)


def _remove_docstrings(source: str) -> str:
    lines = source.splitlines(keepends=True)
    for start, end, col_start, col_end, replace_with_pass in _docstring_spans(source):
        i0 = start - 1
        i1 = end - 1
        if i0 < 0 or i1 >= len(lines):
            continue
        first_line = lines[i0]
        last_line = lines[i1]
        prefix = first_line[:col_start]
        suffix = last_line[col_end:]
        if prefix.strip() or suffix.strip():
            continue
        newline = "\n" if last_line.endswith("\n") else ""
        if replace_with_pass:
            lines[i0] = prefix + "pass" + newline
        else:
            lines[i0] = newline
        for idx in range(i0 + 1, i1 + 1):
            lines[idx] = "\n" if lines[idx].endswith("\n") else ""
    return "".join(lines)


def _remove_python_comments(source: str) -> str:
    source = _remove_docstrings(source)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        return source
    kept = []
    for token in tokens:
        if token.type == tokenize.COMMENT:
            if token.start[0] == 1 and token.string.startswith("#!"):
                kept.append(token)
            continue
        kept.append(token)
    cleaned = tokenize.untokenize(kept)
    try:
        compile(cleaned, "<comment-cleanup>", "exec")
    except SyntaxError:
        return source
    return cleaned


def _remove_full_line_hash_comments(text: str, *, preserve_shebang: bool = False, preserve_docker_directives: bool = False) -> str:
    out: list[str] = []
    for index, line in enumerate(text.splitlines(keepends=True)):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            out.append(line)
            continue
        if preserve_shebang and index == 0 and stripped.startswith("#!"):
            out.append(line)
            continue
        if preserve_docker_directives and stripped.lower().startswith(("# syntax=", "# escape=")):
            out.append(line)
            continue
    return "".join(out)


def _remove_html_comments(text: str) -> str:
    return re.sub(r"<!--(?!\[if\b).*?-->", "", text, flags=re.DOTALL | re.IGNORECASE)


def _clean_file(path: Path) -> bool:
    try:
        original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    if path.suffix == ".py":
        cleaned = _remove_python_comments(original)
    elif path.suffix == ".html":
        cleaned = _remove_html_comments(original)
    elif path.suffix == ".sh":
        cleaned = _remove_full_line_hash_comments(original, preserve_shebang=True)
    elif path.name == "Dockerfile":
        cleaned = _remove_full_line_hash_comments(original, preserve_docker_directives=True)
    elif path.name in {".env.example", ".gitignore", ".dockerignore"} or path.suffix in {".yml", ".yaml", ".toml"}:
        cleaned = _remove_full_line_hash_comments(original)
    else:
        return False
    if cleaned == original:
        return False
    path.write_text(cleaned, encoding="utf-8")
    return True


def main() -> int:
    changed: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.name == Path(__file__).name:
            continue
        if path.name not in TEXT_NAMES and path.suffix not in TEXT_SUFFIXES | {".py", ".html"}:
            continue
        if _clean_file(path):
            changed.append(str(path.relative_to(ROOT)))
    print(f"Cleaned {len(changed)} files")
    for item in changed:
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
