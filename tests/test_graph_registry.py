from src.graph import route_after_task_profile


def test_task_profile_route():
    assert route_after_task_profile({"task_profile_ok": True}) == "continue"
    assert route_after_task_profile({"task_profile_ok": False}) == "unsupported"
