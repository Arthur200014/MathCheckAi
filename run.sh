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

# Это только аварийный потолок для одного текстового агента.
# Частичный JSON не используется: при превышении лимита вызов считается неудачным.
# 5 минут оставляют запас медленной локальной модели, но не дают одному этапу висеть 15 минут.
TEXT_TIMEOUT="${OLLAMA_TEXT_TOTAL_TIMEOUT_SECONDS:-300}"
if ! [[ "$TEXT_TIMEOUT" =~ ^[0-9]+$ ]] || [ "$TEXT_TIMEOUT" -gt 300 ]; then
  TEXT_TIMEOUT=300
fi
export OLLAMA_TEXT_TOTAL_TIMEOUT_SECONDS="$TEXT_TIMEOUT"

OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
if ! curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  echo "Ошибка: Ollama не отвечает по адресу $OLLAMA_URL"
  echo "Запусти Ollama и повтори: bash run.sh"
  exit 1
fi

echo "MathCheck AI запускается..."
echo "Сайт:    http://127.0.0.1:8000/"
echo "Swagger: http://127.0.0.1:8000/docs"
echo "Аварийный лимит одного текстового агента: ${OLLAMA_TEXT_TOTAL_TIMEOUT_SECONDS} с"
echo "Остановка: Ctrl+C"

exec uvicorn src.api:app --reload
