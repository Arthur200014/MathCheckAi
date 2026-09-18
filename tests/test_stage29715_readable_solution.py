from pathlib import Path


def test_student_solution_is_rendered_as_readable_math_blocks():
    html = Path("web/index29710.html").read_text(encoding="utf-8")

    assert 'id="confirmedSolution"' in html
    assert "solutionLineContent" in html
    assert "mathLine" in html
    assert "Cambria Math" in html
    assert "appendPrettyMath" in html
    assert "className='frac'" in html
    assert "fracNum" in html
    assert "fracDen" in html
    assert "визуально оформляем его для чтения" in html


def test_readable_math_is_display_only_and_status_is_human_readable():
    html = Path("web/index29710.html").read_text(encoding="utf-8")

    assert "исходный подтверждённый текст ученика не переписывается" in html
    assert "function statusRu" in html
    assert "Проверка завершена" in html
    assert "Нужна ручная проверка" in html
