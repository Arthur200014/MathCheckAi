from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.grader import grader_agent
from src.agents.persistence import persist_review_node
from src.agents.reference_verifier import reference_verifier_agent
from src.agents.reviewer import reviewer_agent
from src.agents.solver import solver_agent
from src.agents.vision import vision_agent
from src.observability.runtime import finish_trace_span, start_trace_span
from src.progress_store import finish_stage, start_stage
from src.state import ReviewState
from src.task_registry import load_task_profile_node
from src.tools.ege13_user_report_exact import build_user_report_node


def _timed(stage: str, func):
    def wrapped(state: ReviewState):
        review_id = str(state.get("review_id", "") or "")
        start_stage(review_id, stage)
        span = start_trace_span(review_id=review_id, stage=stage)
        try:
            result = func(state)
        except Exception as exc:
            finish_stage(review_id, stage, status="error")
            finish_trace_span(span, status="error", error=str(exc))
            raise
        finish_stage(review_id, stage, status="done")
        finish_trace_span(span, status="done")
        return result

    wrapped.__name__ = f"timed_{stage}"
    return wrapped


def route_after_vision(state: ReviewState) -> str:
    if state.get("human_confirmation_required", False):
        return "stop_for_confirmation"
    if state.get("needs_confirmation") or not state.get("transcript_confirmed", False):
        return "stop_for_confirmation"
    return "solver"


def route_after_solver(state: ReviewState) -> str:
    if state.get("status") == "UNSUPPORTED_TASK_TYPE":
        return "solver_failed"
    return "verify_reference"


def route_after_task_profile(state: ReviewState) -> str:
    return "continue" if state.get("task_profile_ok", False) else "unsupported"


def route_after_reference(state: ReviewState) -> str:
    # A human-confirmed EGE-13 solution must always reach Grader and receive a
    # score. Reference verification is strong evidence when available, but a
    # verifier limitation is an advisory condition, not a reason to skip grading.
    return "grade"


def route_after_diagram_verify(state: ReviewState) -> str:
    """Legacy compatibility helper. Diagram nodes are not part of the active graph."""
    return "grade"


def _wire_tail(graph: StateGraph) -> None:
    graph.add_node("verify_reference", _timed("verify_reference", reference_verifier_agent))
    graph.add_node("grader", _timed("grader", grader_agent))
    graph.add_node("reviewer", _timed("reviewer", reviewer_agent))
    graph.add_node("build_report", _timed("build_report", build_user_report_node))
    graph.add_node("persist_review", _timed("persist_review", persist_review_node))

    graph.add_conditional_edges(
        "verify_reference",
        route_after_reference,
        {"grade": "grader"},
    )
    graph.add_edge("grader", "reviewer")
    graph.add_edge("reviewer", "build_report")
    graph.add_edge("build_report", "persist_review")
    graph.add_edge("persist_review", END)


def build_review_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("load_task_profile", load_task_profile_node)
    graph.add_node("vision", _timed("vision", vision_agent))
    graph.add_node("solver", _timed("solver", solver_agent))
    _wire_tail(graph)

    graph.add_edge(START, "load_task_profile")
    graph.add_conditional_edges(
        "load_task_profile",
        route_after_task_profile,
        {"unsupported": END, "continue": "vision"},
    )
    graph.add_conditional_edges(
        "vision",
        route_after_vision,
        {"stop_for_confirmation": END, "solver": "solver"},
    )
    graph.add_conditional_edges(
        "solver",
        route_after_solver,
        {"solver_failed": "verify_reference", "verify_reference": "verify_reference"},
    )
    return graph.compile()


def build_post_confirmation_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("load_task_profile", load_task_profile_node)
    graph.add_node("solver", _timed("solver", solver_agent))
    _wire_tail(graph)

    graph.add_edge(START, "load_task_profile")
    graph.add_conditional_edges(
        "load_task_profile",
        route_after_task_profile,
        {"unsupported": END, "continue": "solver"},
    )
    graph.add_edge("solver", "verify_reference")
    return graph.compile()


review_graph = build_review_graph()
post_confirmation_graph = build_post_confirmation_graph()
