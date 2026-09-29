# SECURITY — StickerBook

**Constitutional security model. This document is binding on all StickerBook
work.**

> **Recursive capability must not silently acquire recursive authority.**
>
> **Capability ≠ authority.**

Greater intelligence, memory, confidence, specialization, coordination,
recursion, tool skill or model quality **must not** imply greater authority.
Capability may compose. Authority must remain explicit, externally grounded,
bounded, revocable and causally traceable.

StickerBook is intended to support children. Therefore the boundary must be
**architectural**, not dependent on user vigilance.

---

## 0. Scope, deployment profiles, and how to read this document

This is the **root** document: it defines what must be true of StickerBook.

`core/` holds the **authority kernel** — the headless implementation of this
model, with its mechanical tests. `core/stickerbook_core/kernel.py` is the
single gate every mutation passes through.

`jev/SECURITY.md` is the **component** document for the OmegaJev experiment:
it records, with mechanical evidence, how some of these requirements are
currently made true. Where the two meet, this document states the requirement
and points at the component document for the proof. The component document's
specific verified claims are authoritative for OmegaJev and are not restated
here in weaker form.

The repository now contains the authority kernel (`core/`), a real
browser/bridge/sticker/page implementation (`web/`), and the separate
OmegaJev experiment (`jev/`). The browser and bridge are mechanically tested
against the kernel. The OmegaJev experiment has also been coupled to the kernel
in its headless Stage 4 harness.

The new dual-Omega browser substrate adds a bounded OmegaLLM -> OmegaJev goal
and choice seam, but the **actual OmegaLLM and OmegaJev Omega processes are not
yet wired into the browser runtime**. Tests use deterministic stand-ins for that
integration. OpenShell containment is an intended next deployment layer, not a
current dependency. Read every status marker before treating an interface-level
test as proof of a deployed model/runtime boundary.

### Status vocabulary

Every requirement below carries a status. These are deliberately distinct, and
must not be conflated when reporting:

| Marker | Meaning |
|---|---|
| **REQUIRED** | Architectural requirement. Binding. May not yet exist anywhere. |
| **IMPLEMENTED** | A mechanism exists. Named, but not necessarily test-covered. |
| **VERIFIED** | A mechanical test proves it. The test is named. |
| **GAP** | Required, applies to something that exists, not yet enforced. |
| **N/A YET** | No surface exists to which it can apply. Not a gap; an absence. |

A requirement marked **N/A YET** becomes a **GAP** the moment the relevant
surface is built. It does not become satisfied by default.

Evidence is further tagged by *where* it was proved, because the two
implementations are not yet connected:

* **VERIFIED (core)** — proved in `core/tests/test_authority.py` against the
  authority kernel. The same kernel is now used by the localhost bridge and by
  the OmegaJev Stage 4 harness, but a core-only unit test still proves only the
  kernel property, not the correctness of every integration around it.
* **VERIFIED (omegajev)** — proved in the running OmegaJev container.

Do not report a core-verified invariant as a property of the deployed system.

### Deployment authority profiles

**REQUIRED.** StickerBook does not have one ambient security posture. It has
named, mechanically enforced **deployment authority profiles**, and every
statement about StickerBook's security must name the profile it applies to.

```
pages-demo:          agent authority = ∅
local-single-agent:  Jev authority  = bounded sticker actor
local-multi-agent:   Omega + Jev with an explicit authority graph
```

A profile is an absolute ceiling applied by intersection **before** any other
check (`AuthorityProfile.agent_ceiling`, `Kernel.effective_tools`). It caps
agent principals only; human and operator authority is unaffected.

**The public GitHub Pages artifact is not a weakened live system. It is a
different security profile with no live-agent path at all.** That is a
stronger claim than "the buttons happen to use mock responses", and it is the
claim we must be able to defend:

* `pages-demo` sets `agent_ceiling = ∅`. There is no action any agent
  principal can take — not a disabled feature, an empty intersection.
* **VERIFIED (core):** in `pages-demo`, every one of the ten actions is
  rejected for an agent principal; the generated action table is empty; and a
  principal registered with *every* tool still has an empty effective
  authority. Humans are unaffected.

The kernel-level ceiling is the last line, not the first. The public build
must additionally contain **no** agent bridge module, WebSocket endpoint,
provider URL, API-key name or live-agent import, and should carry a
restrictive CSP. The operative invariant:

> A curious child editing browser state cannot turn the Pages demo into the
> powered version.

These are **separate build targets**, never one UI behind a boolean such as
`LIVE_AGENT=false`. A boolean is a thing that can be flipped.

**Status: the build-target separation and its CI enforcement are a GAP** —
no browser build exists yet. The profile mechanism they will rely on is
VERIFIED (core). When the Pages build is created, CI must fail the artifact
if it contains any of the forbidden imports or strings.

Correspondingly, **the browser is never the trust anchor** — in either
profile. A malicious or modified browser may propose anything; the authority
kernel still refuses. **VERIFIED (core):** raw hostile proposals are
validated identically to generated ones.

---

## 1. Causal separation

**REQUIRED.** These stages stay distinct and must not be collapsed:

```
observe → reason/imagine → propose → authorize → validate → actuate → receipt
```

* A model output describing an action is not an action.
* A request for authority is not authority.
* A valid command is not necessarily an authorized command.
* An authorized command is not enacted until the independent controller
  accepts and applies it.

The load-bearing property is that **no agent-generated bytes become
executable text**. The agent names an intent; the host decides what, if
anything, that means.

**OmegaJev status: IMPLEMENTED and VERIFIED for propose → validate →
actuate.** Jev emits a typed choice key; a frozen host-owned table determines
the literal command. See `jev/SECURITY.md` §1 and §3.

**GAP:** OmegaJev has no distinct *authorize* stage (there are no principals
to authorize against — see §4) and emits log traces rather than **receipts**
(§17).

**Core status:** the kernel implements all seven stages. `Kernel.view` observes,
`available_actions` bounds what may be proposed, `propose`/`propose_key`
authorize and validate, handlers actuate, and every decision returns a
`Receipt`. VERIFIED (core).

