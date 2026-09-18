#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "== MathCheck AI: update =="

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Остановка: есть локальные изменения в отслеживаемых файлах."
  echo "Сначала закоммить их или откати, затем повтори обновление."
  git status --short
  exit 1
fi

echo "Получаю последнюю версию из GitHub..."
git pull --ff-only

echo "Пересоздаю чистое виртуальное окружение для новой версии..."
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env.local" ]; then
  cp .env.example .env.local
  echo "Создан .env.local из .env.example"
fi

echo
echo "Обновление завершено."
echo "Текущий commit: $(git rev-parse --short HEAD)"
echo "Для запуска: bash run.sh"
