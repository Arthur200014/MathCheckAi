"""Optional local-only OCR load on real photographs.

Photos stay on the user's Mac: this script uploads them to the local FastAPI
instance, but does NOT publish them to GitHub or blindly confirm OCR results.
The application normally pauses for human transcript confirmation.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

SUPPORTED = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def build_photo_request(path: Path, base_url: str) -> Request:
    data = path.read_bytes()
    if not data or len(data) > 12 * 1024 * 1024:
        raise ValueError("Image must be nonempty and no larger than 12 MB")
    mime = SUPPORTED.get(path.suffix.lower())
    if not mime:
        raise ValueError("Unsupported image extension")
    boundary = "----MathCheckLocalDemo" + uuid4().hex

    def field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
            f"{value}\r\n"
        ).encode("utf-8")

    # Use a safe ASCII filename in the HTTP header even for Cyrillic files.
    parts = [
        field("student_id", "demo-photo-local"),
        field("task_type", "ege_13"),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
        f"filename=\"example{path.suffix.lower()}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n".encode("ascii"),
        data,
        b"\r\n" + f"--{boundary}--\r\n".encode("ascii"),
    ]
    return Request(
        base_url.rstrip("/") + "/api/reviews/photo",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Send local images for real OCR (no auto-grading).")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    if not args.directory.is_dir():
        parser.error(f"Not a folder: {args.directory}")
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be from 1 to 20")
    images = sorted(
        p for p in args.directory.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED
    )[:args.limit]
    if not images:
        parser.error("No PNG, JPG, JPEG or WEBP images found in this directory")

    print(f"Real OCR: submitting {len(images)} locally stored images (no automatic confirmation).")
    succeeded = 0
    for i, image in enumerate(images, start=1):
        try:
            with urlopen(build_photo_request(image, args.base_url), timeout=1200) as resp:
                result = json.load(resp)
            print(
                f"OCR {i}/{len(images)}: {image.name} | "
                f"review_id={result.get('review_id', '?')} | "
                f"status={result.get('status', 'unknown')}",
                flush=True,
            )
            succeeded += 1
        except (HTTPError, URLError, ValueError, OSError, json.JSONDecodeError) as exc:
            print(f"OCR {i}/{len(images)} failed: {image.name} ({type(exc).__name__})", flush=True)

    print(
        f"Real OCR submitted: {succeeded}/{len(images)}. "
        "Further Solver/Grader steps need the usual manual transcript confirmation."
    )
    if succeeded != len(images):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
