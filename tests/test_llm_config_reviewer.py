from src.llm.config import get_reviewer_model


def test_reviewer_model_can_be_selected_independently(monkeypatch):
    monkeypatch.setenv("OLLAMA_REVIEWER_MODEL", "reviewer-model-test")
    assert get_reviewer_model() == "reviewer-model-test"
