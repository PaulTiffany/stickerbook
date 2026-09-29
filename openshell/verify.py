"""Repository-level checks for the pinned OpenShell integration.

These checks do not claim a live sandbox was exercised in CI. They protect the
static contract: immutable pin, default-deny sandbox policies, provider-only
OpenRouter access, non-root OpenShell image, and an explicit Jev transport mode.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


pin = read("openshell/PIN.env")
assert "OPENSHELL_VERSION=v0.1.2" in pin
assert "OPENSHELL_COMMIT=6648bd0c290efbc41ba131ee9831ee45cd431f94" in pin

for path in (
    "openshell/policies/omega-jev.yaml",
    "openshell/policies/omega-llm.yaml",
):
    policy = read(path)
    assert "network_policies: {}" in policy
    assert "include_workdir: false" in policy
    assert "/PeTTa/repos/Omega/memory" in policy
    assert "openrouter.ai" not in policy

for path in (
    "openshell/providers/openrouter-omega-jev.yaml",
    "openshell/providers/openrouter-omega-llm.yaml",
):
    profile = read(path)
    assert "host: openrouter.ai" in profile
    assert "enforcement: enforce" in profile
    assert "OPENROUTER_API_KEY" in profile
    binary_lines = []
    in_binaries = False
    for line in profile.splitlines():
        if line.strip() == "binaries:":
            in_binaries = True
            continue
        if in_binaries:
            if line.startswith("  - "):
                binary_lines.append(line[4:].strip())
                continue
            if line and not line.startswith(" "):
                break
    assert binary_lines == ["/usr/local/bin/swipl", "/usr/bin/swipl"]

dockerfile = read("jev/Dockerfile.openshell")
assert "USER 65534:65534" in dockerfile
assert "stickerbook-openshell-entrypoint" in dockerfile

entrypoint = read("jev/openshell-entrypoint.sh")
assert "env -i" in entrypoint
assert "OPENROUTER_API_KEY" in entrypoint
entrypoint_code = "\n".join(
    line for line in entrypoint.splitlines()
    if not line.lstrip().startswith("#")
)
assert "/opt/nginx" not in entrypoint_code
assert "nginx.sh" not in entrypoint_code
assert " su " not in (" " + entrypoint_code.replace("\n", " ") + " ")

jev = read("jev/omega_jev/providers/jev.py")
assert "OpenShellProviderTransport" in jev
assert 'jevTransport' in jev
assert 'https://openrouter.ai' in jev

print("OpenShell static integration contract: PASS")
