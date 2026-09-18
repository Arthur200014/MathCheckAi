#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "== MathCheck AI: setup =="

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Ошибка: python3.12 не найден. Установи Python 3.12 и повтори запуск."
  exit 1
fi

if [ ! -f ".env.local" ]; then
  cp .env.example .env.local
  echo "Создан .env.local из .env.example"
fi

echo "Пересоздаю чистое виртуальное окружение..."
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Готово. Для запуска: bash run.sh"
