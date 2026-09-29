#!/usr/bin/env bash
set -euo pipefail

sb_profile_apply() {
  local profile_id="$1"
  local file="$2"
  openshell profile lint --file "$file" >/dev/null
  if openshell profile describe "$profile_id" >/dev/null 2>&1; then
    openshell profile update "$profile_id" --file "$file" >/dev/null
  else
    openshell profile import --file "$file" >/dev/null
  fi
}

sb_provider_ensure() {
  local provider_name="$1"
  local profile_id="$2"
  if openshell provider get "$provider_name" >/dev/null 2>&1; then
    return 0
  fi
  if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "OpenRouter credential is required once to create $provider_name." >&2
    return 2
  fi
  OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
    openshell provider create \
      --name "$provider_name" \
      --type "$profile_id" \
      --from-existing >/dev/null
}

sb_sandbox_delete() {
  local name="$1"
  local port="$2"
  openshell forward stop "$port" "$name" >/dev/null 2>&1 || true
  if openshell sandbox get "$name" >/dev/null 2>&1; then
    openshell sandbox delete "$name" >/dev/null
    local i
    for i in $(seq 1 40); do
      if ! openshell sandbox get "$name" >/dev/null 2>&1; then
        return 0
      fi
      sleep 0.25
    done
    echo "OpenShell sandbox $name did not disappear after delete." >&2
    return 1
  fi
}

sb_sandbox_create_service() {
  local name="$1"
  local port="$2"
  local image="$3"
  local policy="$4"
  local provider="$5"
  shift 5

  sb_sandbox_delete "$name" "$port"
  openshell sandbox create \
    --name "$name" \
    --from "$image" \
    --policy "$policy" \
    --provider "$provider" \
    --approval-mode manual \
    --forward "127.0.0.1:$port" \
    --detach \
    -- "$@" >/dev/null
}

sb_wait_health() {
  local url="$1"
  local role="$2"
  local i
  for i in $(seq 1 120); do
    if python3 - "$url" "$role" <<'PY' >/dev/null 2>&1
import json, sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=1) as r:
    body = json.load(r)
if body.get("ok") is not True or body.get("role") != sys.argv[2]:
    raise SystemExit(1)
PY
    then
      return 0
    fi
    sleep 0.5
  done
  echo "Timed out waiting for $role at $url" >&2
  return 1
}