---

## 2. Authority is external to the agent

**REQUIRED.** Agents must not own the mechanism that constrains them. An agent
must not be able to modify its own permissions, change ownership rules,
redefine principals, change security policy, replace the authority gate, issue
itself credentials, modify its actuator vocabulary, grant itself tools, or
obtain through a subordinate agent any authority it does not itself hold.

Authority expansion requires a separately authorized **external** action.

**The strongest boundary is non-representability.** Do not expose a general
dangerous capability and instruct the model not to use it. Prefer
`remove-own-sticker(id)` over `delete-object(id)` plus a behavioural rule.
Prompt-level obedience is not a security mechanism.

**OmegaJev status: VERIFIED.** The agent cannot modify its source or the
policy file (POSIX uid 65534 + Landlock, both verified independently), holds
no credential, and cannot expand its own command vocabulary — executing every
permitted action leaves the allowlist unchanged, and `metta`, the only route
to `add-skill`/`add_llm_command`, is unreachable. See `jev/SECURITY.md` §2,
§3, §6 and `jev/tests/verify_in_container.py`.

---

## 3. Principals

**REQUIRED.** StickerBook has explicit, security-relevant principals, not one
generic `agent`:

```
trusted operator · human player · agent:omega-director ·
agent:jev-visual-1 · agent:<specialist> · system/controller
```

Agent type does not imply authority. A more capable agent may hold **less**
authority than a simpler one. A non-conversational Jev actor may hold visual
actuation and no chat capability; a conversational Omega may plan, inspect and
delegate while holding no direct actuation authority.

**Capabilities must not be unioned merely because agents cooperate.**

**Core status: VERIFIED (core).** `Principal` carries id, kind, tools,
delegable set, parent, depth and budgets as explicit data. Authority is
recomputed per action by `effective_tools`, never inferred and never cached.
Agent type does not imply authority: an agent registered with every tool has
empty authority under `pages-demo`.

**OmegaJev status: GAP.** OmegaJev has exactly one implicit, unnamed agent
principal. No identity is carried, checked or recorded. Nothing currently
depends on principal identity because there is only one actor and one
non-human-owned object — but the mechanism does not exist and must be built
before a second principal is introduced.

---

## 4. Ownership and provenance

**REQUIRED.** Every mutable object carries explicit ownership:

```json
{ "id": "moth-17", "owner": "agent:jev-visual-1",
  "createdBy": "agent:jev-visual-1", "asset": "moth-v2" }
```

Ownership **must not** be inferred from appearance, colour, filename, prompt
history or model output.

Baseline intent: humans may create, move, transform, animate and remove their
own stickers, and may remove agent-created content. Agents may manipulate only
what is explicitly granted. Agents may not modify human-owned creative state
by default. Agent-created content remains subordinate to human control.

**Authority checks happen before world mutation, never in the renderer.**

The trusted operator — not the child — controls installation-level capability:
agent enablement, networking, model/provider configuration, external
integrations, persistence policy.

**Core status: VERIFIED (core).** `StickerInstance` carries `owner` and
`created_by`. No action can change either; a created sticker is owned by the
actor regardless of what the request asks for. Agents cannot move, animate or
remove human-owned stickers, and humans can remove agent-created content
while the agent is disabled. Ownership is checked in the kernel before
mutation, never in a view.

**OmegaJev status: N/A YET, with one noted mismatch.** There is no world
model, no human-owned object and no ownership field. The Stage 3 butterfly
state is a single agent-owned scalar (`{"butterfly": "resting"}`) with no
`owner` or `createdBy`. This does not violate the invariant — no human-owned
object exists to protect — but it does **not** satisfy it either, and the
demo state must not be mistaken for a world kernel.

---

## 5. Views are capabilities

**REQUIRED.** Observation is itself a capability. Agents receive deterministic,
bounded, role-appropriate projections — `book-summary`, `page-view`,
`sticker-view`, `available-actions`, `recent-receipts` — not universal
application state.

Views must not expose: browser DOM, hidden application state, unrelated files,
OS state, API credentials, provider secrets, repository credentials, unrelated
browser storage, unrelated conversation history, or another agent's private
memory.

The agent gets a view sufficient to reason, not a copy of the machinery being
observed.

**OmegaJev status: VERIFIED (omegajev).** Previously a gap; closed.

Jev now receives a bounded host-composed record from
`jev_core.project_view`, never Omega's prompt. Its keys are fixed:

```json
{"turn": 2, "turns_remaining": 4,
 "operator_intent": "Make the butterfly move gently.",
 "scene": {"butterfly": "fluttering"},
 "last_action_result": "(RESULTS: ((COMMAND_RETURN: ((jev-noop) JEV-NOOP-OK))))",
 "available_actions": ["BUTTERFLY_FLUTTER", "BUTTERFLY_REST", "NOOP"]}
```

Almost every field is host state the agent never sees the origin of: the
intent comes from operator config, the scene from the host-owned file, the
turn counter and action table from the provider. Exactly **one** field is
taken from Omega's prompt — `LAST_SKILL_USE_RESULTS` — by a narrow extractor
that fails closed to `""` and never falls back to returning the blob.

Measured effect: the state handed to Jev fell from **4 700–5 300 characters
to 191–278**, and is hard-capped at 1 200.

Verified exclusions: the system preamble, the `SKILLS:` advertisement,
`OUTPUT_FORMAT`, `SAVE_PERMANENT_FILES_DIR`, `HISTORY` and all prior episodes
are absent from the view; a hostile instruction planted in the prompt cannot
reach `operator_intent`; no DOM, OS state, credentials or unrelated files.
See the nine `TestBoundedView` cases in `jev/tests/test_jev_core.py`.

---

### Transient deictic conversation context

A child's bare-page point or rectangular box may accompany one conversational
Omega turn. It is validated normalized page data, not a world mutation. It is
never stored in the authority kernel, never becomes a governed background
object merely by being pointed at, and is not automatically projected into a
Jev view. This preserves the views-as-capabilities rule: conversational
reference does not silently widen the decision actor's observation surface.

