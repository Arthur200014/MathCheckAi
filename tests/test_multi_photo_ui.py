from src.run_app import _build_web_ui


def test_multi_photo_ui_is_generated():
    html = _build_web_ui().read_text(encoding="utf-8")

    assert 'id="file" type="file" accept="image/png,image/jpeg,image/webp" multiple' in html
    assert "const st={file:null,files:[]" in html
    assert "files.length>8" in html
    assert "for(let i=0;i<files.length;i++)" in html
    assert "mergePhotoOcr(pages,files)" in html
    assert "multi_photo_count" in html
    assert "Исходные сканы · в порядке загрузки" in html
