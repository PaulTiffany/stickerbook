#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.stickerbook-runtime"

probe() {
  local label="$1" url="$2"
  if python3 - "$url" <<'PY' >/dev/null 2>&1
import sys, urllib.request
urllib.request.urlopen(sys.argv[1], timeout=1).read()
PY
  then
    printf '%-12s READY  %s\n' "$label" "$url"
  else
    printf '%-12s DOWN   %s\n' "$label" "$url"
  fi
}

probe OmegaLLM http://127.0.0.1:8761/health
probe OmegaJev http://127.0.0.1:8762/health
probe StickerBook http://127.0.0.1:8756/api/state

if command -v openshell >/dev/null 2>&1; then
  printf '\nOpenShell:\n'
  openshell status || true
fi
if [[ -f "$STATE/bridge.pid" ]]; then
  echo "Bridge PID: $(cat "$STATE/bridge.pid")"
fi
