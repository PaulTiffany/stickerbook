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
- PR #42: non-sticker bare-page path observation and generic input ordering.
- PR #43: host-issued physical input-event provenance for box/path co-origin.
- PR #44: bounded semantic demonstration binding to a current page-path event.
- PR #45: real OmegaLLM provider contract for the existing discrete
  remember-pattern/perform-pattern intents, plus correct kernel-page checking
  for demonstration subjects (the UI page ID is a different namespace).
- PR #46: one host-owned pending semantic reference for bounded
  linguistic continuation, separate from current input evidence.
- This tranche: non-executing page-path trajectory references with explicit
  page/subject frame and immutable host-resolved geometry.

The provider now accepts subject/intent plus a bounded label or pattern id for
the existing pattern intents. Remember requires a label; perform requires a
label or id. Label validation and normalization match host memory; pattern ids
remain bounded references that the host resolves. The provider never supplies
PatternSteps, action keys, trajectory geometry, or a historical slice. Tests
exercise real provider parsing/staging with a fake inference transport and
then host remembering and Jev selection. This proves the powered-language
contract mechanically, not live model interpretation or OpenShell execution.

An episode records utterance, optional validated point/box, descriptive
voice/text mode, scene revision, and up to four recent host-observed input
summaries. The host ledger sequences sticker drags and bare-page paths together
at recording time. A conversation receives the newest four entries since the
previous linguistic turn, in host arrival order. Monotonic sequence numbers
keep eviction deterministic. Input remains recorded and the cursor advances if
inference fails. The
next turn receives only its own input episode; semantic carry below preserves
an admitted referent without replaying earlier inputs. The record holds at
most 24 episodes and does not persist.

The existing background drag still creates a deictic box. In powered localhost
mode it also sends a `PagePathTrace`: up to 32 retained observed page-space
samples from at most 64 client samples, with no world anchors, interpretation,
kernel receipt, or revision change. The browser samples the existing gesture,
reduces it deterministically, and sends it through a separate auxiliary
endpoint. Malformed telemetry is discarded; the box remains. OmegaLLM receives
only a `page-path` reference and duration. Host arrival order is the evidence
order; network delay does not establish precise physical timing across separate
requests. Page paths are not learnable or executable yet.

For one bare-page drag, the auxiliary request carries both its existing box
and bounded path samples. The host checks the box against observed endpoints,
then returns `sourceEvent` as `input-event-N`, issued from its observation
sequence. The browser attaches it only to the still-pending box. The host
projects that token on the box only when it identifies the latest eligible
path in the current bounded window and matches the box stored at capture. The
path signal carries the same token. Stale, fabricated, mismatched, or failed
captures leave the box usable but unlinked. This is checked correlation of
client observations, not independent attestation of physical hardware events.
It does not solve cross-request timing or assign semantic meaning.

OmegaLLM may now return exactly `{subject, intent: "bind-demonstration",
demonstration: "input-event-N"}`. Its provider checks the identifier against
the current `scene.interaction` page-path signals or exposed pending reference;
the host checks the same admissibility window, the path's fixed principal/page, and the
subject's current page. The model selects which eligible event it means; the
host does not choose by recency, box matching, or geometry. A valid result is
an inspectable, non-mutating `{result: "bound", subject, demonstration,
pathRef}`. It creates no memory, Jev call, kernel receipt, or world revision.
The response remains under the legacy `jev` key, also used for host-side
pattern memory; renaming that public envelope is deferred for compatibility.
The semantic goal carries no path samples or movement instructions.

A successful host-validated binding admits/replaces one immutable
`PendingSemanticReference`: subject, demonstration, path ref, source episode,
fixed principal, and page. The next linguistic call receives its bounded
projection as `scene.pendingReference`, separate from `scene.interaction`.
Binding can select current page-path evidence or exactly that exposed
pending subject/event pair. No prior episode lookup is introduced.
A valid linguistic response consumes the carry, including when its goal is
refused; a successful binding replaces it. Explicit rebinding of the same
carry renews it without changing its original provenance. Runtime errors,
provider failure, and invalid response envelopes preserve it while the new
input episode and observation cursor still record the turn normally.
Linguistic calls are serialized so concurrent requests cannot share a
one-turn consumption window. Direct gestures do not consume the carry.
No transcript or samples are retained in this slot. It does not pin path
geometry against log eviction or grant future execution rights. Its lifetime
is measured in successful turns, not elapsed time; repeated failures preserve
the one slot. Open-ended transcript memory remains absent.

