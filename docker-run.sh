#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден. Открой Docker Desktop и проверь установку."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop не запущен. Запусти его и повтори команду."
  exit 1
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama не отвечает на http://127.0.0.1:11434"
  echo "Запусти Ollama и повтори команду."
  exit 1
fi

MODEL="qwen3-vl:4b-instruct"
if ! curl -fsS http://127.0.0.1:11434/api/tags | grep -q "$MODEL"; then
  if command -v ollama >/dev/null 2>&1; then
    echo "Загружаю модель $MODEL..."
    ollama pull "$MODEL"
  else
    echo "Модель $MODEL не найдена. Установи её через Ollama."
    exit 1
  fi
fi

echo "Собираю и запускаю MathCheck через Docker..."
docker compose up --build
