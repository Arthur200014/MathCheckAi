from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_ui_file_has_human_confirmation_flow_and_raw_json_copy():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "/api/reviews/photo" in html
    assert "/api/reviews/confirm-transcript" in html
    assert "confirmed_transcript" in html
    assert "confirmed_task_statement" in html
    assert "taskOcrText" in html
    assert "Условие и решение проверены — начать проверку" in html
    assert "copyFinalBtn" in html
    assert "copyOcrBtn" in html
    assert "finalJson" in html
    assert "ocrJson" in html


def test_api_serves_root_ui_and_keeps_confirmation_endpoint():
    source = (ROOT / "src" / "api.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert '@app.get("/", include_in_schema=False)' in source
    assert 'def web_ui()' in source
    assert '@app.post("/api/reviews/confirm-transcript")' in source
    assert '"browser_ui_enabled": True' in source
