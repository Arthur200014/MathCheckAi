from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.grader import grader_agent
from src.agents.persistence import persist_review_node
from src.agents.reference_verifier import reference_verifier_agent
from src.agents.reviewer import reviewer_agent
from src.agents.solver import solver_agent
from src.agents.vision import vision_agent
from src.state import ReviewState
from src.task_registry import load_task_profile_node
from src.tools.ege13_report_v2 import build_compact_report_node


def route_after_vision(state: ReviewState) -> str:
    # Photo OCR is a draft only. A photo review can never continue directly
    # from Vision to Solver, even if a future Vision implementation accidentally
    # reports high confidence / transcript_confirmed=True.
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


def route_post_confirmation(state: ReviewState) -> str:
    # A pending state from a future/alternate runtime may already contain Solver
    # output. Reuse it when available; otherwise run Solver now.
    if state.get("solver_model") or state.get("solver_machine_spec"):
        return "verify_reference"
    return "solver"


def route_after_reference(state: ReviewState) -> str:
    return "grade" if state.get("reference_verification_ok", False) else "review"


def _wire_tail(graph: StateGraph) -> None:
    graph.add_node("verify_reference", reference_verifier_agent)
    graph.add_node("grader", grader_agent)
    graph.add_node("reviewer", reviewer_agent)
    graph.add_node("build_report", build_compact_report_node)
    graph.add_node("persist_review", persist_review_node)

    graph.add_conditional_edges(
        "verify_reference",
        route_after_reference,
        {"grade": "grader", "review": "reviewer"},
    )
    graph.add_edge("grader", "reviewer")
    graph.add_edge("reviewer", "build_report")
    graph.add_edge("build_report", "persist_review")
    graph.add_edge("persist_review", END)


def build_review_graph():
    """Four real agents, sequenced for one local accelerator.

    Running Vision and Solver concurrently with the same local 4B model on a
    16 GB Mac can create accelerator/context contention. The project does not
    require parallel agents, so the default runtime is the simpler and usually
    faster chain: Vision -> Solver -> verifier -> Grader -> Reviewer.
    """
    graph = StateGraph(ReviewState)
    graph.add_node("load_task_profile", load_task_profile_node)
    graph.add_node("vision", vision_agent)
    graph.add_node("solver", solver_agent)
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
    graph.add_node("solver", solver_agent)
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