`reference-trajectory` has exactly subject, intent, demonstration, and required
frame (`page` or `subject`, without a default). Provider and host validate the
same current-or-pending evidence window and visible subject; the host resolves
only the admitted path ref. Evicted source geometry returns
`trajectory-evidence-unavailable`, with no substitute or episode search.
Successful resolution consumes carry without renewal. `bind-demonstration`
remains purely referential and is still the only carry admission operation.

For retained source points p_i, page frame preserves q_i = p_i; subject frame
uses q_i = s + (p_i - p_0), where s is the subject position at resolution. Page
axes/units, shape, orientation, scale, sample order, t, and observed duration
are preserved. Out-of-page derived coordinates remain unchanged. Timing is
evidence, not an execution schedule. No segment to the page-path start is added.

The frozen `ResolvedTrajectoryReference` holds provenance, source/subject
starts, immutable source and resolved sample tuples, observed duration, source
recording revision, and resolution revision. A host world lock shared by every
bridge-reachable kernel mutation makes the subject/visibility/revision snapshot
coherent. It brackets the world operation only: both OmegaLLM and OmegaJev
inference, and the runtime availability probes behind `state()`, run outside
it, so child movement during inference is reflected at resolution and model
latency never blocks a gesture or a state poll. The kernel's own
`based_on_revision` check, not the lock, still adjudicates staleness.
The bridge retains only its last successful reference,
without lookup endpoints or persistence. Response summaries omit sample arrays,
and no resolved geometry is added to later OmegaLLM scenes. The legacy `jev`
response key remains for compatibility, not as evidence of a Jev call.

Layering: PagePathTrace = observed geometry; sourceEvent = physical co-origin;
bind-demonstration = evidence selection; PendingSemanticReference = discourse
carry; reference-trajectory = semantic frame selection; ResolvedTrajectoryReference
= host-derived non-authoritative geometry. Motor interpretation and trajectory
control by OmegaJev are NOT YET implemented. Kernel authority is unchanged.

## OpenShell status

**BLOCKED_UPSTREAM / LIVE GRAPH UNVERIFIED.** See
[OpenShell runtime status](../openshell/README.md) and
[runtime architecture](TOOLS-AND-MODIFICATIONS.md). Do not bypass containment.

## Validation commands

From the repository root unless a `cd` is shown:

```bash
python -m py_compile web/page_path.py web/interaction.py web/sticker_drag.py web/bridge.py web/jev_controller.py web/tests/test_demonstration_binding.py web/tests/test_input_event.py web/tests/test_page_path.py web/tests/test_interaction.py jev/omega_jev/providers/jev.py llm/omega_llm/providers/stickerbook_llm.py runtime/omega/stickerbookrpc.py
cd core && python -m unittest discover -s tests
cd ../jev && python -m unittest discover -s tests
cd ../web && python -m unittest discover -s tests -p test_interaction.py
python -m unittest discover -s tests -p test_demonstration_binding.py
python -m unittest discover -s tests -p test_pattern_provider.py
python -m unittest discover -s tests -p test_semantic_carry.py
python -m unittest discover -s tests -p test_trajectory_reference.py
python -m py_compile trajectory_reference.py tests/test_trajectory_reference.py
python -m py_compile semantic_reference.py tests/test_semantic_carry.py
python -m py_compile tests/test_pattern_provider.py
python -m unittest discover -s tests -p test_page_path.py
python -m unittest discover -s tests -p test_input_event.py
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

The next design question is which explicit movement-use intent permits a
resolved spatial reference to become a bounded motor objective, including how
to handle a page-frame start away from the sticker. Reference resolution alone
does not request execution or remembering. Candidate generation, timing use,
page-edge behavior, and trajectory memory remain unimplemented research work.

1. Decide whether a bound page path is a demonstration, route, region, or other meaning in context before defining motor behavior.
2. Extend binding to “around there” and “do that” across other evidence kinds without geometry-only heuristics.
3. Turn embodied trajectories into movement memory without false symbolic quantisation.
4. Let OmegaJev act relative to that memory while selecting only from a finite CURRENT legal surface.
5. Determine trajectory scale, shape, and timing invariance.
6. Design persistence and child/session boundaries.
7. Prove the live OpenShell graph when upstream permits it.

## Repository workflow

Do not add `Co-Authored-By` trailers for coding agents or “Generated with …”
branding to PR descriptions. Do not rewrite repository history merely to
change tooling attribution.
