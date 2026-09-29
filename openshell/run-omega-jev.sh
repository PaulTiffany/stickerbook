#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${STICKERBOOK_OPENSHELL_JEV_NAME:-stickerbook-jev}"
IMAGE="${STICKERBOOK_OPENSHELL_JEV_IMAGE:-stickerbook-omega-jev:openshell}"
PROVIDER="${STICKERBOOK_OPENSHELL_JEV_PROVIDER:-stickerbook-openrouter-omega-jev}"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY must be set in the host shell for provider creation." >&2
  exit 2
fi

openshell status >/dev/null

docker build -t "$IMAGE" -f "$ROOT/jev/Dockerfile.openshell" "$ROOT"

openshell profile lint -f "$ROOT/openshell/providers/openrouter-omega-jev.yaml"
openshell profile import -f "$ROOT/openshell/providers/openrouter-omega-jev.yaml"

# Provider creation is intentionally explicit. If the provider already exists,
# OpenShell will refuse rather than silently replacing stored credentials.
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  openshell provider create \
    --name "$PROVIDER" \
    --type stickerbook-openrouter-omega-jev \
    --from-existing

openshell sandbox create \
  --name "$NAME" \
  --from "$IMAGE" \
  --policy "$ROOT/openshell/policies/omega-jev.yaml" \
  --provider "$PROVIDER" \
  -- \
  jevTransport=openshell \
  jevActionSet=stickerbook \
  jevProfile=local-single-agent
