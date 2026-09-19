from pathlib import Path


def test_multi_photo_ui_sends_all_pages_in_one_request():
    text = Path("src/run_app.py").read_text(encoding="utf-8")
    assert "fd.append('images',f)" in text
    assert "fetch('/api/reviews/photos'" in text
    assert "одним проходом" in text
    assert "for(let i=0;i<files.length;i++)" not in text


def test_multi_photo_api_uses_one_graph_vision_run():
    text = Path("src/multi_photo_api.py").read_text(encoding="utf-8")
    assert '@api.app.post("/api/reviews/photos")' in text
    assert text.count("api.review_graph.invoke(initial_state)") == 1
    assert '"vision_strategy"] = "single_call_all_pages"' in text
    assert "MAX_PAGE_WIDTH = 2200" in text
