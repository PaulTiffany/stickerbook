#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.stickerbook-runtime"
LOGS="$STATE/logs"
UPSTREAM="$STATE/upstream/Omega"
OMEGA_COMMIT="ee0618a293ec3662a32b10b09c6cbb073f59d6b2"
CHROMADB_COMMIT="218484875d5d1bfb217a9a03d3983dc1ed9d406c"

mkdir -p "$LOGS" "$(dirname "$UPSTREAM")"
export PATH="$HOME/.local/bin:$PATH"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "StickerBook needs '$1' in WSL." >&2
    exit 2
  }
}

need git
need docker
need python3

docker info >/dev/null 2>&1 || {
  echo "Docker is not running or is not available inside WSL." >&2
  echo "Start Docker Desktop, then run Start StickerBook again." >&2
  exit 2
}

# OpenShell is pinned project infrastructure. Install/repair the pin when the
# exact version is not available; the installer URL itself is commit-pinned.
if ! command -v openshell >/dev/null 2>&1 \
   || ! openshell --version 2>/dev/null | grep -q '0\.1\.2'; then
  bash "$ROOT/openshell/install-pinned.sh"
  hash -r
fi
need openshell
openshell status >/dev/null

# Build the exact Omega baseline only once. Derived images are rebuilt each
# launch so a git pull cannot leave an older service image running.
if ! docker image inspect omega-jev:baseline >/dev/null 2>&1; then
  echo "First run: preparing pinned Omega baseline..."
  rm -rf "$UPSTREAM"
  git init -q "$UPSTREAM"
  git -C "$UPSTREAM" remote add origin https://github.com/singnet/Omega.git
  git -C "$UPSTREAM" fetch -q --depth 1 origin "$OMEGA_COMMIT"
  git -C "$UPSTREAM" checkout -q --detach FETCH_HEAD
  test "$(git -C "$UPSTREAM" rev-parse HEAD)" = "$OMEGA_COMMIT"
  docker build \
    --build-arg CHROMADB_REF="$CHROMADB_COMMIT" \
    -t omega-jev:baseline "$UPSTREAM"
fi

echo "Building current StickerBook Omega images..."
docker build -t omega-jev:experiment -f "$ROOT/jev/Dockerfile.jev" "$ROOT"
docker build -t stickerbook-omega-jev:openshell -f "$ROOT/jev/Dockerfile.openshell" "$ROOT"
docker build -t stickerbook-omega-llm:experiment -f "$ROOT/llm/Dockerfile.omega-llm" "$ROOT"
docker build -t stickerbook-omega-llm:openshell -f "$ROOT/llm/Dockerfile.openshell" "$ROOT"

# Provider credentials live in OpenShell, not in repo state. Prompt only when
# one of the two role-specific provider instances still needs to be created.
need_key=0
openshell provider get stickerbook-openrouter-omega-llm >/dev/null 2>&1 || need_key=1
openshell provider get stickerbook-openrouter-omega-jev >/dev/null 2>&1 || need_key=1
if [[ "$need_key" -eq 1 && -z "${OPENROUTER_API_KEY:-}" ]]; then
  printf 'OpenRouter API key (first setup only; input is hidden): ' >&2
  IFS= read -r -s OPENROUTER_API_KEY
  printf '\n' >&2
  if [[ -z "$OPENROUTER_API_KEY" ]]; then
    echo "No key entered; powered StickerBook was not started." >&2
    exit 2
  fi
  export OPENROUTER_API_KEY
fi

# Cleanly replace only StickerBook-owned runtime processes/sandboxes.
bash "$ROOT/runtime/stop.sh" --quiet || true

echo "Starting bounded OmegaLLM..."
bash "$ROOT/openshell/run-omega-llm-service.sh"
echo "Starting bounded OmegaJev..."
bash "$ROOT/openshell/run-omega-jev-service.sh"

# Refuse to mask an untracked old bridge process.
if python3 - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8756/api/state", timeout=.5).read()
PY
then
  echo "Port 8756 is already serving an untracked StickerBook bridge." >&2
  echo "Close that older bridge before starting the governed runtime." >&2
  exit 2
fi

echo "Starting StickerBook authority kernel + browser bridge..."
nohup env \
  STICKERBOOK_OMEGA_LLM_URL=http://127.0.0.1:8761 \
  STICKERBOOK_OMEGA_JEV_URL=http://127.0.0.1:8762 \
  STICKERBOOK_OMEGA_TIMEOUT=45 \
  STICKERBOOK_PORT=8756 \
  python3 "$ROOT/web/bridge.py" \
  >"$LOGS/bridge.log" 2>&1 &
bridge_pid=$!
echo "$bridge_pid" > "$STATE/bridge.pid"

for _ in $(seq 1 60); do
  if python3 - <<'PY' >/dev/null 2>&1
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8756/api/state", timeout=1) as r:
    state=json.load(r)
caps=state.get("capabilities", {})
if not caps.get("conversational_agent") or not caps.get("jev_controller"):
    raise SystemExit(1)
PY
  then
    echo "StickerBook READY: http://127.0.0.1:8756/"
    echo "Voice is available from the adult-controlled push-to-talk toggle."
    exit 0
  fi
  if ! kill -0 "$bridge_pid" 2>/dev/null; then
    echo "StickerBook bridge exited during startup." >&2
    tail -n 80 "$LOGS/bridge.log" >&2 || true
    exit 1
  fi
  sleep 0.5
done

echo "StickerBook bridge did not become ready." >&2
tail -n 80 "$LOGS/bridge.log" >&2 || true
exit 1
