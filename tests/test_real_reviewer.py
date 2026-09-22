from src.agents import reviewer as reviewer_module


def _base_state():
    return {
        "task_type": "ege_13",
        "task_statement": "а) Решите уравнение: 2sin(x - π/6) - 2√3 cos(π/2 - x) = 0. б) Найдите все корни этого уравнения, принадлежащие отрезку [-6π; -9π/2].",
        "confirmed_transcript": r"x=-\frac{\pi}{6}+\pi n, n\in\mathbb Z; б) -\frac{31\pi}{6}",
        "transcript_confirmed": True,
        "needs_confirmation": False,
        "reference_verification_ok": True,
        "reference_verified_families": [{"expression": "pi*(n - 1/6)", "parameter": "n"}],
        "reference_expected_roots": ["-31*pi/6"],
        "reference_answer_part_a_verified": r"x=\pi(n-1/6)",
        "reference_answer_part_b_verified": r"-31\pi/6",
        "grader_mode": "real",
        "grader_ok": True,
        "grader_manual_review_required": False,
        "grader_part_a_equivalent": True,
        "grader_part_b_roots_match": True,
        "draft_score": 2,
        "max_score": 2,
        "errors": [],
        "warnings": [],
    }


def _good_reviewer_payload():
    return {
        "can_review": True,
        "part_a_status": "correct",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": False,
        "confidence": 0.98,
        "student_machine_spec": {
            "general_solution_families": [{"expression": "-pi/6 + pi*n", "parameter": "n"}],
            "selected_roots": ["-31*pi/6"],
        },
        "evidence": ["оба пункта корректны"],
        "assessment": "Независимая проверка подтверждает решение.",
        "proposed_score": 2,
        "_model": "reviewer-test",
    }


def test_reviewer_agreement_creates_final_score(monkeypatch):
    monkeypatch.setattr(reviewer_module, "ollama_chat_json", lambda **kwargs: _good_reviewer_payload())
    out = reviewer_module.reviewer_agent(_base_state())
    assert out["reviewer_ok"] is True
    assert out["reviewer_independent_score"] == 2
    assert out["final_score"] == 2
    assert out["status"] == "REVIEWED"


def test_reviewer_score_disagreement_requires_manual_review(monkeypatch):
    payload = _good_reviewer_payload()
    payload["part_b_status"] = "incorrect"
    payload["student_machine_spec"] = {
        "general_solution_families": [{"expression": "-pi/6 + pi*n", "parameter": "n"}],
        "selected_roots": [],
    }
    payload["proposed_score"] = 1
    monkeypatch.setattr(reviewer_module, "ollama_chat_json", lambda **kwargs: payload)
    out = reviewer_module.reviewer_agent(_base_state())
    assert out["reviewer_ok"] is True
    assert out["status"] == "REVIEWED"
    assert out["final_score"] == 2
    assert out["reviewer_manual_review_required"] is True
    assert any("reviewer_score_disagrees_with_grader" in x for x in out["reviewer_evidence"])


def test_reviewer_is_not_given_grader_score(monkeypatch):
    captured = {}
    def fake_call(**kwargs):
        captured.update(kwargs)
        return _good_reviewer_payload()
    monkeypatch.setattr(reviewer_module, "ollama_chat_json", fake_call)
    reviewer_module.reviewer_agent(_base_state())
    prompt = captured["user_prompt"]
    assert "draft_score" not in prompt
    assert "grader_proposed_score" not in prompt


def test_grader_manual_review_blocks_reviewer(monkeypatch):
    state = _base_state()
    state["grader_ok"] = False
    state["grader_manual_review_required"] = True
    state["grader_conflicts"] = ["example_conflict"]
    out = reviewer_module.reviewer_agent(state)
    assert out["status"] == "REVIEWED"
    assert out["final_score"] == 2
    assert out["reviewer_manual_review_required"] is True
    assert any("example_conflict" in x for x in out["warnings"])


