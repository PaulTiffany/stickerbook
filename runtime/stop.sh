#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.stickerbook-runtime"
quiet=0
[[ "${1:-}" == "--quiet" ]] && quiet=1

if [[ -f "$STATE/bridge.pid" ]]; then
  pid="$(cat "$STATE/bridge.pid" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$STATE/bridge.pid"
fi

if command -v openshell >/dev/null 2>&1; then
  openshell forward stop 8762 stickerbook-omega-jev >/dev/null 2>&1 || true
  openshell forward stop 8761 stickerbook-omega-llm >/dev/null 2>&1 || true
  openshell sandbox delete stickerbook-omega-jev >/dev/null 2>&1 || true
  openshell sandbox delete stickerbook-omega-llm >/dev/null 2>&1 || true
fi

if [[ "$quiet" -eq 0 ]]; then
  echo "StickerBook stopped."
fi
