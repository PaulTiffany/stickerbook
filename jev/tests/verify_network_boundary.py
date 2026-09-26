"""
Verify the agent/gateway split and network isolation.

Root SECURITY.md section 21 target shape:

    OmegaJev container            Gateway
      no provider secret   ->       provider secret
      no general Internet           provider-only egress
      StickerBook tools             no StickerBook authority

Run from the jev/ directory (needs Docker and the jev-gateway container up):

    python tests/verify_network_boundary.py
"""

from __future__ import annotations

import json
import subprocess
import sys

AGENT_IMAGE = "omega-jev:experiment"
INTERNAL = "jev-internal"
GATEWAY = "jev-gateway"

failures = []


def check(label, condition, detail=""):
    print("  [%s] %s%s" % ("PASS" if condition else "FAIL", label,
                           ("  -- " + detail) if detail else ""))
    if not condition:
        failures.append(label)


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def on_internal(script):
    """Run a shell snippet on the agent's network, in a throwaway container."""
    return docker("run", "--rm", "--network", INTERNAL, "alpine:latest",
                  "sh", "-c", script).stdout.strip()


print("=" * 70)
print("NETWORK TOPOLOGY")
print("=" * 70)
out = docker("network", "inspect", INTERNAL, "--format", "{{.Internal}}")
check("agent network is a Docker 'internal' network (no external route)",
      out.stdout.strip() == "true", out.stdout.strip())

print()
print("=" * 70)
print("EGRESS: the agent's network cannot reach the Internet")
print("=" * 70)
for host in ("https://openrouter.ai/", "https://github.com/",
             "https://pypi.org/"):
    result = on_internal(
        "wget -qO- --timeout=4 %s >/dev/null 2>&1 && echo REACHABLE "
        "|| echo BLOCKED" % host)
    check("%-24s unreachable from agent network" % host.split("//")[1].rstrip("/"),
          result == "BLOCKED", result)

dns = on_internal("nslookup openrouter.ai >/dev/null 2>&1 && echo RESOLVES || echo NO-DNS")
print("  [info] external DNS from agent network: %s "
      "(egress is blocked regardless)" % dns)

print()
print("=" * 70)
print("THE ONE PERMITTED DESTINATION")
print("=" * 70)
health = on_internal(
    "wget -qO- --timeout=5 http://%s:8080/health 2>&1 || echo FAILED" % GATEWAY)
check("gateway reachable from the agent network", health == "ok", health)

code = on_internal(
    "wget -S -qO- --timeout=5 http://%s:8080/ 2>&1 | grep -c '404' || true"
    % GATEWAY)
check("gateway refuses non-/jev/ paths (not an open proxy)",
      code not in ("", "0"), "404 responses: " + code)

print()
print("=" * 70)
print("GATEWAY IS NOT REACHABLE FROM THE HOST")
print("=" * 70)
ports = docker("port", GATEWAY).stdout.strip()
check("gateway publishes no ports", ports == "", repr(ports))

print()
print("=" * 70)
print("THE AGENT HOLDS NO CREDENTIAL")
print("=" * 70)
inspect = docker("inspect", AGENT_IMAGE, "--format", "{{json .Config.Env}}")
env = json.loads(inspect.stdout or "[]")
check("agent image environment has no OPENROUTER_API_KEY",
      not any("OPENROUTER_API_KEY" in e for e in env),
      ", ".join(e.split("=")[0] for e in env)[:90])

started = docker("run", "-d", "--rm", "--network", INTERNAL,
                 "--entrypoint", "sleep", AGENT_IMAGE, "20")
cid = started.stdout.strip()
if cid:
    live = json.loads(docker("inspect", cid, "--format",
                             "{{json .Config.Env}}").stdout or "[]")
    check("running agent container has no OPENROUTER_API_KEY",
          not any("OPENROUTER_API_KEY" in e for e in live))
    docker("rm", "-f", cid)
else:
    check("could start an agent container to inspect", False,
          started.stderr.strip()[:80])

print()
print("=" * 70)
print("NO PROXY CONFIG OR SECRET PATH INSIDE THE AGENT IMAGE")
print("=" * 70)
probe = docker("run", "--rm", "--entrypoint", "sh", AGENT_IMAGE, "-c",
               "ls /opt/nginx/ 2>/dev/null; echo '---'; cat /opt/nginx/nginx.sh 2>/dev/null")
text = probe.stdout
check("no nginx.conf.template in the agent image",
      "nginx.conf.template" not in text, text.replace("\n", " ")[:70])
check("no generated nginx.conf in the agent image",
      "nginx.conf\n" not in text and "nginx.conf " not in text)
check("nginx startup hook is a no-op", "exit 0" in text,
      text.split("---")[-1].strip()[:40])

print()
print("=" * 70)
print("THE GATEWAY HOLDS THE SECRET (and only the gateway)")
print("=" * 70)
genv = json.loads(docker("inspect", GATEWAY, "--format",
                         "{{json .Config.Env}}").stdout or "[]")
check("gateway container does hold OPENROUTER_API_KEY",
      any(e.startswith("OPENROUTER_API_KEY=") for e in genv),
      "this is the intended location for it")
check("gateway contains no Omega/agent code",
      docker("run", "--rm", "--entrypoint", "sh", "jev-gateway:1", "-c",
             "test -d /PeTTa && echo yes || echo no").stdout.strip() == "no")

print()
print("=" * 70)
if failures:
    print("RESULT: %d CHECK(S) FAILED: %s" % (len(failures), failures))
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
sys.exit(0)
