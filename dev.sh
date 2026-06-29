#!/usr/bin/env bash
# dev.sh — start API server + Next.js dev server together.
# Usage: ./dev.sh
# Ctrl-C kills both.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Colour helpers
GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'

cleanup() {
  echo ""
  echo -e "${CYAN}Stopping servers…${RESET}"
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
  wait "$API_PID" "$WEB_PID" 2>/dev/null || true
  echo -e "${GREEN}Done.${RESET}"
}
trap cleanup EXIT INT TERM

echo -e "${CYAN}Starting API  →  http://localhost:8000${RESET}"
"$ROOT/.venv/bin/uvicorn" scribe.api.app:app --reload --app-dir "$ROOT" 2>&1 \
  | sed 's/^/[api] /' &
API_PID=$!

echo -e "${CYAN}Starting Web  →  http://localhost:3000${RESET}"
cd "$ROOT/web" && npm run dev 2>&1 \
  | sed 's/^/[web] /' &
WEB_PID=$!

echo -e "${GREEN}Both servers running. Ctrl-C to stop.${RESET}"
wait "$API_PID" "$WEB_PID"
