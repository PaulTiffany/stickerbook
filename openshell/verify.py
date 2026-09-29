"""Repository-level checks for the governed OpenShell runtime.

These are static/mechanical integration checks. They deliberately do NOT claim
that a live OpenShell sandbox, provider request, WSL2 port forward, or browser
session ran in CI.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SWIPL = "/usr/lib/swipl/bin/x86_64-linux/swipl"


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
    assert binary_lines == [CANONICAL_SWIPL]

for path in ("jev/Dockerfile.openshell", "llm/Dockerfile.openshell"):
    dockerfile = read(path)
    assert "USER 65534:65534" in dockerfile
    assert "stickerbook-openshell-entrypoint" in dockerfile

for path in ("jev/openshell-entrypoint.sh", "runtime/omega/openshell-entrypoint.sh"):
    entrypoint = read(path)
    assert "env -i" in entrypoint
    assert "OPENROUTER_API_KEY" in entrypoint
    code = "\n".join(
        line for line in entrypoint.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "/opt/nginx" not in code
    assert "nginx.sh" not in code
    assert " su " not in (" " + code.replace("\n", " ") + " ")

rpc = read("runtime/omega/stickerbookrpc.py")
assert 'ThreadingHTTPServer(("127.0.0.1", port)' in rpc
assert '"omegallm"' in rpc and '"omegajev"' in rpc
assert 'set(payload) - allowed' in rpc
assert 'set(payload) != allowed' in rpc
assert "complete_staged" in rpc

agent_runtime = read("web/agent_runtime.py")
jev_runtime = read("web/jev_runtime.py")
for runtime in (agent_runtime, jev_runtime):
    assert '{"127.0.0.1", "localhost", "::1"}' in runtime
    assert 'parsed.scheme != "http"' in runtime
assert "kernel" not in agent_runtime.split("def converse", 1)[1].split(
    "def creator_draft", 1)[0]
assert '"actions": actions' in jev_runtime

jev = read("jev/omega_jev/providers/jev.py")
assert "OpenShellProviderTransport" in jev
assert '"stickerbook-rpc"' in jev
assert '{"_": "sb-return"}' in jev
assert 'rpc.current_request("omegajev")' in jev
assert '"choice": choice' in jev

llm = read("llm/omega_llm/providers/stickerbook_llm.py")
assert 'providers.registerLLMProvider("StickerBookLLM"' in llm
assert 'module.LLM_COMMANDS.add("sb-return")' in llm
assert 'rpc.current_request("omegallm")' in llm
assert 'clean_goal(decoded.get("goal"))' in llm
assert '"reply": reply' in llm
assert "stickerbook_core" not in llm

llm_image = read("llm/Dockerfile.omega-llm")
assert "omega-jev:baseline" in llm_image
assert "stickerbook_llm.py" in llm_image
assert "stickerbook_core" not in llm_image
assert "jev.py" not in llm_image

for path, port in (
    ("openshell/run-omega-llm-service.sh", "8761"),
    ("openshell/run-omega-jev-service.sh", "8762"),
):
    script = read(path)
    assert "sb_sandbox_create_service" in script
    assert port in script

lib = read("runtime/lib.sh")
assert '--approval-mode manual' in lib
assert '--forward "127.0.0.1:$port"' in lib
assert "--provider" in lib
assert "--detach" in lib
assert "--privileged" not in lib
assert "docker.sock" not in lib

start = read("runtime/start.sh")
assert "ee0618a293ec3662a32b10b09c6cbb073f59d6b2" in start
assert CANONICAL_SWIPL in start
assert "STICKERBOOK_OMEGA_LLM_URL=http://127.0.0.1:8761" in start
assert "STICKERBOOK_OMEGA_JEV_URL=http://127.0.0.1:8762" in start
assert "OPENROUTER_API_KEY" in start
assert ".stickerbook-runtime" in read(".gitignore")
assert "wsl.exe" in read("Start StickerBook.cmd")
assert "runtime/start.sh" in read("Start StickerBook.cmd")
assert "runtime/stop.sh" in read("Stop StickerBook.cmd")

print("Governed OpenShell runtime static contract: PASS")
