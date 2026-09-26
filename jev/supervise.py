#!/usr/bin/env python3
"""
External run supervisor for the OmegaJev experiment.

Root SECURITY.md section 19: the operator's stopping path must lie outside
the agent's failure path. "Do not put the brake on the same failure path as
the engine."

The provider's own `jevMaxTurns` counter runs *inside* the agent process. It
is a budget, not a brake: if the provider blocks on a socket, wedges, or the
loop stalls, that counter never advances and never fires. This supervisor is
a separate host process that watches from outside and stops the container
without the agent's cooperation or awareness.

Three independent limits:

  --max-turns      stop after N observed decisions
  --stall-seconds  stop if no new decision appears within N seconds  <- the
                   one the in-process counter structurally cannot provide
  --max-seconds    absolute wall-clock deadline

It handles no credential and reads nothing but the container's log stream.

NOTE ON GRANULARITY: this is a mechanism for guaranteeing *termination*, not
an exact per-action gate. The agent may complete another turn between the
supervisor observing a limit and the container stopping. Precise per-action
budgets belong in the authority kernel (../core), which decides before each
mutation; this only guarantees the run ends.

Usage:
    python supervise.py --max-turns 4 -- jevActionSet=butterfly
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time

IMAGE = "omega-jev:experiment"
NETWORK = "jev-internal"
NAME = "omega-jev-run"
TRACE_MARKER = "decision trace, turn"
OWN_LIMIT_MARKER = "TURN LIMIT REACHED"

EXIT_COMPLETED = 0      # container finished on its own
EXIT_MAX_TURNS = 10
EXIT_STALLED = 11
EXIT_DEADLINE = 12
EXIT_START_FAILED = 2


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          errors="replace")


def running(name: str) -> bool:
    out = docker("inspect", "-f", "{{.State.Running}}", name)
    return out.returncode == 0 and out.stdout.strip() == "true"


def stop(name: str, reason: str) -> None:
    print("\n[supervisor] STOPPING: %s" % reason, flush=True)
    docker("stop", "-t", "5", name)
    if running(name):
        print("[supervisor] still running after stop; forcing", flush=True)
        docker("rm", "-f", name)
    print("[supervisor] container stopped without agent cooperation", flush=True)


class LogWatcher(threading.Thread):
    """Streams `docker logs -f` and counts decisions as they appear.

    Streaming rather than re-reading: the agent's log reaches hundreds of
    kilobytes within seconds, and repeatedly fetching all of it was slow
    enough that whole runs finished before the supervisor noticed a single
    decision. Reading incrementally makes detection effectively immediate.
    """

    daemon = True

    def __init__(self, name: str):
        super().__init__()
        self.name_ = name
        self.turns = 0
        self.last_progress = time.monotonic()
        self.lines: list[str] = []
        self.own_limit_fired = False
        self._proc = None

    def run(self) -> None:
        try:
            self._proc = subprocess.Popen(
                ["docker", "logs", "-f", self.name_],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", bufsize=1)
        except Exception as exc:  # noqa: BLE001
            print("[supervisor] log stream failed: %s" % exc, flush=True)
            return
        for line in self._proc.stdout:
            self.lines.append(line)
            if TRACE_MARKER in line:
                self.turns += 1
                self.last_progress = time.monotonic()
            if OWN_LIMIT_MARKER in line:
                self.own_limit_fired = True

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-turns", type=int, default=4)
    ap.add_argument("--stall-seconds", type=int, default=120)
    ap.add_argument("--max-seconds", type=int, default=600)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--network", default=NETWORK)
    ap.add_argument("--name", default=NAME)
    ap.add_argument("--poll", type=float, default=0.2)
    ap.add_argument("--min-runtime", type=float, default=5.0,
                    help="a run ending sooner than this with zero decisions "
                         "is reported as a failed start, not a completed run")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("args", nargs="*", help="arguments passed to the container")
    opts = ap.parse_args()

    docker("rm", "-f", opts.name)

    # argparse leaves a literal "--" in a nargs="*" positional.
    container_args = [a for a in opts.args if a != "--"]

    # Detached: the supervisor never shares a process, a pipe or a failure
    # mode with the agent.
    run_cmd = ["run", "-d", "--name", opts.name,
               "--network", opts.network, opts.image, *container_args]
    started = docker(*run_cmd)
    if started.returncode != 0:
        print("[supervisor] failed to start: " + started.stderr.strip())
        return EXIT_START_FAILED
    print("[supervisor] docker " + " ".join(run_cmd))

    for _ in range(25):
        if running(opts.name):
            break
        time.sleep(0.2)
    else:
        print("[supervisor] container never reached running state")
        docker("rm", "-f", opts.name)
        return EXIT_START_FAILED

    watcher = LogWatcher(opts.name)
    watcher.start()

    print("[supervisor] started %s on %s" % (opts.name, opts.network))
    print("[supervisor] limits: max_turns=%d stall=%ds deadline=%ds"
          % (opts.max_turns, opts.stall_seconds, opts.max_seconds))

    begin = time.monotonic()
    watcher.last_progress = begin
    seen = 0
    verdict = EXIT_COMPLETED
    next_liveness = 0.0

    try:
        while True:
            time.sleep(opts.poll)
            now = time.monotonic()

            if watcher.turns > seen:
                seen = watcher.turns
                if not opts.quiet:
                    print("[supervisor] observed decision %d/%d (t+%.1fs)"
                          % (seen, opts.max_turns, now - begin), flush=True)

            if seen >= opts.max_turns:
                stop(opts.name, "turn limit reached (%d)" % opts.max_turns)
                verdict = EXIT_MAX_TURNS
                break
            if now - watcher.last_progress > opts.stall_seconds:
                stop(opts.name, "stalled: no decision for %ds "
                                "(the in-process counter cannot catch this)"
                                % opts.stall_seconds)
                verdict = EXIT_STALLED
                break
            if now - begin > opts.max_seconds:
                stop(opts.name, "wall-clock deadline %ds" % opts.max_seconds)
                verdict = EXIT_DEADLINE
                break

            # Liveness is the only remaining docker call in the hot loop, and
            # it is cheap; still, do not run it every tick.
            if now >= next_liveness:
                next_liveness = now + 1.0
                if not running(opts.name):
                    if seen == 0 and (now - begin) < opts.min_runtime:
                        print("[supervisor] container died after %.1fs with no "
                              "decision -- failed start, not a completed run"
                              % (now - begin))
                        verdict = EXIT_START_FAILED
                        break
                    print("[supervisor] container exited on its own after %d "
                          "decisions" % seen)
                    verdict = EXIT_COMPLETED
                    break
    except KeyboardInterrupt:
        stop(opts.name, "operator interrupt")
        verdict = EXIT_DEADLINE

    time.sleep(0.4)          # let the stream drain
    watcher.close()
    captured = list(watcher.lines)
    docker("rm", "-f", opts.name)

    print("\n" + "=" * 62)
    print("DECISION TRACE")
    print("=" * 62)
    for line in captured:
        for needle in (TRACE_MARKER, "ACTION_ID", "confidence",
                       "probabilities", "compiled", "BUTTERFLY ",
                       "FAILED CLOSED", "view          :", OWN_LIMIT_MARKER,
                       "staged", "SB-RECEIPT", "NOT STAGED", "probes  "):
            if needle in line:
                print("  " + line.split("| jev |")[-1].strip()[:150])
                break
    print("=" * 62)
    print("decisions observed      : %d" % seen)
    print("in-process limit fired  : %s" % watcher.own_limit_fired)
    print("verdict                 : %s" % {
        EXIT_COMPLETED: "container completed on its own",
        EXIT_MAX_TURNS: "STOPPED by supervisor (turn limit)",
        EXIT_STALLED: "STOPPED by supervisor (stall)",
        EXIT_DEADLINE: "STOPPED by supervisor (deadline)",
        EXIT_START_FAILED: "FAILED TO START",
    }[verdict])
    return verdict


if __name__ == "__main__":
    sys.exit(main())
