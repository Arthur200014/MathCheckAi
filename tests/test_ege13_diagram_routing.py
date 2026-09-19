from src.graph import route_after_diagram_verify, route_after_reference


def test_reference_failure_goes_to_reviewer_without_diagram():
    assert route_after_reference({"reference_verification_ok": False}) == "review"


def test_algebraic_selection_skips_diagram_agent():
    state = {
        "task_type": "ege_13",
        "image_b64": "ZmFrZQ==",
        "reference_verification_ok": True,
        "confirmed_transcript": "а) решение\nб) x1=-3π; x2=-2π",
    }
    assert route_after_reference(state) == "grade"


def test_visual_selection_uses_diagram_agent():
    state = {
        "task_type": "ege_13",
        "image_b64": "ZmFrZQ==",
        "reference_verification_ok": True,
        "confirmed_transcript": "б) Отберём корни с помощью тригонометрической окружности",
    }
    assert route_after_reference(state) == "diagram"


def test_diagram_reinspection_only_when_requested():
    assert route_after_diagram_verify({"diagram_reinspection_needed": True}) == "reinspect"
    assert route_after_diagram_verify({"diagram_reinspection_needed": False}) == "grade"
