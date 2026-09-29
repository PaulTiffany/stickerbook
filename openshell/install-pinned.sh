#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/openshell/PIN.env"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

installer="https://raw.githubusercontent.com/NVIDIA/OpenShell/${OPENSHELL_COMMIT}/install.sh"
echo "Fetching pinned OpenShell installer: ${OPENSHELL_COMMIT}"
curl -fLsS "$installer" -o "$tmp"

echo "Installing ${OPENSHELL_VERSION}"
OPENSHELL_VERSION="$OPENSHELL_VERSION" sh "$tmp"

echo
openshell --version
openshell status
