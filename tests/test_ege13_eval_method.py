import json
from collections import Counter
from pathlib import Path

import evals.run_ege13_benchmark as bench


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "task_13" / "benchmark_cases.json"


def _cases():
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def test_ege13_eval_dataset_is_complete_and_balanced():
    cases = _cases()

    assert len(cases) == 12
    assert Counter(case["expert_score"] for case in cases) == {0: 4, 1: 4, 2: 4}

    ids = {case["id"] for case in cases}
    assert "13.3.3" in ids
    assert "13.3.2" not in ids

    for case in cases:
        assert case["manual_transcript"].strip(), case["id"]
        assert isinstance(case["expected_key_points"], list), case["id"]
        assert isinstance(case["expected_errors"], list), case["id"]
        assert isinstance(case["expected_manual_review"], bool), case["id"]
        assert case["task_equation"].strip(), case["id"]
        assert case["interval"].strip(), case["id"]
        assert case["pages"], case["id"]


def _demo_case():
    return {
        "id": "demo",
        "expert_score": 2,
        "expert_summary": "",
        "task_equation": "sin x = 0",
        "interval": "[0; π]",
        "pages": [{"page": 1, "crop": [0, 0, 1, 1]}],
        "manual_transcript": "а) sin x = 0\nб) 0; π",
        "expected_key_points": [],
        "expected_errors": [],
        "expected_manual_review": False,
    }


def _fake_pipeline(received):
    def fake(_case, _model, transcript):
        received["transcript"] = transcript
        return {
            "final_score": 2,
            "reference_verification_ok": True,
            "grader_ok": True,
            "reviewer_ok": True,
            "reviewer_manual_review_required": False,
            "solver_elapsed_seconds": 1.0,
            "reference_elapsed_seconds": 0.1,
            "grader_elapsed_seconds": 1.0,
            "reviewer_elapsed_seconds": 1.0,
        }
    return fake


def test_primary_eval_uses_raw_vision_only_for_ocr_metric_then_human_confirmation(tmp_path, monkeypatch):
    case = _demo_case()
    (tmp_path / "demo_p1.png").write_bytes(b"fake-image")

    monkeypatch.setattr(
        bench,
        "_run_vision",
        lambda *_args, **_kwargs: {
            "transcript": "а) sin x = 0\nб) 0; 2π",
            "errors": [],
            "vision_elapsed_seconds": 1.0,
        },
    )

    received = {}
    monkeypatch.setattr(bench, "_run_confirmed_pipeline", _fake_pipeline(received))

    row = bench._run_case(case, "demo-model", tmp_path)

    assert received["transcript"] == case["manual_transcript"]
    assert row["vision_transcript"] != row["confirmed_transcript"]
    assert row["confirmed_transcript"] == case["manual_transcript"]
    assert row["human_edit_required"] is True
    assert row["vision_similarity"] < 1.0
    assert row["vision_ok"] is True
    assert row["final_score"] == 2
    assert row["score_match"] is True


def test_vision_invalid_json_does_not_cancel_human_confirmed_grading(tmp_path, monkeypatch):
    case = _demo_case()
    (tmp_path / "demo_p1.png").write_bytes(b"fake-image")

    monkeypatch.setattr(
        bench,
        "_run_vision",
        lambda *_args, **_kwargs: {
            "transcript": "",
            "errors": ["vision:OLLAMA_INVALID_JSON"],
            "vision_elapsed_seconds": 12.0,
        },
    )

    received = {}
    monkeypatch.setattr(bench, "_run_confirmed_pipeline", _fake_pipeline(received))

    row = bench._run_case(case, "demo-model", tmp_path)

    assert received["transcript"] == case["manual_transcript"]
    assert row["vision_ok"] is False
    assert row["vision_similarity"] is None
    assert row["human_edit_required"] is True
    assert "OLLAMA_INVALID_JSON" in row["vision_error"]
    assert row["final_score"] == 2
    assert row["score_match"] is True
