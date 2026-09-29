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
  local credential_var="${3:-OPENROUTER_API_KEY}"
  if openshell provider get "$provider_name" >/dev/null 2>&1; then
    return 0
  fi
  if [[ -z "${!credential_var:-}" ]]; then
    echo "$credential_var is not configured for $provider_name." >&2
    return 2
  fi
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
  local providers_csv="$5"
  shift 5

  local provider_args=()
  local provider
  local -a _providers=()
  IFS=',' read -r -a _providers <<< "$providers_csv"
  for provider in "${_providers[@]}"; do
    [[ -n "$provider" ]] && provider_args+=(--provider "$provider")
  done

  sb_sandbox_delete "$name" "$port"
  openshell sandbox create \
    --name "$name" \
    --from "$image" \
    --policy "$policy" \
    "${provider_args[@]}" \
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
