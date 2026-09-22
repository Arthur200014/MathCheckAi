#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

echo "[1/3] Compile eval scripts"
python -m py_compile evals/run_ege13_benchmark.py evals/prepare_ege13_images.py evals/validate_ege13_release.py

echo "[2/3] Deterministic EGE-13 release gate"
python evals/validate_ege13_release.py

echo "[3/3] Unit/integration tests"
pytest -q

echo "RELEASE CHECK OK"
