from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_real_criteria_replaced_placeholder():
    text = (ROOT / "criteria/task_13.md").read_text(encoding="utf-8")
    assert "ПЛЕЙСХОЛДЕР" not in text
    assert "2 балла" in text
    assert "вычислительной ошибки" in text
    assert "разные математически корректные способы" in text


def test_expert_eval_manifest_contains_scored_examples():
    data = json.loads((ROOT / "evals/task_13/expert_cases.json").read_text(encoding="utf-8"))
    scores = [case["expert_score"] for case in data["cases"]]
    assert 0 in scores and 1 in scores and 2 in scores
    assert len(data["cases"]) >= 20
