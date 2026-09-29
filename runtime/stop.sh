#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.stickerbook-runtime"
source "$ROOT/runtime/lib.sh"
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
  sb_sandbox_delete stickerbook-jev 8762 || true
  sb_sandbox_delete stickerbook-llm 8761 || true
fi

if [[ "$quiet" -eq 0 ]]; then
  echo "StickerBook stopped."
fi
