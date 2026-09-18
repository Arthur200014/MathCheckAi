from src.llm.config import DEFAULT_VISION_MODEL, get_vision_model


def test_default_model(monkeypatch):
    monkeypatch.delenv("OLLAMA_VISION_MODEL", raising=False)
    assert get_vision_model() == DEFAULT_VISION_MODEL


def test_model_can_be_switched_without_code_change(monkeypatch):
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "another-vision-model")
    assert get_vision_model() == "another-vision-model"