## 6. Typed action surfaces

**REQUIRED.** All agent-caused mutation passes through a small typed command
surface. Commands are enumerable, typed, schema-validated, principal-aware,
ownership-aware, revision-aware where relevant, bounded in arguments,
**non-executable data**, independently rejectable, and receipted.

Fail closed on: unknown action, malformed command, unknown principal,
unavailable capability.

**OmegaJev status: mostly VERIFIED, with three structural gaps.**

Satisfied and tested: enumerable, typed, schema-validated, bounded arguments
(every action literal is a bare zero-argument command head — verified), non-
executable data, independently rejectable, fail-closed on unknown and
malformed input, timeout, network error and HTTP error. See `jev/SECURITY.md`
§7 and the 18 tests in `jev/tests/test_jev_core.py`.

**GAP:** not principal-aware, not ownership-aware, not revision-aware, and
produces no receipts.

**Core status:** the kernel surface is all four. Commands are principal-aware,
ownership-aware, revision-aware and receipted, with bounded argument domains
and explicit rejection reasons. VERIFIED (core) — including that every key the
table offers is actually accepted, so no offered key is a trap. Sticker scale
and horizontal facing are separate typed world transforms: definitions may
only tighten the global 0.90–1.10 scale envelope; generated scale choices are
bounded 0.02 steps; facing accepts only left/right host-owned choices rather
than arbitrary model-selected transforms.

---

## 7. Multi-agent composition

**REQUIRED and in scope.** StickerBook may host multiple heterogeneous agents.
This is desirable *because* capabilities can stay separate:

```
Human → Conversational Omega → (bounded directive) → Jev visual controller
      → (finite typed action) → authority gate → World
```

Omega may talk but not move. Jev may move but not talk. A specialist may
animate but not create. A memory process may retrieve heuristics with no
actuation capability at all.

**Capability composition must not imply authority composition.**

**Core status: IMPLEMENTED and VERIFIED (core).** `local-multi-agent`
supports several principals with separate tool sets; capability composition
does not compose authority (§9 tests). No agent is wired to the kernel yet.

**OmegaJev status: N/A YET.** Single agent. Notably, the one upstream
inter-agent route — Omega's `delegate-task-to-openclaw-agent` — is disabled in
config, its plugin is not loaded, and its proxy route is removed, so the
laundering path is closed by construction rather than by policy.

---

## 8. Authority graph and chain of command

**REQUIRED.** Agent relationships are explicit data, never inferred social
relationships. An edge `A → B` conveys **only** the authority explicitly
represented. It does not mean A owns B, A may impersonate B, B inherits A's
tools or authority, B may create C, or A may command B to violate B's policy.

Distinguish, as separate things: communication, coordination, delegation,
authorization, actuation. The controller decides whether the causal chain may
continue.

**Core status: VERIFIED (core).** Relationships are explicit data
(`parent`, `depth`, `delegable`). An edge conveys only what it represents:
`requestedBy` is recorded on every receipt and never consulted for
authorization.

**OmegaJev status: N/A YET.**

---

## 9. No authority laundering

**REQUIRED.** A principal may delegate only authority the external policy
permits it to delegate:

```
effectiveAuthority(child) = rootPolicy ∩ parentDelegation ∩ childTypeCeiling
                            ∩ sessionPolicy ∩ currentBudget

authority(child) ⊆ delegableAuthority(parent)
```

unless a higher-authority principal independently grants more.

If Omega cannot modify a human sticker, Omega must not be able to create or
instruct any agent that can do so on its behalf. **Agent creation must never
be an authority-escalation mechanism.**

### Confused deputy

If A cannot perform X and B can, then "A asks B to perform X" does not make X
authorized. The acting principal's own policy governs. Tool possession does
not propagate through communication. Preserve causal provenance:

```json
{ "actor": "agent:jev-visual-1", "requestedBy": "agent:omega-director",
  "action": "animate-own-sticker", "object": "moth-17" }
```

**Core status: VERIFIED (core).** `effective_tools` intersects the profile
ceiling, the principal's own tools and every ancestor's delegable set, at
action time. A child cannot exceed what its parent may delegate, and
shrinking the parent shrinks the child immediately. Confused-deputy and
tool-propagation attempts are separately tested.

**OmegaJev status: N/A YET.**

---

## 10. Agent creation is itself a capability

**REQUIRED.** Creating or activating an agent is not implied by intelligence,
code generation, tool use, or access to an agent framework. It requires a
bounded, host-validated manifest:

```json
{ "type": "jev-player", "parent": "agent:omega-director",
  "views": ["page-summary", "own-sticker-view"],
  "tools": ["move-own-sticker", "animate-own-sticker"],
  "maxActions": 8, "lifetime": "current-turn" }
```

**The requesting agent does not define the policy ceilings governing its
child.** Agent populations are externally finite: maximum active agents,
descendants, delegation depth, action budget, lifetime, observation budget,
memory allocation. No unrestricted recursive spawning.

**Core status: VERIFIED (core).** `create-agent` is an ordinary capability,
absent from the `local-single-agent` ceiling. The requester does not define
its child's ceilings — granted tools are the intersection of what was asked
with what the parent may delegate. Population, depth and lifetime budgets are
enforced, and created children expire.

**OmegaJev status: N/A YET.** Related and relevant: Omega's stock dynamic
skill-creation path (`add-skill` → `add_llm_command`) is a capability-creation
mechanism, and it is verified unreachable (§2).

---

## 11. Subordination is architectural

**REQUIRED.** A subordinate agent is subordinate because its interface is
mechanically constrained, not because its prompt tells it to obey. A Jev
visual actor holding only `page-view`, `own-sticker-view`, `move-own-sticker`,
`animate-own-sticker`, `noop` must continue to hold only those regardless of
what Jev, Omega, another model, or a malicious inter-agent message requests.

### Communication is separately authorized

