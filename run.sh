#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Виртуальное окружение не найдено. Запускаю setup..."
  bash setup.sh
fi

if [ ! -f ".env.local" ]; then
  cp .env.example .env.local
  echo "Создан .env.local из .env.example"
fi

source .venv/bin/activate
set -a
source .env.local
set +a

OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
if ! curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  echo "Ошибка: Ollama не отвечает по адресу $OLLAMA_URL"
  echo "Запусти Ollama и повтори: bash run.sh"
  exit 1
fi

echo "MathCheck AI запускается..."
echo "Сайт:    http://127.0.0.1:8000/"
echo "Swagger: http://127.0.0.1:8000/docs"
echo "Остановка: Ctrl+C"

exec uvicorn src.api:app --reload
