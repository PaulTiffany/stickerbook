#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/runtime/lib.sh"

NAME="${STICKERBOOK_OPENSHELL_LLM_NAME:-stickerbook-omega-llm}"
IMAGE="${STICKERBOOK_OPENSHELL_LLM_IMAGE:-stickerbook-omega-llm:openshell}"
PORT="${STICKERBOOK_OMEGA_LLM_PORT:-8761}"

declare -a PROVIDERS=()

add_provider() {
  local profile_id="$1"
  local provider_name="$2"
  local credential_var="$3"
  local file="$4"

  sb_profile_apply "$profile_id" "$file"
  if sb_provider_ensure "$provider_name" "$profile_id" "$credential_var"; then
    PROVIDERS+=("$provider_name")
    return 0
  fi

  local code=$?
  if [[ "$code" -eq 2 ]]; then
    echo "OmegaLLM option unavailable until $credential_var is configured: $provider_name" >&2
    return 0
  fi
  return "$code"
}

# OpenRouter is always present because OmegaJev requires it, and it remains the
# safe fallback when the sponsored lane is unavailable.
add_provider   stickerbook-openrouter-omega-llm   stickerbook-openrouter-omega-llm   OPENROUTER_API_KEY   "$ROOT/openshell/providers/openrouter-omega-llm.yaml"

# Optional parent-selectable OmegaLLM lanes.
add_provider   stickerbook-asicloud-omega-llm   stickerbook-asicloud-omega-llm   ASI_API_KEY   "$ROOT/openshell/providers/asicloud-omega-llm.yaml"
add_provider   stickerbook-anthropic-omega-llm   stickerbook-anthropic-omega-llm   ANTHROPIC_API_KEY   "$ROOT/openshell/providers/anthropic-omega-llm.yaml"
add_provider   stickerbook-openai-omega-llm   stickerbook-openai-omega-llm   OPENAI_API_KEY   "$ROOT/openshell/providers/openai-omega-llm.yaml"
add_provider   stickerbook-asione-omega-llm   stickerbook-asione-omega-llm   ASIONE_API_KEY   "$ROOT/openshell/providers/asione-omega-llm.yaml"

provider_csv="$(IFS=,; echo "${PROVIDERS[*]}")"
if [[ -z "$provider_csv" ]]; then
  echo "OmegaLLM has no configured inference provider." >&2
  exit 2
fi

sb_sandbox_create_service   "$NAME" "$PORT" "$IMAGE" "$ROOT/openshell/policies/omega-llm.yaml" "$provider_csv"   commchannel=stickerbookrpc   stickerbookRpcRole=omegallm   stickerbookRpcPort="$PORT"   provider=StickerBookLLM   maxNewInputLoops=1   maxWakeLoops=0

sb_wait_health "http://127.0.0.1:$PORT/health" omegallm
echo "OmegaLLM ready on loopback port $PORT"
