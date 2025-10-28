#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT"

python3 -m venv backend/.venv
source backend/.venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

echo "Backend environment ready. Activate with: source backend/.venv/bin/activate"