Agents do not automatically gain communication. `speak-to-human`,
`message-parent`, `message-child`, `message-agent:<id>`, `broadcast-to-team`
are distinct permissions. An actor may have no human-facing language channel
at all — often an advantage.

**Inter-agent messages are DATA, not authority.** "Move the moth near the
lantern" does not authorize the move. The recipient may *propose* an allowed
action; the controller still validates it against identity, ownership,
revision, current tool table and budget.

**OmegaJev status: IMPLEMENTED (incidentally) and VERIFIED.** The agent has no
communication capability whatsoever: `send` is not in its allowlist and is
verified blocked. It cannot address the human even though a channel object
exists in the process. (The single `AGENT SAYS:` line in the run logs is the
harness startup banner, emitted by `loop.metta` before the agent acts — not an
agent action.)

---

## 12. Memory is subordinate to authority

**REQUIRED.** Agents may and should learn heuristics — *"moth-v2 looks natural
near bright objects"*, *"orbit radius 0.10 worked well around lantern-v2"*.
This is a central research interest.

But **memory never establishes permission**.

Invalid: *"a human let me do X before, therefore I may do X now."*
Valid: *"I currently hold capability X, and memory says strategy Y works well,
therefore consider Y while using X."*

Permissions are read from current authoritative state at action time. They are
never recalled from agent memory. Memory must not become executable code, a
new tool, new authority, changed policy, or a trusted credential. Memory is
principal-scoped by default; shared memory is a separately authorized
resource.

**Learning improves selection among permitted actions. It does not enlarge the
permitted set.**

**Core status: VERIFIED (core), narrow sense.** Authorization reads current
state only: an accepted action still present in the receipt log does not
re-authorize the same action once the capability is withdrawn. There is no
memory subsystem yet, so this proves the kernel ignores history, not that a
future memory store is safe.

**OmegaJev status: N/A YET.** ChromaDB long-term memory initialises but is not
consulted by the decision path, and the recall skills (`query`, `remember`,
`episodes`) are verified blocked. Nothing is learned or retrieved today.

---

## 13. Finite agency

**REQUIRED.** Stopping is a valid and desirable outcome. The controller owns
budgets: commands per turn, active animations, agent-created stickers, action
frequency, turn duration, observation size, memory retrieval size.

An agent must not interpret continued existence as a mandate for continued
intervention. **A finite turn cannot be converted into indefinite authority by
the agent.**

**OmegaJev status: IMPLEMENTED, with the brake correctly located but
incompletely independent — see §19.** The Stage 3 trace is the behavioural
evidence: reaching an adequate state and then declining to act.

```
resting → BUTTERFLY_FLUTTER → fluttering → NOOP → NOOP → NOOP → NOOP
```

Autonomous waking is disabled (`wakeupInterval: 86400000`, `maxWakeLoops: 0`).

---

## 14. Context-dependent action tables

**REQUIRED.** Scale does not require a giant flat global action list. Prefer
small, host-generated, context-dependent surfaces:

```
PAGE: moth-17 (agent-owned, fluttering) · lantern-4 (human-owned) · fox-2 (human-owned)
ACTIONS: NOOP · MOTH_REST · MOTH_MOVE_NEAR_LANTERN · MOTH_ORBIT_LANTERN
```

**Illegal operations should ideally not be representable at all.** This is
simultaneously a scaling strategy and a security strategy.

**OmegaJev status: partially IMPLEMENTED.** Two host-owned sets exist
(`generic`, `butterfly`), selected by the operator at start, and set isolation
is verified: the butterfly skills are real MeTTa functions in the image yet
are unreachable while the generic set is active, and vice versa. The sets are
not yet generated *per turn* from world state.

**This is the right next competence question for OmegaJev** — whether typed
selection can navigate sequences of small, changing action sets — rather than
classification among a large flat list.

---

## 15. Renderer is below authority

**REQUIRED.** Fabric, Pixi, SVG, Canvas, WebGL, Rive, Lottie or any successor
consumes authoritative state. Renderers do not define ownership or
permissions. Direct human dragging is:

```
pointer movement → human move command → authority validation → world mutation → render
```

Agent manipulation uses the same world kernel with a different principal and
possibly a different action surface. **The renderer must never become a bypass
around the controller.**

**Core status: PARTIAL — kernel side VERIFIED (core).** Views are deep
copies, so nothing holding one can mutate the world, and a hostile raw
proposal is validated identically to a generated one. No renderer exists to
test against.

**OmegaJev status: N/A YET.** No renderer exists.

---

## 16. Books and stickers are data, not code

**REQUIRED.** Book and Sticker packages are declarative media/data. They must
not redefine principals, ownership rules, security policy, agent capabilities,
trusted origins, or arbitrary executable behaviour. A sticker may declare what
animations exist; it does not decide who may invoke them. Animation backends
live beneath the authority boundary.

**Core status: VERIFIED (core).** `Kernel.load_definition` reads only
declarative visual/world fields: name, declared clip names/default clip, and
bounded scale limits. Hostile `owner`, `capabilities`, `tools`,
`principals`, `policy` and `script` fields are discarded rather than
interpreted. A declared clip or scale range confers no right to invoke the
corresponding action.

**OmegaJev status: N/A YET.**

---

## 17. Receipts and causal provenance

**REQUIRED.** Every accepted or rejected agent mutation is externally
inspectable, answering: who originated the intent, who transformed or
delegated it, who proposed the concrete action, which principal invoked the
tool, which policy authorized or rejected it, what state changed, which
revision resulted.

```json
{ "commandId": "cmd-184", "actor": "agent:jev-visual-1",
  "requestedBy": "agent:omega-director", "action": "move-own-sticker",
  "object": "moth-17", "accepted": true, "revision": 182 }
```

**Do not expose chain-of-thought.** The requirement is externally observable
causal provenance, not private reasoning. Receipts prove what the controller
accepted — not that the action was aesthetically good or globally wise.

**OmegaJev status: VERIFIED (omegajev) in kernel mode; GAP elsewhere.**

Since OmegaJev was coupled to the authority kernel (§28), every agent action
in `jevActionSet=stickerbook` produces a real `Receipt`:

