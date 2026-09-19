import json
from pathlib import Path

from evals.validate_ege13_release import validate_case


ROOT = Path(__file__).resolve().parents[1]


def test_all_labelled_cases_pass_fast_release_gate():
    data = json.loads((ROOT / "evals" / "task_13" / "benchmark_cases.json").read_text(encoding="utf-8"))
    rows = [validate_case(case) for case in data["cases"]]
    failed = [row for row in rows if not row["ok"]]
    assert failed == []
