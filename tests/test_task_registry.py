import pytest

from src.task_registry import (
    TaskTypeNotImplementedError,
    UnknownTaskTypeError,
    get_task_profile,
    list_task_profiles,
    load_task_profile_node,
)


def test_ege13_profile_is_enabled_and_complete():
    profile = get_task_profile("ege_13")
    assert profile.enabled is True
    assert profile.solver_skill == "skills/task_13/solve.md"
    assert profile.grader_skill == "skills/task_13/grade.md"
    assert profile.criteria_path == "criteria/task_13.md"
    assert "render_trig_circle" in profile.tool_names
    assert profile.max_score == 2


def test_ege15_is_registered_but_not_enabled_yet():
    with pytest.raises(TaskTypeNotImplementedError):
        get_task_profile("ege_15")


def test_unknown_task_type_fails_closed():
    with pytest.raises(UnknownTaskTypeError):
        get_task_profile("ege_99")


def test_langgraph_registry_node_attaches_serializable_profile():
    result = load_task_profile_node({"task_type": "ege_13", "errors": []})
    assert result["task_profile_ok"] is True
    assert result["task_profile"]["id"] == "ege_13"
    assert result["task_title"]
    assert result["task_max_score"] == 2


def test_public_registry_summary_shows_enabled_status():
    rows = {row["id"]: row for row in list_task_profiles()}
    assert rows["ege_13"]["enabled"] is True
    assert rows["ege_15"]["enabled"] is False
