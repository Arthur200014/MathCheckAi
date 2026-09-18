from pathlib import Path


def test_graph_has_four_agent_nodes_in_one_langgraph_flow():
    text = (Path(__file__).resolve().parents[1] / "src/graph.py").read_text(encoding="utf-8")
    for node in ["vision", "solver", "grader", "reviewer"]:
        assert f'add_node("{node}"' in text

    # Local runtime is deliberately sequential: same four agents, no fake
    # disconnected single-agent demos, and no same-model parallel contention.
    assert '{"unsupported": END, "continue": "vision"}' in text
    assert '{"stop_for_confirmation": END, "solver": "solver"}' in text
    assert 'graph.add_edge("grader", "reviewer")' in text
