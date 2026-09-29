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
- PR #41: bounded multimodal InteractionEpisode records for linguistic turns.
- This tranche: non-sticker bare-page path observation and generic input ordering.

An episode records utterance, optional validated point/box, descriptive
voice/text mode, scene revision, and up to four recent host-observed input
summaries. The host ledger sequences sticker drags and bare-page paths together
at recording time. A conversation receives the newest four entries since the
previous linguistic turn, in host arrival order. Monotonic sequence numbers
keep eviction deterministic. Input remains recorded and the cursor advances if
inference fails. The
next turn receives only its own episode, so retry context is a future design
question. The record holds at most 24 episodes and does not persist.

The existing background drag still creates a deictic box. In powered localhost
mode it also sends a `PagePathTrace`: up to 32 retained observed page-space
samples from at most 64 client samples, with no world anchors, interpretation,
kernel receipt, or revision change. The browser samples the existing gesture,
reduces it deterministically, and sends it through a separate auxiliary
endpoint. Malformed telemetry is discarded; the box remains. OmegaLLM receives
only a `page-path` reference and duration. Host arrival order is the evidence
order; network delay does not establish precise physical timing across separate
requests. Page paths are not learnable or executable yet.

## OpenShell status

**BLOCKED_UPSTREAM / LIVE GRAPH UNVERIFIED.** See
[OpenShell runtime status](../openshell/README.md) and
[runtime architecture](TOOLS-AND-MODIFICATIONS.md). Do not bypass containment.

## Validation commands

From the repository root unless a `cd` is shown:

```bash
python -m py_compile web/page_path.py web/interaction.py web/sticker_drag.py web/bridge.py web/tests/test_page_path.py web/tests/test_interaction.py jev/omega_jev/providers/jev.py llm/omega_llm/providers/stickerbook_llm.py runtime/omega/stickerbookrpc.py
cd core && python -m unittest discover -s tests
cd ../jev && python -m unittest discover -s tests
cd ../web && python -m unittest discover -s tests -p test_interaction.py
python -m unittest discover -s tests -p test_page_path.py
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

1. Decide how OmegaLLM should bind “like this,” “around there,” and “do that” to distinct point/box/path evidence without treating geometry alone as meaning.
2. Turn embodied trajectories into movement memory without false symbolic quantisation.
3. Let OmegaJev act relative to that memory while selecting only from a finite CURRENT legal surface.
4. Determine trajectory scale, shape, and timing invariance.
5. Design persistence and child/session boundaries.
6. Prove the live OpenShell graph when upstream permits it.

## Repository workflow

Do not add `Co-Authored-By` trailers for coding agents or “Generated with …”
branding to PR descriptions. Do not rewrite repository history merely to
change tooling attribution.
