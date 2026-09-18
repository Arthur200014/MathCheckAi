import base64
from pathlib import Path

from src import pending_store


def test_pending_image_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(pending_store, "PENDING_DIR", tmp_path / "pending")
    payload = b"fake-jpeg-bytes"
    pending_store.save_pending_image("r-abc12345", payload)
    encoded = pending_store.load_pending_image_b64("r-abc12345")
    assert base64.b64decode(encoded) == payload


def test_invalid_review_id_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(pending_store, "PENDING_DIR", tmp_path / "pending")
    try:
        pending_store.save_pending_image("../../oops", b"x")
    except ValueError as exc:
        assert str(exc) == "invalid_review_id"
    else:
        raise AssertionError("invalid id must be rejected")


def test_pending_image_delete_after_use(tmp_path, monkeypatch):
    monkeypatch.setattr(pending_store, "PENDING_DIR", tmp_path / "pending")
    pending_store.save_pending_image("r-delete123", b"fake-jpeg-bytes")
    assert pending_store.load_pending_image_b64("r-delete123") is not None
    pending_store.delete_pending_image("r-delete123")
    assert pending_store.load_pending_image_b64("r-delete123") is None
