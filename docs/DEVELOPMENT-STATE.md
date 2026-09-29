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
- PR #47: non-executing page-path trajectory references with explicit
  page/subject frame and immutable host-resolved geometry, plus a world-lock
  scope correction so no model think-time is serialized.
- PR #48: movement staleness correctness. Powered pattern execution proposes
  against the revision its own action table was built from, plus a narrow
  `move_only` choice surface for the trajectory follower.
- PR #49: the deterministic mechanical subject-frame trajectory follower.
  Monotonic progress, one-step lookahead objective, truthful partial/stopped
  audit, and no model inference anywhere on the path.
- This tranche: the powered follower. `perform-trajectory` asks for movement,
  and OmegaJev selects each motor step from the same shared control loop.

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

**BLOCKED_UPSTREAM / LIVE GRAPH UNVERIFIED.** The newer-WSL-kernel
hypothesis from upstream issue #3842 was tested on the live host on
2026-09-29 and did not hold: moving to WSL 3.0.1.0 /
`6.18.40.1-microsoft-standard-WSL2` and changing nothing else reproduced the
same `seccomp notification probe / notification launcher disappeared`
failure. A probe of the exact listener path then located the failing step:
`PR_SET_NO_NEW_PRIVS` and `SECCOMP_GET_NOTIF_SIZES` succeed, a plain seccomp
filter installs cleanly, but `SECCOMP_SET_MODE_FILTER` with `NEW_LISTENER`
returns `EBUSY` both on the WSL host and in an ordinary Docker container, so
no listener is ever created to send to the broker. `EBUSY` there means a
notifier already exists in the task's inherited filter chain, and indeed
every process in the distro — PID 1 included — inherits a filter installed
by WSL's own init layer. No process under WSL2 on this host can install a
seccomp user-notification listener, at any kernel version. The separate
gateway-connectivity issue #3880 was never reached. See
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
python -m unittest discover -s tests -p test_trajectory_follower.py
python -m unittest discover -s tests -p test_powered_trajectory.py
python -m unittest discover -s tests -p test_remember_and_recall.py
python -m unittest discover -s tests -p test_pattern_memory.py
python -m py_compile trajectory_reference.py tests/test_trajectory_reference.py
python -m py_compile trajectory_execution.py tests/test_trajectory_follower.py
python -m py_compile tests/test_powered_trajectory.py
python -m py_compile jev_controller.py tests/test_remember_and_recall.py
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

## The action-table revision rule

> A finite action table containing absolute move destinations is valid only
> against the world revision from which that table was constructed. Model
> think-time never refreshes the revision attached to an old choice.

