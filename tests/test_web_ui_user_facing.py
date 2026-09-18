from pathlib import Path


def test_user_ui_has_one_global_math_toolbar_and_russian_result_labels():
    html = Path("web/index29710.html").read_text(encoding="utf-8")
    assert html.count('id="globalMathBar"') == 1
    assert "Итоговый балл" in html
    assert "Правильный отбор корней" in html
    assert "вставка →" in html
    assert "statusRu" in html
    assert "data.status||'Результат'" not in html


def test_result_layout_places_analysis_and_circle_side_by_side():
    html = Path("web/index29710.html").read_text(encoding="utf-8")
    assert 'class="resultShell"' in html
    assert 'class="analysis"' in html
    assert 'class="circlePanel"' in html
    assert "grid-template-columns:minmax(0,1.18fr) minmax(330px,.82fr)" in html
