from src.run_app import api


def test_multi_photo_ui_is_generated():
    html = api.UI_INDEX_PATH.read_text(encoding="utf-8")

    assert 'id="file" type="file" accept="image/png,image/jpeg,image/webp" multiple' in html
    assert "const st={file:null,files:[]" in html
    assert "files.length>8" in html
    assert "files.forEach(f=>fd.append('images',f))" in html
    assert "fetch('/api/reviews/photos'" in html
    assert "одним проходом" in html
    assert "Исходные сканы · в порядке загрузки" in html