`_move_candidates` offers eight local steps as absolute page destinations
derived from the subject's position when the table is built, and the world
lock is deliberately released across chooser inference. A proposal therefore
names its own table's revision, and the kernel answers `stale-revision` when
the subject moved meanwhile. Re-reading the revision at submission time would
apply an old coordinate as current and silently undo the child's own gesture.
The ordinary bounded goal loop, powered pattern execution and mechanical
replay all follow this rule. See
[agent interface](AGENT-INTERFACE.md#a-finite-action-table-belongs-to-one-world-revision).

## Trajectory layering

```text
reference-trajectory            semantic coordinate frame
perform-trajectory              a request for movement now
ResolvedTrajectoryReference     frozen non-authoritative geometry
mechanical trajectory follower  deterministic reference implementation
powered trajectory follower     OmegaJev selects each motor step
kernel authority                unchanged
```

`perform-trajectory` is the child-facing intent that asks for movement now:

```json
{"subject":"bird-1","intent":"perform-trajectory","demonstration":"input-event-7","frame":"subject"}
```

Exactly four fields, and `frame` must be `subject` with no default.
`reference-trajectory` still takes both frames; `bind-demonstration` stays
purely referential. All three admit evidence through one shared path, so
there is no second way to name a demonstration. Performing consumes pending
carry under the ordinary one-turn rule and never renews it.

The attempt holds the frozen reference resolved at admission.
`bridge.last_trajectory_reference` is an inspection slot, not execution
state, and is never read back mid-attempt.

Powered following swaps only the selector. OmegaJev receives a bounded
`follow-trajectory` decision context -- position, progress index, objective,
local error, at most a two-point lookahead, and the current action table
including `NOOP` -- and returns one offered key. No sample array reaches
either model. `MAX_AGENT_TRAJECTORY_STEPS = 12` bounds model spend separately
from the `MAX_TRAJECTORY_STEPS = 48` motor cap, and the two exhaustion
reasons are distinct. Jev declining is `jev-noop`; an absent runtime is
`jev-unavailable`; a failing one is `jev-selection-failed`. None of those is
completion.

`JevController.follow_trajectory()` follows one already-resolved
**subject-frame** reference. Page-frame references remain valid non-executing
data: a page-frame path can begin far from the subject, and whether that means
teleport, approach, refuse or clarify is a semantic question, not a geometric
one, so it is deliberately undecided.

Nothing is precompiled. Each step re-derives everything from current state, so
possessing a trajectory grants no more than the right to propose one ordinary
move at a time. `perform-trajectory` does not exist yet: this path is a host
reference implementation, not a child-facing contract.

**Monotonic progress and the one-step lookahead.** Progress is an index into
the retained points that only ever moves forward:

```text
while progress < last and distance(subject_now, points[progress]) < MOVE_STEP:
    progress += 1
objective = points[progress]
```

It is never a nearest-point search and never projects across the path. That
ordering is the only thing protecting loops. Retained waypoint spacing is
typically finer than one `MOVE_STEP`, so a next-waypoint objective overshoots
reference arc length by about 49% against roughly 7.5% for this lookahead. And
in an out-and-return path the first and last retained points can be the same
coordinate, so any nearest-point rule faces a tie that, resolved toward the
later index, would declare the whole excursion complete before a single step.

**Completion** is host bookkeeping only: sequential arrival at the final point,
within the same reach. Never proximity to some later point, never proximity to
the origin, never a selector declining, never budget exhaustion. An
already-satisfied reference completes with zero proposals.

**Step budget**, derived once from the frozen geometry, is a motor-step count
and never a clock:

```text
planned = min(48, ceil(1.25 * arc_length / MOVE_STEP))
```

Exhaustion reports `step-budget-exhausted` as `partial` when steps landed, and
never `completed`.

**Duplicate destinations.** At a page edge, clamping makes some diagonal keys
share a destination with an axis key, so `STEP-NE` and `STEP-E` can both mean
the same place. The table is deliberately **not** deduplicated, because that is
the honest legal surface a powered chooser will be shown. Selection orders by
`(distance to objective, action key)`, so the tie-break decides the recorded
key, not a different physical path.

**Page edges.** The frozen reference keeps its off-page coordinates. When legal
moves exist but none strictly reduces distance to the objective, the host stops
with `trajectory-objective-unreachable`, `partial` if steps already landed.
Host-determined, and never represented as a selector `NOOP`.

**Timing** is ignored by execution. Observed `t` and `observed_duration_ms`
stay on the reference as evidence; no wall-clock scheduling exists, and the
speed at which the path was drawn is not simulated.

**The action-table revision rule** applies to every step: the coherent read
(subject, progress, objective, `move_only` table, revision) happens under a
brief world lock, the lock is released across the selector seam, and the
proposal names the snapshot revision. See
[agent interface](AGENT-INTERFACE.md#a-finite-action-table-belongs-to-one-world-revision).

**Human supersession, and what is not supersession.** Direct human
manipulation of the subject supersedes the attempt: the child is the
higher-authority actor, their move stands, and nothing re-aims or retries.
But a `stale-revision` refusal alone is not evidence of that. The host labels
`superseded-by-human` only when governed history shows an accepted
`human-gesture` record for **this same subject**, newer than the motor
snapshot. The same subject moved by another controller path stops neutrally as
`world-changed`, because claiming the child did it would be fabricated
provenance. A change to a *different* sticker does not disturb the attempt at
all, since the staleness check in the kernel is per-sticker.

Both followers remain available, and produce the same record shape with only
`mode` and attribution differing, so a mechanical run and a powered run of the
same reference are directly comparable.

## Next research and build questions

The next step is live application testing: comparing a deterministic
mechanical trajectory against an OmegaJev-powered one in the running app, and
using measured latency to set the provisional agent decision cap and decide
whether a wall-clock bound is needed. Beyond that, timing use, continuous
trajectory memory and page-frame execution semantics remain unimplemented
research work.

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
