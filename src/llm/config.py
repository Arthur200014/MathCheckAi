import os

                                                                                 
DEFAULT_VISION_MODEL = "qwen3-vl:4b-instruct"
DEFAULT_SOLVER_MODEL = "qwen3-vl:4b-instruct"
DEFAULT_GRADER_MODEL = "qwen3-vl:4b-instruct"
DEFAULT_REVIEWER_MODEL = "qwen3-vl:4b-instruct"
DEFAULT_DIAGRAM_MODEL = "qwen3-vl:4b-instruct"

                                                                        
                                                                        
BENCHMARK_VISION_MODELS = [
    "qwen3-vl:4b-instruct",
    "gemma3:4b",
    "granite3.2-vision:2b",
]


def get_vision_model() -> str:
    return os.getenv("OLLAMA_VISION_MODEL", DEFAULT_VISION_MODEL)


def get_solver_model() -> str:
    return os.getenv("OLLAMA_SOLVER_MODEL", DEFAULT_SOLVER_MODEL)


def get_grader_model() -> str:
    return os.getenv("OLLAMA_GRADER_MODEL", DEFAULT_GRADER_MODEL)


def get_reviewer_model() -> str:
    return os.getenv("OLLAMA_REVIEWER_MODEL", DEFAULT_REVIEWER_MODEL)


def get_diagram_model() -> str:
    return os.getenv("OLLAMA_DIAGRAM_MODEL", os.getenv("OLLAMA_VISION_MODEL", DEFAULT_DIAGRAM_MODEL))


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
# fix
