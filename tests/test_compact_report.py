from pathlib import Path

from src.tools.ege13_report import (
    build_compact_report_node,
    extract_solution_steps,
    normalize_step_assessments,
    render_verified_trig_circle,
)


def test_extract_solution_steps_splits_arrows_and_answer():
    text = r"a) A=B \\Rightarrow B=C \\Rightarrow C=0\nб) отбор корней\nОтвет: б) -3*pi/2"
    steps = extract_solution_steps(text)
    assert len(steps) >= 4
    assert steps[0]["step_id"] == "S1"
    assert any("Ответ" in x["text"] for x in steps)


def test_answer_mismatch_overrides_final_answer_step():
    steps = [
        {"step_id": "S1", "text": "x=..."},
        {"step_id": "S2", "text": "Ответ: б) -3π/4; -11π/4; -9π/4"},
    ]
    raw = [
        {"step_id": "S1", "status": "correct", "comment": "Верно."},
        {"step_id": "S2", "status": "correct", "comment": "Верно."},
    ]
    got = normalize_step_assessments(steps, raw, explicit_final_answer_mismatch=True)
    assert got[-1]["status"] == "incorrect"
    assert "не совпадает" in got[-1]["comment"]


def test_render_verified_circle_creates_png(tmp_path, monkeypatch):
    import src.tools.ege13_report as report_mod

    monkeypatch.setattr(report_mod, "REPORT_DIR", tmp_path)
    path = render_verified_trig_circle(
        review_id="r-test",
        task_statement="а) Решите уравнение. б) Найдите корни на отрезке [-9*pi/2; -3*pi].",
        expected_roots=["-4*pi", "-15*pi/4", "-3*pi"],
    )
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 5000


def test_build_compact_report_uses_existing_grader_steps(tmp_path, monkeypatch):
    import src.tools.ege13_report as report_mod

    monkeypatch.setattr(report_mod, "REPORT_DIR", tmp_path)
    state = {
        "review_id": "r-report",
        "task_type": "ege_13",
        "task_title": "Тригонометрическое уравнение и отбор корней",
        "task_statement": "а) Решите. б) Найдите корни на отрезке [-3*pi; -3*pi/2].",
        "status": "REVIEWED",
        "final_score": 2,
        "max_score": 2,
        "reference_verification_ok": True,
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_a_verified": "x=...",
        "reference_answer_part_b_verified": "-11*pi/4; -9*pi/4; -3*pi/2",
        "reviewer_part_a_equivalent": True,
        "reviewer_part_b_roots_match": True,
        "reviewer_diagram_override_applied": False,
        "reviewer_error_class": "none",
        "diagram_verification_status": "DIAGRAM_UNVERIFIED_AFTER_REINSPECTION",
        "diagram_part_b_valid": None,
        "diagram_method_used": True,
        "grader_step_assessments": [
            {"step_id": "S1", "text": "шаг", "status": "correct", "comment": "Верно."}
        ],
    }
    out = build_compact_report_node(state)
    assert out["report"]["score_text"] == "2/2"
    assert out["report"]["step_checks"][0]["status"] == "correct"
    assert out["report"]["correct_trig_circle_url"].endswith("/report-circle")
    assert (tmp_path / "r-report-trig-circle.png").exists()