def test_reviewer_accepts_deterministic_diagram_override_and_finalizes_one(monkeypatch):
    task = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    state = {
        "task_type": "ege_13",
        "task_statement": task,
        "confirmed_transcript": "пункт а верен; б) отбор по окружности",
        "transcript_confirmed": True,
        "needs_confirmation": False,
        "reference_verification_ok": True,
        "reference_verified_families": [
            {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
            {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
            {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_a_verified": "verified",
        "reference_answer_part_b_verified": "verified",
        "diagram_method_used": True,
        "diagram_verification_status": "DIAGRAM_INVALID",
        "diagram_part_b_valid": False,
        "diagram_verification_issues": [
            "diagram_point_value_mismatch:id=1:value=-9*pi/4:drawn=lower_left:mathematical=lower_right"
        ],
        "diagram_verification_results": ["diagram_claimed_root_set_matches_reference:true"],
        "grader_mode": "real",
        "grader_ok": True,
        "grader_manual_review_required": False,
        "grader_part_a_equivalent": True,
        "grader_part_b_roots_match": True,
        "draft_score": 1,
        "max_score": 2,
        "errors": [],
        "warnings": [],
    }
    payload = {
        "can_review": True,
        "part_a_status": "correct",
        "part_b_status": "correct",                                              
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": False,
        "confidence": 0.98,
        "student_machine_spec": {
            "general_solution_families": [
                {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
                {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
                {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
            ],
            "selected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        },
        "evidence": ["text root set looks correct"],
        "assessment": "text-only pass",
        "proposed_score": 2,
        "_model": "reviewer-test",
    }
    monkeypatch.setattr(reviewer_module, "ollama_chat_json", lambda **kwargs: payload)
    out = reviewer_module.reviewer_agent(state)
    assert out["reviewer_ok"] is True
    assert out["reviewer_independent_score"] == 1
    assert out["reviewer_part_b_status"] == "incorrect"
    assert out["reviewer_error_class"] == "diagram_selection_error"
    assert out["reviewer_diagram_override_applied"] is True
    assert out["final_score"] == 1
    assert out["status"] == "REVIEWED"
    assert any("overridden_by_diagram" in x for x in out["reviewer_overrides"])


def test_reviewer_unreadable_diagram_does_not_block_confirmed_math(monkeypatch):
    task = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    state = {
        "task_type": "ege_13",
        "task_statement": task,
        "confirmed_transcript": "пункт а верен; б) -11π/4; -9π/4; -3π/2; отбор по окружности",
        "transcript_confirmed": True,
        "needs_confirmation": False,
        "reference_verification_ok": True,
        "reference_verified_families": [
            {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
            {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
            {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_a_verified": "verified",
        "reference_answer_part_b_verified": "verified",
        "diagram_method_used": True,
        "diagram_verification_status": "DIAGRAM_UNVERIFIED_AFTER_REINSPECTION",
        "diagram_part_b_valid": None,
        "diagram_verification_issues": ["uncertain:handwriting"],
        "grader_mode": "real",
        "grader_ok": True,
        "grader_manual_review_required": False,
        "grader_part_a_equivalent": True,
        "grader_part_b_roots_match": True,
        "draft_score": 2,
        "max_score": 2,
        "errors": [],
        "warnings": [],
    }
    payload = {
        "can_review": True,
        "part_a_status": "correct",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": True,
        "confidence": 0.98,
        "student_machine_spec": {
            "general_solution_families": [
                {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
                {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
                {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
            ],
            "selected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        },
        "evidence": ["математика подтверждена"],
        "assessment": "Рисунок неразборчив, но математический результат проверяем.",
        "proposed_score": 1,                                                                    
        "_model": "reviewer-test",
    }
    monkeypatch.setattr(reviewer_module, "ollama_chat_json", lambda **kwargs: payload)
    out = reviewer_module.reviewer_agent(state)
    assert out["reviewer_ok"] is True
    assert out["reviewer_manual_review_required"] is False
    assert out["reviewer_diagram_unverified_ignored_for_score"] is True
    assert any("unreadable_diagram_no_proven_error" in x for x in out["reviewer_overrides"])
    assert out["reviewer_independent_score"] == 2
    assert out["final_score"] == 2
    assert out["status"] == "REVIEWED"
    assert "diagram_unverified_no_penalty" in out["warnings"]


def test_reviewer_explicit_final_answer_lock_confirms_case_b_score_one(monkeypatch):
    task = "а) Решите уравнение 1 - cos 2x + √2 sin x = √2 - 2 sin(x + π). б) Найдите все корни этого уравнения, принадлежащие отрезку [-3π; -3π/2]."
    transcript = r"""13. а) решение корректно
x = (-1)^k*(-\frac{\pi}{4})+\pi k; x=\frac{\pi}{2}+2\pi n
б) (1): -\frac{\pi}{4}-2\pi=-\frac{9\pi}{4}; (2): -\frac{3\pi}{4}-2\pi=-\frac{11\pi}{4}; (3): -\frac{3\pi}{2}
Ответ: а) x = ...; б) -\frac{3\pi}{4}, -\frac{11\pi}{4}, -\frac{9\pi}{4}"""
    state = {
        "task_type": "ege_13",
        "task_statement": task,
        "confirmed_transcript": transcript,
        "transcript_confirmed": True,
        "needs_confirmation": False,
        "reference_verification_ok": True,
        "reference_verified_families": [
            {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
            {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
            {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
        ],
        "reference_expected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        "reference_answer_part_a_verified": "verified",
        "reference_answer_part_b_verified": "verified",
        "diagram_method_used": True,
        "diagram_verification_status": "DIAGRAM_UNVERIFIED_AFTER_REINSPECTION",
        "diagram_part_b_valid": None,
        "grader_mode": "real",
        "grader_ok": True,
        "grader_manual_review_required": False,
        "grader_part_a_equivalent": True,
        "grader_part_b_roots_match": False,
        "draft_score": 1,
        "max_score": 2,
        "errors": [],
        "warnings": [],
    }
    payload = {
        "can_review": True,
        "part_a_status": "correct",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": False,
        "confidence": 0.98,
        "student_machine_spec": {
            "general_solution_families": [
                {"expression": "pi*(4*n + 1)/2", "parameter": "n"},
                {"expression": "pi*(8*n + 5)/4", "parameter": "n"},
                {"expression": "pi*(8*n + 7)/4", "parameter": "n"},
            ],
            "selected_roots": ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
        },
        "evidence": ["LLM text-only pass"],
        "assessment": "LLM incorrectly repaired the final answer.",
        "proposed_score": 2,
        "_model": "reviewer-test",
    }
    monkeypatch.setattr(reviewer_module, "ollama_chat_json", lambda **kwargs: payload)
    out = reviewer_module.reviewer_agent(state)

    assert out["reviewer_student_answer_lock_applied"] is True
    assert set(out["reviewer_student_final_answer_part_b"]) == {"-3*pi/4", "-11*pi/4", "-9*pi/4"}
    assert out["reviewer_part_b_roots_match"] is False
    assert out["reviewer_part_b_status"] == "incorrect"
    assert out["reviewer_error_class"] == "root_selection_error"
    assert out["reviewer_independent_score"] == 1
    assert out["final_score"] == 1
    assert out["status"] == "REVIEWED"
    assert any("overridden_by_explicit_final_answer" in x for x in out["reviewer_overrides"])
