"""Test only multipart encoding: do not post any real photographs to CI."""
import tempfile
from pathlib import Path

from scripts.demo_photos import build_photo_request


def test_photo_demo_encodes_local_file_without_publishing(tmp_path: Path):
    file = tmp_path / "sample.png"
    file.write_bytes(b"not-a-real-photo")
    request = build_photo_request(file, "http://127.0.0.1:8000")
    assert request.full_url == "http://127.0.0.1:8000/api/reviews/photo"
    assert b'name="image"' in request.data
    assert b'name="student_id"' in request.data
    assert b"not-a-real-photo" in request.data
    assert request.get_header("Content-type").startswith("multipart/form-data; boundary=")
