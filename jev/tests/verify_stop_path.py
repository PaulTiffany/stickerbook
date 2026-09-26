"""
Verify that the stop path is independent of the agent.

Root SECURITY.md section 19: "Do not put the brake on the same failure path
as the engine." The provider's in-process `jevMaxTurns` counter is a budget;
this proves there is also a real brake.

Two scenarios:

  1. NORMAL   -- the external supervisor stops a healthy run at its own limit,
                 below the in-process limit, so the external control is what
                 actually fires.

  2. WEDGED   -- the provider is pointed at a TCP black hole with a one-hour
                 timeout and an in-process limit of 999, so the in-process
                 counter can NEVER fire. Only an outside observer can end the
                 run. This is the case os._exit() structurally cannot catch.

Takes roughly two to three minutes. Run from the jev/ directory:

    python tests/verify_stop_path.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPERVISE = os.path.join(HERE, "supervise.py")

EXIT_COMPLETED, EXIT_MAX_TURNS, EXIT_STALLED = 0, 10, 11

failures = []


def check(label, condition, detail=""):
    print("  [%s] %s%s" % ("PASS" if condition else "FAIL", label,
                           ("  -- " + detail) if detail else ""))
    if not condition:
        failures.append(label)


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def supervise(*args, timeout=400):
    started = time.monotonic()
    proc = subprocess.run([sys.executable, SUPERVISE, *args],
                          capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - started


print("=" * 70)
print("SCENARIO 1: external supervisor stops a healthy run")
print("=" * 70)
print("  supervisor limit = 2 turns; in-process jevMaxTurns = 6 (the backstop)")
code, out, secs = supervise("--max-turns", "2", "--stall-seconds", "90",
                            "--max-seconds", "300", "--quiet", "--",
                            "jevActionSet=butterfly")
check("supervisor stopped the run (exit 10)", code == EXIT_MAX_TURNS,
      "exit=%d in %ds" % (code, secs))
check("it was the supervisor, not the in-process limit",
      "STOPPED by supervisor (turn limit)" in out)
check("the in-process limit did NOT fire (the supervisor got there first)",
      "in-process limit fired  : False" in out)
check("stop needed no agent cooperation",
      "stopped without agent cooperation" in out)

print()
print("=" * 70)
print("SCENARIO 2: WEDGED provider -- the in-process counter cannot fire")
print("=" * 70)
docker("rm", "-f", "jev-blackhole")
docker("run", "-d", "--name", "jev-blackhole", "--network", "jev-internal",
       "alpine:latest", "sh", "-c",
       "while true; do nc -l -p 8080 >/dev/null; done")
time.sleep(2)
print("  black hole up: accepts TCP, never answers")
print("  jevTimeout=3600  jevMaxTurns=999  -> os._exit() can never run")
try:
    code, out, secs = supervise("--max-turns", "99", "--stall-seconds", "40",
                                "--max-seconds", "180", "--quiet", "--",
                                "jevGatewayUrl=http://jev-blackhole:8080",
                                "jevTimeout=3600", "jevMaxTurns=999")
    check("supervisor stopped the wedged run (exit 11)", code == EXIT_STALLED,
          "exit=%d in %ds" % (code, secs))
    check("it stopped because of the stall detector",
          "stalled: no decision for" in out)
    check("the in-process limit never fired (it was set to 999)",
          "in-process limit fired  : False" in out)
    check("the run could not have ended itself", "exited on its own" not in out)
    check("it terminated well inside the wall-clock deadline", secs < 170,
          "%ds" % secs)
finally:
    docker("rm", "-f", "jev-blackhole")
    docker("rm", "-f", "omega-jev-run")

print()
print("=" * 70)
print("NOTHING LEFT RUNNING")
print("=" * 70)
left = docker("ps", "--filter", "name=omega-jev", "--format", "{{.Names}}")
check("no agent container remains", left.stdout.strip() == "",
      repr(left.stdout.strip()))

print()
print("=" * 70)
if failures:
    print("RESULT: %d CHECK(S) FAILED: %s" % (len(failures), failures))
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
sys.exit(0)
