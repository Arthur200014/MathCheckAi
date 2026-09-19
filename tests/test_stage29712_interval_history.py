from pathlib import Path

from src.tools.ege13_task_input import extract_interval_draft


def test_interval_recovered_from_visible_part_b_family_inequality():
    transcript = """
    а) 1-cos 2x+sqrt(2)sin x=sqrt(2)-2sin(x+pi)
    x=pi/2+pi*n, n in Z
    x=-pi/4+2pi*k, k in Z
    x=-3pi/4+2pi*k, k in Z
    б) -3pi <= pi/2+pi*n <= -3pi/2 /:pi
    -3 <= 1/2+n <= -3/2
    -6 <= 1+2n <= -3
    б) -3pi <= -pi/4+2pi*k <= -3pi/2 /:pi
    -3 <= -1/4+2k <= -3/2
    б) -3pi <= -3pi/4+2pi*k <= -3pi/2 /:pi
    """
    interval, source = extract_interval_draft(transcript)
    assert interval == "[-3pi; -3pi/2]"
    assert source == "visible_selection_inequality"


def test_transformed_parameter_inequality_is_not_used_as_task_interval():
    interval, source = extract_interval_draft(
        "-6 <= 1+2n <= -3\n-7/2 <= n <= -5/2"
    )
    assert interval == ""
    assert source == "empty"


def test_literal_interval_has_priority_over_selection_work():
    transcript = """
    б) [-3π; -3π/2]
    -3π ≤ π/2+2πn ≤ -3π/2
    """
    interval, source = extract_interval_draft(transcript)
    assert interval == "[-3π; -3π/2]"
    assert source == "visible_interval"


def test_browser_keeps_previous_result_history():
    html = Path("web/index29710.html").read_text(encoding="utf-8")
    assert "mathcheck-ege13-result-history-v3" in html
    assert "archiveCurrentResult()" in html
    assert "Предыдущие проверки" in html
    assert "localStorage.setItem(HISTORY_KEY" in html
