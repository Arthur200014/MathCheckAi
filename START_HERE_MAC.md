# Быстрый запуск на macOS

```bash
cd ~/Downloads/mathcheck-ai-stage2.9.7.8-ege13-human-readable-editor
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OLLAMA_VISION_MODEL=qwen3-vl:4b-instruct
export OLLAMA_SOLVER_MODEL=qwen3-vl:4b-instruct
export OLLAMA_GRADER_MODEL=qwen3-vl:4b-instruct
export OLLAMA_REVIEWER_MODEL=qwen3-vl:4b-instruct
export OLLAMA_KEEP_ALIVE=15m
export OLLAMA_VISION_NUM_CTX=16384
export OLLAMA_CONNECT_TIMEOUT_SECONDS=15
export OLLAMA_IDLE_TIMEOUT_SECONDS=180
export OLLAMA_VISION_TOTAL_TIMEOUT_SECONDS=900
export OLLAMA_TEXT_TOTAL_TIMEOUT_SECONDS=900

uvicorn src.api:app --reload
```

После запуска открой:

- интерфейс: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`
- health: `http://127.0.0.1:8000/health`

В основном интерфейсе теперь вводится только ID ученика и загружается **одно фото**. Vision извлекает из него и условие, и решение. На следующем экране проверь/исправь оба поля и нажми кнопку подтверждения. Финальный JSON остаётся внизу страницы для копирования.
