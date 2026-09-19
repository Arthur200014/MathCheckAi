from pathlib import Path

from src.tools import core


def _use_temp_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(core, "DB_PATH", tmp_path / "mathcheck.db")
    monkeypatch.setattr(core, "REPORTS_DIR", tmp_path / "reports")


def test_saved_review_can_be_loaded(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    review = {
        "review_id": "r-test001",
        "student_id": "student-001",
        "task_type": "ege_13",
        "final_score": 2,
        "max_score": 2,
        "status": "REVIEWED",
        "reviewer_error_class": "none",
        "reviewer_manual_review_required": False,
        "vision_elapsed_seconds": 1.5,
        "solver_elapsed_seconds": 2.5,
        "grader_elapsed_seconds": 3.5,
        "reviewer_elapsed_seconds": 0.5,
        "errors": [],
        "report": {"expert_comment": "ok"},
    }

    core.save_review(review)
    loaded = core.load_review("r-test001")

    assert loaded is not None
    assert loaded["review_id"] == "r-test001"
    assert loaded["final_score"] == 2
    assert loaded["report"]["expert_comment"] == "ok"


def test_metrics_summary_uses_persisted_reviews(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    base = {
        "student_id": "student-001",
        "task_type": "ege_13",
        "max_score": 2,
        "status": "REVIEWED",
        "report": {},
    }
    core.save_review(
        {
            **base,
            "review_id": "r-a",
            "final_score": 2,
            "reviewer_manual_review_required": False,
            "vision_elapsed_seconds": 2,
            "solver_elapsed_seconds": 4,
            "grader_elapsed_seconds": 6,
            "reviewer_elapsed_seconds": 8,
            "errors": [],
        }
    )
    core.save_review(
        {
            **base,
            "review_id": "r-b",
            "final_score": 0,
            "reviewer_manual_review_required": True,
            "vision_elapsed_seconds": 4,
            "solver_elapsed_seconds": 6,
            "grader_elapsed_seconds": 8,
            "reviewer_elapsed_seconds": 10,
            "errors": ["example"],
        }
    )

    summary = core.metrics_summary()

    assert summary["reviews"] == 2
    assert summary["success_rate"] == 1.0
    assert summary["error_rate"] == 0.5
    assert summary["manual_review_rate"] == 0.5
    assert summary["average_final_score"] == 1.0
    assert summary["average_agent_seconds"] == {
        "vision": 3.0,
        "solver": 5.0,
        "grader": 7.0,
        "reviewer": 9.0,
    }


def test_missing_review_returns_none(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    assert core.load_review("r-missing") is None
