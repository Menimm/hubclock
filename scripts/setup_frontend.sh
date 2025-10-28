#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT/frontend"

CACHE_DIR="$PROJECT_ROOT/.cache/npm"
mkdir -p "$CACHE_DIR"

npm_config_cache="$CACHE_DIR" npm install

echo "Frontend dependencies installed. Start dev server with: npm run dev"