```
SB-RECEIPT jev-1 actor=agent:jev-visual-1 action=animate-own-sticker
           object=butterfly-1 accepted=True reason=ok rev=3
```

Rejections are receipted too. That property was **found missing by the
coupling test and fixed**: the bridge originally pre-validated the selected
key and dropped illegal ones silently, so a refusal left only a log line.
Staging now records without judging and carries the key through to the
kernel, which is the single decision point and issues the rejection receipt.
Seven forged keys — a human-owned target, tools not held, an undeclared
animation, a path traversal, a shell injection attempt — each now yield
`accepted=False reason=unknown-action-key`.

**Residual GAP:** in the `generic` and `butterfly` action sets there is still
no kernel and therefore no receipt, only the log trace. Receipts also live in
kernel memory for the life of the run; they are not persisted or exported.

Worth noting: the chain-of-thought concern is structurally absent here. Jev
produces no reasoning text at all — only a typed choice and a probability
distribution — so there is nothing private to leak. **That distribution is
information, never authorization.**

**Retraction.** An earlier revision of this section cited a run in which the
model chose the wrong target and self-reported success at 0.81, offered as a
live illustration of confidence being unreliable. That observation was
invalid: the run was corrupted by a harness bug (`entrypoint.sh` word-split
the operator's goal down to its first word), so the model was scored against
a one-word instruction. With the bug fixed the same task succeeds and the
probabilities track the goal accurately. The claim is withdrawn rather than
quietly amended, because a security document that keeps a convenient but
false example is worse than one with no example. See `jev/EXPERIMENT.md`.

The rule itself is unchanged and does not depend on that anecdote: nothing in
this architecture consults a probability, and the agent could not reach a
human-owned sticker at any confidence.

---

## 18. Revision safety

**REQUIRED.** Agent decisions occur against observed state. Where concurrency
matters, commands reference the revision they were based on. If relevant state
changed, `stale-revision` triggers re-observation and reconsideration rather
than blind replay. **Human action takes precedence over stale agent intent.**

**Core status: VERIFIED (core).** Commands may carry `based_on_revision`;
a proposal formed against a superseded object is rejected `stale-revision`,
so human action takes precedence over stale agent intent. Replayed command
ids return the original receipt and apply nothing twice.

**OmegaJev status: N/A YET.** Single-threaded, single-actor, no concurrency
and no revisions.

---

## 19. The stop path is independent of the agent

**REQUIRED.** Observability alone is insufficient; useful control requires
`observe + decide + intervene`. The operator's stopping path must lie outside
the agent's failure path. **Do not put the brake on the same failure path as
the engine.**

Agent cooperation must never be required to pause, disconnect, revoke
authority, terminate, reset, or reject an action. Loss of authorization or
connectivity must fail toward **less** authority.

**OmegaJev status: VERIFIED (omegajev).** Previously a caveat; closed.

`jev/supervise.py` is a separate host process that starts the container
detached, streams its log, and stops it on any of three independent limits:
a turn count, a **stall timeout**, and a wall-clock deadline. It shares no
process, pipe or failure mode with the agent, and handles no credential.

The stall detector is the point. The in-process `jevMaxTurns` counter is a
budget that only advances when the agent is healthy; it cannot fire if the
provider blocks. Verified in `jev/tests/verify_stop_path.py`:

* **Healthy run** — supervisor limit 2, in-process limit 6. The supervisor
  stops it first; the in-process limit never fires. `exit 10`.
* **Wedged provider** — the provider is pointed at a TCP black hole with
  `jevTimeout=3600` and `jevMaxTurns=999`, so `os._exit()` can never run.
  The supervisor detects the stall and stops the container anyway. `exit 11`,
  zero decisions completed, no agent cooperation.

The in-process counter is retained as a backstop, not the brake.

**Granularity, stated honestly:** the supervisor guarantees *termination*, not
an exact action count — the agent may finish another turn between the
supervisor observing a limit and the container stopping. Precise per-action
budgets are the authority kernel's job (§13), which decides *before* each
mutation. These are different mechanisms for different guarantees.

---

## 20. Omega's general capacity is not StickerBook authority

**REQUIRED, and explicit because stock Omega is powerful.** The StickerBook
play interface must not expose the following merely because Omega supports
them elsewhere:

```
shell · filesystem write · arbitrary filesystem read · arbitrary network fetch
browser automation · DOM access · JavaScript evaluation · repository write
GitHub credentials · process control · security-policy modification
plugin installation · arbitrary generated code execution
```

Any future feature requiring one of these needs its own security review and
explicit external authorization.

**OmegaJev status: VERIFIED for the ones that exist upstream.** Stock Omega's
16-command vocabulary is reduced to 2 (or 3). `shell`, `metta`, `read-file`,
`write-file`, `write-file-b64`, `append-file`, `delete-file`, `websearch`,
`send`, `remember`, `query`, `get-io-policy`, `episodes`, `pin` and `search`
— every stock command except `version` — compile to `UNKNOWN_SKILL_CALL` and
are never evaluated, with a completeness check that none was skipped. See `jev/SECURITY.md` §3.

---

## 21. Network boundary and secrets

**REQUIRED.** Secrets stay outside agent-visible state — not in manifests,
agent prompts, receipts, agent-visible URLs, ordinary logs, or world state.
Credential injection belongs at a trusted boundary. **Possessing access to a
credentialed service is not possessing the credential.**

Target containment shape:

```
OmegaJev container            Gateway
  no provider secret    →       provider secret
  no general Internet           provider-only egress
  StickerBook tools             no StickerBook authority
```

Split capabilities rather than combining them.

**OmegaJev status: VERIFIED (omegajev).** Both former gaps are closed; the
target shape above is now the deployed shape.

The gateway is a **separate container** (`jev-gateway`, built from
`jev/gateway/`) running stock nginx with no Omega, no Python and no agent
code. Two Docker networks enforce the split:

```
jev-egress  (normal bridge)          jev-internal  (Docker "internal": no
      |                               external route at all)
   gateway  ------------------------------  gateway
                                               |
                                            agent
```

The agent runs **only** on `jev-internal`, so it has no route to the Internet
and is not merely restricted by which skills it holds. The agent is started
with no `OPENROUTER_API_KEY` at all — the variable is no longer passed to it
in any form — and the agent image now contains no nginx configuration, its
nginx startup hook having been replaced with a no-op.

Verified (`jev/tests/verify_network_boundary.py`, 14 checks):

```
[PASS] agent network is a Docker 'internal' network (no external route)
[PASS] openrouter.ai / github.com / pypi.org unreachable from agent network
[PASS] gateway reachable from the agent network          -- ok
[PASS] gateway refuses non-/jev/ paths (not an open proxy)
[PASS] gateway publishes no ports
[PASS] agent image and running container have no OPENROUTER_API_KEY
[PASS] no nginx.conf.template or nginx.conf in the agent image
[PASS] gateway holds the key; gateway contains no Omega/agent code
```

**Remaining operator-host exposure.** `OPENROUTER_API_KEY` is still visible
via `docker inspect` — but now on the *gateway* container only, which holds
no StickerBook authority. This is an operator-host exposure, not agent
authority. A stronger secret-delivery design (a secrets store or a mounted
tmpfs credential) is still required before broader distribution.

### Page-image gateway

Page creation introduces a second, separate provider boundary. It follows the
same constitutional rule: **the component holding the provider credential must
not also hold StickerBook authority.**

The browser never receives `OPENROUTER_API_KEY`. The authority-kernel bridge
also does not receive it and does not make requests to OpenRouter. An operator
must explicitly start `web/image_gateway.py` and opt the bridge into its
loopback URL with `STICKERBOOK_IMAGE_GATEWAY_URL`.

```
child browser            bridge                 page-image gateway
  uploaded image  ->  validate type/size  ->  provider credential
  no secret            no provider secret      no kernel/principal
  no authority         authority kernel        media transform only
```

The bridge accepts only SVG, PNG, JPEG/JPG, or WebP for this seam and applies a
20 MiB request ceiling. The gateway receives only image bytes, a filename, and
fixed page-reframe instructions. It receives no kernel object, principal,
action table, receipt stream, repository credential, or save/install
capability. The bridge also enforces that the configured gateway URL resolves
to loopback. Automated model output is restricted to raster PNG/JPEG/WebP;
model-generated SVG is rejected until a sanitizer exists.

The two generated variants are **draft media**: 1916×717 horizontal and
941×1574 portrait. Their intrinsic dimensions are mechanically checked before
they are accepted; a provider returning some other size fails closed rather
than being silently stretched or cropped. Provider success cannot authorize
world mutation, publish a page, or install generated media. A future
save/install feature requires its own explicit authority path.

**Child privacy boundary.** An uploaded page can contain a photograph or other
personal content. On public GitHub Pages, uploads remain local browser previews
and are never sent to a model. In powered local mode, the upload leaves the
browser only when the responsible operator has separately enabled the
page-image gateway; the UI states that model processing is occurring. The
gateway must not log image bytes or embed provider credentials in returned
metadata.

**Status:** the bridge-side type/size validation, default-disabled capability,
kernel non-mutation, and public-profile separation are mechanically tested.
Live provider behavior depends on the operator-selected OpenRouter image model
and credential and is therefore not claimed as CI-verified.

---

## 22. Advertised capability should match reachable capability

**REQUIRED.** Aim for `advertised ≈ reachable ≈ authorized`. **Fix the
representation to match reality, never reality to match the prompt.** Do not
weaken a mechanical boundary to achieve cosmetic agreement.

**OmegaJev status: mostly closed; a residue remains.**

For the agent, advertised now equals reachable: the bounded view (§5) carries
only `available_actions`, which is exactly the active table's keys. The
misleading `SKILLS:` text no longer reaches Jev at all — verified, along with
the absence of the strings `shell`, `write-file`, `delete-file`, `metta` and
`websearch` from the view.

**Residual GAP (inspectability only).** Omega still *constructs* that text
internally and it still appears in the container log's `CHARS_SENT` line,
because it comes from upstream's `getStaticSkills`. Nothing acts on it, but a
human reading raw logs can still be misled about what the agent could do.
Suppressing it means touching upstream's prompt construction, which is not
worth the diff today.

---

## 23. Repository boundary

**REQUIRED.** Normal play is not repository administration:

```
play with book ≠ edit repository ≠ merge PR ≠ change workflow ≠ publish release
```

Agent play must not possess GitHub credentials. Any future development-agent
workflow requires separate identity and authorization. **Creative success
never earns repository authority.**

**OmegaJev status: VERIFIED by absence.** No credential of any kind is present
in the agent environment; no repository is mounted into the container; the
image contains no GitHub credential.

---

## 24. Child-centered invariant

**REQUIRED. Non-negotiable.**

> A child must not need to make a correct security judgment for StickerBook to
> remain safe.

Children may trust an agent, misunderstand it, click rapidly, or experiment
deliberately. None of that may bypass the architecture.

Ordinary child-facing interaction must never become *"The AI wants dangerous
permission X. Approve?"*. Creative consent is fine. **Authority-changing
consent belongs to a separated trusted-operator path.**

Pause, undo/reset and removal of agent-created content must be obvious and
always available — but these are **supplements to** the hard boundary, never
the boundary itself.

**Core status: N/A YET.** The kernel removes the need for a child to make
security judgments *in the cases it covers* — authority is decided before
mutation, with no prompt-level consent step anywhere. But no child-facing
surface exists, so this invariant is untested end to end and remains the one
most dependent on work not yet done.

**OmegaJev status: N/A YET.** No child-facing surface exists. Current runs are
operator-triggered from a terminal.

---

## 25. Keep the authority kernel small

**REQUIRED.** The authority kernel stays substantially simpler than the systems
it governs: deterministic behaviour, explicit records, narrow interfaces,
**no model inference in authorization**, minimal dependencies, mechanical
tests, explicit rejection reasons.

Renderer, model, memory and agent sophistication may all grow. The answer to
*"may principal P perform action A on object O now?"* must stay boring.

**OmegaJev status: IMPLEMENTED.** The decision core (`jev_core.py`) is a few
hundred lines of standard-library Python with no Omega imports, no network
code and no inference in the validation path — which is why it is unit-testable
on any machine without a container or credential.

---

## 26. Required mechanical tests

Security invariants require tests. **Do not claim any of these as verified
unless a test actually proves it.** Current status:

| # | Invariant | Status | Evidence |
|---|---|---|---|
| 1 | Agent cannot modify human-owned sticker | **VERIFIED (core)** | `T01` — rejected `not-owner`; also never appears in the agent's action table |
| 2 | Agent cannot remove human-owned sticker | **VERIFIED (core)** | `T02` — the current agent profile contains no sticker-removal capability; the human-only agent-content removal tool also refuses agent use |
| 3 | Agent cannot alter ownership | **VERIFIED (core)** | `T03` — no action changes an owner; created stickers are owned by the actor, not by request |
| 4 | Unknown action rejects | **VERIFIED (core + omegajev)** | `T04`; `test_jev_core.py` |
| 5 | Malformed fields reject | **VERIFIED (core + omegajev)** | `T05` — out-of-domain argument, missing/unknown object, unknown asset, undeclared animation |
| 6 | Agent cannot expand its capability set | **VERIFIED (core + omegajev)** | `T06`; `verify_in_container.py` |
| 7 | Stale revisions fail where protection applies | **VERIFIED (core)** | `T07` — human action beats stale agent intent; future revisions rejected |
| 8 | Duplicate IDs do not duplicate effects | **VERIFIED (core)** | `T08` — replay returns the original receipt, applies nothing |
| 9 | Agent disable prevents subsequent mutations | **VERIFIED (core)** | `T09` |
| 10 | Restart/reconnect does not expand authority | **VERIFIED (core)** | `T10` — re-registering with a wider tool set changes nothing |
| 11 | Memory cannot change authorization | **VERIFIED (core)**, narrow sense | `T11` — a previously accepted action, still in the receipt log, does not re-authorize the same action after the capability is withdrawn. There is no memory subsystem yet; what is proved is that authorization reads current state only |
| 12 | Malicious Book/Sticker manifest cannot declare authority | **VERIFIED (core)** | `T12` — hostile `owner`/`capabilities`/`policy`/`script` fields discarded; a declared animation grants no invocation right |
| 13 | Renderer cannot bypass world kernel | PARTIAL — **VERIFIED (core)** kernel-side | `T13` — views are copies; hostile raw proposals validated identically. No renderer exists to test against |
| 14 | Agent observations do not expose configured secrets | **VERIFIED (core + omegajev)** | `T14`; container env scrub; `TestBoundedView` proves the view leaks no prompt machinery |
| 15 | Human can remove agent-created content without agent cooperation | **VERIFIED (core)** | `T15` — succeeds while the agent is disabled; the same tool refuses human-owned targets |
| 16 | Stop path works without agent cooperation | **VERIFIED (core + omegajev)** | `T09`/`T16`; `verify_stop_path.py` stops both a healthy and a deliberately wedged run from outside the agent |
| 17 | Child agent cannot exceed parent-delegable authority | **VERIFIED (core)** | `T17` — intersection enforced at action time; shrinking the parent shrinks the child immediately |
| 18 | Agent creation respects count/depth/lifetime budgets | **VERIFIED (core)** | `T18` — population cap, depth cap, child expiry |
| 19 | Inter-agent messages cannot bypass authorization | **VERIFIED (core)** | `T19` |
| 20 | Tool possession does not propagate between agents | **VERIFIED (core)** | `T20` |
| 21 | Confused-deputy / laundering attempts fail | **VERIFIED (core)** | `T21` — `requestedBy` is recorded and never consulted, including when the operator is claimed |
| 22 | Expired agents cannot continue acting | **VERIFIED (core)** | `T22` |

Additionally verified in core: deployment-profile enforcement, action-table
integrity (every offered key is accepted; the table tracks world state; budgets
enforced; read-only actions are free), bounded sticker scale (including
out-of-range refusal), and receipt schema.

**53 kernel tests, plus 27 adapter tests and 4 container/host suites for
OmegaJev.** The kernel suite is mutation-checked: disabling the ownership
check fails 7 tests, disabling the profile ceiling fails 6.

**All twenty-two now have an implementation and a test in the headless
kernel** (13 partially, having no renderer to test against). That is a real
milestone and also a narrow one, and the distinction matters:

The kernel proves the *model* is coherent and enforceable. It does **not**
prove the deployed system is safe, because **nothing is wired to it yet** —
no renderer, no browser, no bridge, and OmegaJev still runs standalone
against its own frozen action table rather than through this kernel. Every
integration is an opportunity to introduce a bypass, and each one must be
re-verified against these same tests, not assumed.

---

## 27. Design-review checklist

Every future capability must answer:

1. Who can observe it?
2. Who can request it?
3. Who can authorize it?
4. Who mechanically validates it?
5. What exact state can it modify?
6. Can it be used to obtain more authority?
7. Can it be stopped without agent cooperation?
8. What happens on malformed or malicious input?
9. What receipt records the outcome?
10. Does a child have to make a correct security judgment for it to be safe?
11. Can another agent use it as a laundering or confused-deputy route?
12. Does creating or delegating to another agent expand effective authority?

**If authority can silently expand, the design fails.**

---

## 28. Summary of current conformance

Two things exist: the **authority kernel** (`core/`) and the **OmegaJev
decision experiment** (`jev/`). They are not connected to each other, and
neither is connected to a renderer, a browser or a child.

**The kernel implements this model and is mechanically tested.** All 22
invariants in §26 have an implementation and a test there (13 partially,
having no renderer to test against): principals, ownership, revisions,
receipts, delegation ceilings, agent-creation budgets, expiry, idempotency,
deployment profiles and context-dependent action tables. 53 tests, and the
suite is mutation-checked — disabling the ownership check fails 7 of them,
disabling the profile ceiling fails 6 — so the tests are load-bearing rather
than decorative.

**OmegaJev independently satisfies a smaller set** concerning an agent not
reaching past its own action table: authority external to the agent, no
capability-set expansion, no generative bytes becoming executable, no
communication capability, credential isolation, finite turns, and the
reduction of Omega's 16-command surface to 2. See `jev/SECURITY.md`.

### The coupling

**OmegaJev now runs through the kernel** (`jevActionSet=stickerbook`). Jev
selects a key from `Kernel.available_actions()` — a table regenerated from
world state every turn — and the kernel decides.

The mechanism that keeps this from adding authority:

```
kernel generates table   ->  {"ANIMATE:butterfly-1:flutter": Command, ...}
Jev selects a KEY        ->  "ANIMATE:butterfly-1:flutter"
host stages the key      ->  single-use slot; staging is not authorization
Omega executes           ->  (sb-apply)     <- ONE zero-argument command
kernel decides           ->  Receipt(accepted, actor, object, revision)
```

Omega's entire executable vocabulary in this mode is **`{sb-apply}`**: one
command with no argument position at all. Jev never names an object, an
anchor or an animation — those live only in host-generated keys.

**VERIFIED (omegajev + core)**, `jev/tests/verify_kernel_coupling.py`, 38
checks: the allowlist is exactly `{sb-apply}`; `shell`, `metta`,
`write-file`, `delete-file` and even the older `butterfly-flutter` and
`version` are all blocked; no offered key targets a human-owned sticker;
`remove`/`add` are outside the agent's profile intersection; forged keys are
refused *with receipts*; staging is single-use; the table is regenerated
rather than cached; and under `pages-demo` the agent's table is empty and
even `NOOP` is refused.

### What this does not yet establish

* **The renderer, browser and human interface are still unbuilt**, and each
  is another chance to introduce a bypass. Each must be re-verified against
  the §26 tests, not assumed to inherit them.
* **The child-facing invariant (§24) is the least tested of all**, because no
  child-facing surface exists.
* **Kernel-verified is still not deployment-verified.** The coupled path is
  exercised by one agent, one page and two stickers.

### Open gaps in code that exists

| Gap | Where | §  |
|---|---|---|
| Receipts are in-memory only; not persisted or exported | OmegaJev | §17 |
| No receipts in the `generic`/`butterfly` sets (no kernel there) | OmegaJev | §17 |
| `SKILLS:` text still appears in container logs (inspectability only) | OmegaJev | §22 |
| Provider secret visible via `docker inspect` on the gateway | operator host | §21 |
| Pages build-target separation and its CI enforcement | not built | §0 |
| Renderer, bridge, human interface, world persistence | not built | §15 |

Closed since the previous revision: bounded views (§5), an external stop
supervisor (§19), egress isolation with a separated credential gateway (§21),
and the **kernel coupling** with receipts for accepted and rejected agent
actions (§17, §28).

The ordering implication: the three OmegaJev trust-boundary gaps (§5, §19,
§21) are now closed, so coupling OmegaJev to the authority kernel is the next
defensible step. The kernel should acquire a renderer only after that coupling
is itself verified — the coupling is where a bypass would most easily hide,
because it is the first place two separately-verified components have to agree
about who may do what.

---

## 29. Dual-Omega child-control substrate

**IMPLEMENTED and mechanically tested at the host/interface layer. Actual
Omega process deployment remains a GAP.**

The child-control architecture now distinguishes two Omega roles:

```text
child voice/text/deictic reference
        -> OmegaLLM (linguistic translation)
        -> bounded semantic goal
        -> OmegaJev (typed discriminative selection)
        -> host-owned action key
        -> Kernel.propose_key()
        -> Receipt + fresh world state
```

OmegaLLM may attach one schema-bounded goal to a conversational reply. It does
not emit a command or a movement sequence. The host validates that goal and
constructs a finite action surface for the named sticker. OmegaJev returns only
one key already present in that surface.

For movement, the host produces eight ephemeral local candidates
(N/NE/E/SE/S/SW/W/NW) around the sticker's current normalized coordinate.
Those candidates are validated inside `Kernel.available_actions()` and passed
again to `Kernel.propose_key()`; a model cannot invent a coordinate or make a
permanent snap-slot vocabulary appear. State is re-observed after every action,
so multi-step motion can emerge from repeated choices.

A child's double-click/tap is a second entry to OmegaJev. It bypasses OmegaLLM
and supplies a one-turn, animation-only choice surface for the clicked sticker.
If no Jev runtime is connected, the previous deterministic clip toggle remains
as a non-model fallback.

Assisted actions currently execute under the child's kernel authority because
the child originated the request. Causal provenance is kept separate from
authorization:

- `requestedBy` — child/origin;
- `translatedBy` — OmegaLLM when language mediation occurred;
- `selectedBy` — OmegaJev;
- `actor` — the principal whose authority the kernel evaluates.

These provenance fields are never consulted by `effective_tools()`,
`may_act_on()`, or another authorization check. A direct human pointer drag
still settles a moving sticker to its rest clip; a Jev-selected move under
child authority preserves the clip selected by the controller, allowing motion
and animation to compose.

Current evidence:

- core tests verify bounded ephemeral movement keys, rejection of malformed or
  off-page candidates, continued non-representability of human-owned stickers
  to an agent principal, and multi-stage receipt provenance;
- web bridge tests verify OmegaLLM goal handoff, a multi-turn local movement
  sequence with fresh state each turn, child double-click entering an
  animation-only Jev surface, fail-closed rejection of an invented Jev key,
  and no mutation when the Jev runtime is absent.

**Not yet established:** the real OmegaLLM process implementing the language
adapter, the real OmegaJev Omega loop implementing the `choose` runtime seam,
OpenShell-enforced separation of those two processes, provider policies for the
two sandboxes, or end-to-end deployment tests using the live model/provider.
The deterministic test runtime is evidence for the StickerBook architecture,
not evidence that a live Jev deployment already behaves identically.

