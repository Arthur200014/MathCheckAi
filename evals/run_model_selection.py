from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.llm.ollama_client import OllamaError, ollama_chat_json

SYSTEM = (
    "Ты проходишь короткий benchmark для MathCheck AI. "
    "Следуй инструкции буквально, не добавляй факты от себя и верни только данные по schema."
)

CASES = [
    {
        "id": "math_roots",
        "kind": "items",
        "prompt": "Реши sin(x)=1/2 на отрезке [0, 2*pi]. Верни только корни в SymPy-форме.",
        "expected": {"pi/6", "5*pi/6"},
    },
    {
        "id": "math_interval",
        "kind": "items",
        "prompt": "Реши sin(x)=0 на отрезке [-pi, pi]. Верни только корни в SymPy-форме.",
        "expected": {"-pi", "0", "pi"},
    },
    {
        "id": "no_hallucination",
        "kind": "items",
        "prompt": (
            "Извлеки только семейства корней, которые явно написал ученик. "
            "Не решай задачу и ничего не добавляй. Текст ученика: x=pi/6+2*pi*k. Других корней нет."
        ),
        "expected": {"pi/6+2*pi*k"},
    },
    {
        "id": "role_boundary",
        "kind": "text",
        "prompt": "Перепиши дословно только эту строку и не решай её: sin x = 1/2",
        "expected": "sin x = 1/2",
    },
]

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "text": {"type": "string"},
    },
    "required": ["items", "text"],
    "additionalProperties": False,
}


def _norm(value: str) -> str:
    return "".join(str(value).lower().split()).replace("π", "pi")


def _score(case: dict, result: dict) -> bool:
    if case["kind"] == "items":
        got = {_norm(x) for x in result.get("items", [])}
        expected = {_norm(x) for x in case["expected"]}
        return got == expected
    return _norm(result.get("text", "")) == _norm(case["expected"])


def run_model(model: str) -> dict:
    rows = []
    started_model = time.perf_counter()
    for case in CASES:
        started = time.perf_counter()
        try:
            result = ollama_chat_json(
                system_prompt=SYSTEM,
                user_prompt=case["prompt"],
                model=model,
                response_schema=SCHEMA,
                num_ctx=4096,
                num_predict=512,
                use_num_predict_limit=True,
            )
            ok = _score(case, result)
            rows.append(
                {
                    "case_id": case["id"],
                    "ok": ok,
                    "valid_json": True,
                    "seconds": round(time.perf_counter() - started, 3),
                    "result": {"items": result.get("items", []), "text": result.get("text", "")},
                }
            )
        except OllamaError as exc:
            rows.append(
                {
                    "case_id": case["id"],
                    "ok": False,
                    "valid_json": False,
                    "seconds": round(time.perf_counter() - started, 3),
                    "error": str(exc),
                }
            )

    total = len(rows)
    passed = sum(1 for row in rows if row["ok"])
    valid = sum(1 for row in rows if row["valid_json"])
    hallucination_case = next(row for row in rows if row["case_id"] == "no_hallucination")
    role_case = next(row for row in rows if row["case_id"] == "role_boundary")
    return {
        "model": model,
        "cases": total,
        "task_accuracy": round(passed / total, 4),
        "valid_json_rate": round(valid / total, 4),
        "no_hallucination_pass": bool(hallucination_case["ok"]),
        "role_boundary_pass": bool(role_case["ok"]),
        "total_seconds": round(time.perf_counter() - started_model, 3),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen3-vl:4b-instruct", "gemma3:4b", "granite3.2-vision:2b"],
    )
    parser.add_argument("--output", default="evals/results/model-selection.json")
    args = parser.parse_args()

    results = []
    for model in args.models:
        print(f"\n=== {model} ===", flush=True)
        result = run_model(model)
        results.append(result)
        for row in result["rows"]:
            status = "OK" if row["ok"] else "FAIL"
            print(f"{row['case_id']}: {status}, {row['seconds']}s", flush=True)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k != "rows"},
                ensure_ascii=False,
            ),
            flush=True,
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
