from pathlib import Path


def test_editor_runs_preflight_before_grading_and_shows_stage_times():
    html = Path("web/index29710.html").read_text(encoding="utf-8")

    assert "/api/reviews/preflight" in html
    assert 'id="preflightBox"' in html
    assert "if(!checked.ok)" in html
    assert 'id="stageProgress"' in html
    assert "/progress`" in html
    assert "startProgressPolling" in html
    assert "Куда уходит время" in html
