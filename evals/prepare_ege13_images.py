"""Prepare local EGE-13 benchmark images from the expert PDF.

The repository keeps the official/expert source PDF, but benchmark images must
NOT contain the printed official answer or the expert comment because that would
leak the ground truth to Vision. Crop boxes live in benchmark_cases.json.

Usage:
    pip install -r requirements-eval.txt
    python evals/prepare_ege13_images.py

Output is written to local_eval_data/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evals" / "task_13" / "benchmark_cases.json"
DEFAULT_OUTPUT = ROOT / "local_eval_data"


def _load_cases(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("cases"), list) or not data["cases"]:
        raise SystemExit(f"Нет cases в {path}")
    return data


def _clip_from_normalized(page: fitz.Page, crop: list[float]) -> fitz.Rect:
    if len(crop) != 4:
        raise ValueError("crop должен содержать 4 числа")
    left, top, right, bottom = (float(x) for x in crop)
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"неверный crop: {crop}")
    rect = page.rect
    return fitz.Rect(
        rect.x0 + rect.width * left,
        rect.y0 + rect.height * top,
        rect.x0 + rect.width * right,
        rect.y0 + rect.height * bottom,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dpi", type=int, default=220)
    args = parser.parse_args()

    data = _load_cases(args.cases)
    source_pdf = ROOT / str(data.get("source_pdf", ""))
    if not source_pdf.exists():
        raise SystemExit(f"Не найден source PDF: {source_pdf}")

    args.output.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    with fitz.open(source_pdf) as doc:
        for case in data["cases"]:
            case_id = str(case["id"])
            images: list[str] = []
            for index, page_spec in enumerate(case.get("pages", []), start=1):
                page_number = int(page_spec["page"])
                if page_number < 1 or page_number > len(doc):
                    raise SystemExit(f"{case_id}: страницы {page_number} нет в PDF")
                page = doc[page_number - 1]
                clip = _clip_from_normalized(page, page_spec["crop"])
                pix = page.get_pixmap(dpi=args.dpi, clip=clip, alpha=False)
                out = args.output / f"{case_id}_p{index}.png"
                pix.save(str(out))
                images.append(out.name)
                print(f"{case_id}: {page_number} -> {out.relative_to(ROOT)}")

            manifest.append(
                {
                    "id": case_id,
                    "expert_score": case.get("expert_score"),
                    "task_equation": case.get("task_equation", ""),
                    "interval": case.get("interval", ""),
                    "images": images,
                }
            )

    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(
        json.dumps({"cases": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nГотово: {len(manifest)} кейсов. Manifest: {manifest_path.relative_to(ROOT)}")
    print("Проверь несколько crop-файлов глазами: в них не должно быть печатного эталонного ответа/комментария эксперта.")


if __name__ == "__main__":
    main()
