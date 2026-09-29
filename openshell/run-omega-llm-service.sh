#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/runtime/lib.sh"

NAME="${STICKERBOOK_OPENSHELL_LLM_NAME:-stickerbook-omega-llm}"
IMAGE="${STICKERBOOK_OPENSHELL_LLM_IMAGE:-stickerbook-omega-llm:openshell}"
PROFILE="stickerbook-openrouter-omega-llm"
PROVIDER="${STICKERBOOK_OPENSHELL_LLM_PROVIDER:-stickerbook-openrouter-omega-llm}"
PORT="${STICKERBOOK_OMEGA_LLM_PORT:-8761}"

sb_profile_apply "$PROFILE" "$ROOT/openshell/providers/openrouter-omega-llm.yaml"
sb_provider_ensure "$PROVIDER" "$PROFILE"

sb_sandbox_create_service \
  "$NAME" "$PORT" "$IMAGE" "$ROOT/openshell/policies/omega-llm.yaml" "$PROVIDER" \
  commchannel=stickerbookrpc \
  stickerbookRpcRole=omegallm \
  stickerbookRpcPort="$PORT" \
  provider=StickerBookLLM \
  maxNewInputLoops=1 \
  maxWakeLoops=0

sb_wait_health "http://127.0.0.1:$PORT/health" omegallm
echo "OmegaLLM ready on loopback port $PORT"
