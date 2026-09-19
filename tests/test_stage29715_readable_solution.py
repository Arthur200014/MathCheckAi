from pathlib import Path


def test_student_solution_uses_latex_rendering():
    html = Path("web/index29710.html").read_text(encoding="utf-8")

    assert 'id="confirmedSolution"' in html
    assert "mathjax@3" in html.lower()
    assert "function toLatex" in html
    assert "function typesetMath" in html
    assert "setMath(content,raw,true)" in html
    assert "визуальное" in html


def test_fixes_are_shown_under_the_matching_part():
    html = Path("web/index29710.html").read_text(encoding="utf-8")

    assert "inlineCorrections" in html
    assert "исправление по этому пункту" in html
    assert "byPart[g.key]" in html
    assert "Как исправить" in html
    assert ".compareBox.good .mathText{color:#f8fafc}" in html


def test_restore_ocr_button_is_removed():
    html = Path("web/index29710.html").read_text(encoding="utf-8")

    assert 'id="restoreBtn"' not in html
    assert "OCR-черновик восстановлен" not in html
