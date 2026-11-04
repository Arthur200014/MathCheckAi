from src.graph import route_after_diagram_verify, route_after_reference


def test_reference_failure_still_goes_through_grader():
    # The current LangGraph routes all verification outcomes to the grader.
    # The reviewer follows the grader and is not a direct reference edge.
    assert route_after_reference({"reference_verification_ok": False}) == "grade"


def test_algebraic_selection_skips_diagram_agent():
    state = {
        "task_type": "ege_13",
        "image_b64": "ZmFrZQ==",
        "reference_verification_ok": True,
        "confirmed_transcript": "а) решение\nб) x1=-3π; x2=-2π",
    }
    assert route_after_reference(state) == "grade"


def test_visual_selection_is_ignored_by_project_scope():
    state = {
        "task_type": "ege_13",
        "image_b64": "ZmFrZQ==",
        "reference_verification_ok": True,
        "confirmed_transcript": "б) Отберём корни с помощью тригонометрической окружности",
    }
    assert route_after_reference(state) == "grade"


def test_diagram_compatibility_route_does_not_reinspect():
    assert route_after_diagram_verify({"diagram_reinspection_needed": True}) == "grade"
    assert route_after_diagram_verify({"diagram_reinspection_needed": False}) == "grade"
