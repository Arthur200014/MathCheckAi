import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "task_13" / "benchmark_cases.json"


def test_ege13_benchmark_has_12_balanced_expert_cases():
    data = json.loads(CASES.read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) == 12
    scores = [case["expert_score"] for case in cases]
    assert scores.count(0) == 4
    assert scores.count(1) == 4
    assert scores.count(2) == 4


def test_ege13_benchmark_cases_have_task_fields_and_safe_crop_boxes():
    data = json.loads(CASES.read_text(encoding="utf-8"))
    seen = set()
    for case in data["cases"]:
        assert case["id"] not in seen
        seen.add(case["id"])
        assert case["task_equation"].strip()
        assert case["interval"].strip()
        assert case["expert_summary"].strip()
        assert case["pages"]
        for page in case["pages"]:
            assert int(page["page"]) >= 1
            left, top, right, bottom = page["crop"]
            assert 0 <= left < right <= 1
            assert 0 <= top < bottom <= 1
