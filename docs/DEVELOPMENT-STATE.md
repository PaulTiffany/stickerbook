# Development state

## Architecture

OmegaLLM receives bounded language and scene context, replies, and may emit one
bounded semantic goal. OmegaJev receives that goal, fresh state, and the CURRENT
finite host-owned legal action table; it chooses among offered actions. The
kernel alone adjudicates world mutation. Browser/device speech-to-text supplies
a transcript to `/api/agent/converse`; microphone audio is not stored. A direct
double-click gesture reaches OmegaJev without OmegaLLM. Separate OpenShell
sandboxes contain the two powered loops. The public GitHub Pages build is a
mechanical static demo; the powered authority-kernel runtime runs on localhost.

## Invariants

- Omega talks. Jev chooses. The kernel decides.
- Capability is not authority.
- Learning changes memory, not authority.
- The host remembers what happened; OmegaLLM does not rewrite history.
- Input history is not world history.
- The client supplies signals; the host determines their recorded ordering and association.

## Landed development tranches

- PR #38: typed movement-pattern memory.
- PR #39: Remember that / Do that again.
- PR #40: StickerDragTrace capture.
- This tranche: bounded multimodal InteractionEpisode records for linguistic turns.

An episode records utterance, optional validated point/box, descriptive
voice/text mode, scene revision, and up to four recent host-observed drag
summaries. It does not interpret geometry. Drag associations are the newest
traces since the previous linguistic turn, in host observation order. When an
old cursor is evicted, all retained traces are newer and the newest four are
used. Input remains recorded and the cursor advances if inference fails. The
next turn receives only its own episode, so retry context is a future design
question. The record holds at most 24 episodes and does not persist.

## OpenShell status

**BLOCKED_UPSTREAM / LIVE GRAPH UNVERIFIED.** See
[OpenShell runtime status](../openshell/README.md) and
[runtime architecture](TOOLS-AND-MODIFICATIONS.md). Do not bypass containment.

## Validation commands

From the repository root unless a `cd` is shown:

```bash
python -m py_compile web/interaction.py web/sticker_drag.py web/bridge.py web/tests/test_interaction.py jev/omega_jev/providers/jev.py llm/omega_llm/providers/stickerbook_llm.py runtime/omega/stickerbookrpc.py
cd core && python -m unittest discover -s tests
cd ../jev && python -m unittest discover -s tests
cd ../web && python -m unittest discover -s tests -p test_interaction.py
python -m unittest discover -s tests
cd ..
python openshell/verify.py
node --check web/static/app.js
bash -n openshell/install-pinned.sh openshell/run-omega-jev.sh openshell/run-omega-jev-service.sh openshell/run-omega-llm-service.sh jev/openshell-entrypoint.sh runtime/omega/openshell-entrypoint.sh runtime/lib.sh runtime/start.sh runtime/stop.sh runtime/status.sh
```

The Windows-only intermittent
`test_bridge.TrayPlacement.test_unknown_write_routes_are_404` may raise
`ConnectionAbortedError / WinError 10053`. It predates this tranche, passes
alone, and has not appeared in Linux CI.

## Next research and build questions

1. Capture a non-sticker child path demonstration as another bounded input signal.
2. Bind multimodal phrases such as “like this,” “around there,” and “do that.”
3. Turn embodied trajectories into movement memory without false symbolic quantisation.
4. Let OmegaJev act relative to that memory while selecting only from a finite CURRENT legal surface.
5. Determine trajectory scale, shape, and timing invariance.
6. Design persistence and child/session boundaries.
7. Prove the live OpenShell graph when upstream permits it.

## Repository workflow

Do not add `Co-Authored-By` trailers for coding agents or “Generated with …”
branding to PR descriptions. Do not rewrite repository history merely to
change tooling attribution.
