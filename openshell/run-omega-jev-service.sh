#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/runtime/lib.sh"

NAME="${STICKERBOOK_OPENSHELL_JEV_NAME:-stickerbook-omega-jev}"
IMAGE="${STICKERBOOK_OPENSHELL_JEV_IMAGE:-stickerbook-omega-jev:openshell}"
PROFILE="stickerbook-openrouter-omega-jev"
PROVIDER="${STICKERBOOK_OPENSHELL_JEV_PROVIDER:-stickerbook-openrouter-omega-jev}"
PORT="${STICKERBOOK_OMEGA_JEV_PORT:-8762}"

sb_profile_apply "$PROFILE" "$ROOT/openshell/providers/openrouter-omega-jev.yaml"
sb_provider_ensure "$PROVIDER" "$PROFILE"

sb_sandbox_create_service \
  "$NAME" "$PORT" "$IMAGE" "$ROOT/openshell/policies/omega-jev.yaml" "$PROVIDER" \
  commchannel=stickerbookrpc \
  stickerbookRpcRole=omegajev \
  stickerbookRpcPort="$PORT" \
  provider=Jev \
  jevTransport=openshell \
  jevActionSet=stickerbook-rpc \
  maxNewInputLoops=1 \
  maxWakeLoops=0

sb_wait_health "http://127.0.0.1:$PORT/health" omegajev
echo "OmegaJev ready on loopback port $PORT"
