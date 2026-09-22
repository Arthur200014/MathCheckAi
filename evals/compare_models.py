








import argparse
import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.llm.config import BENCHMARK_VISION_MODELS
from src.llm.ollama_client import OllamaError, ollama_chat_json

SYSTEM = "Ты Vision Agent. Точно перепиши видимую математическую запись. Не решай задачу."
USER = "Верни только JSON: {\"transcript_latex\":\"...\",\"confidence\":0.0,\"uncertain_fragments\":[]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--models", nargs="*", default=BENCHMARK_VISION_MODELS)
    args = parser.parse_args()

    image_b64 = base64.b64encode(args.image.read_bytes()).decode("ascii")
    rows = []
    for model in args.models:
        started = time.perf_counter()
        try:
            result = ollama_chat_json(
                system_prompt=SYSTEM,
                user_prompt=USER,
                image_b64=image_b64,
                model=model,
                timeout=300,
            )
            rows.append({
                "model": model,
                "ok": True,
                "seconds": round(time.perf_counter() - started, 2),
                "confidence": result.get("confidence"),
                "transcript": result.get("transcript_latex", ""),
                "error": None,
            })
        except OllamaError as exc:
            rows.append({
                "model": model,
                "ok": False,
                "seconds": round(time.perf_counter() - started, 2),
                "confidence": None,
                "transcript": "",
                "error": str(exc),
            })

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
