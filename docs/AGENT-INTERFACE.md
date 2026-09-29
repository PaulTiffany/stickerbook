# Dual-Omega play interface

StickerBook separates linguistic interpretation, embodied decision selection,
and authority.

> **OmegaLLM translates. OmegaJev chooses. The kernel decides.**

OmegaLLM and OmegaJev are intended to be two separate Omega agent loops.
OmegaLLM bridges the child's language/voice/deictic reference into a bounded
semantic goal. It does **not** prescribe a motor program. OmegaJev receives the
goal plus fresh world feedback and repeatedly selects one key from a small
host-owned action table. This lets movement patterns be discovered as sequences
of local choices rather than being secretly hard-coded by the language model.

## Conversation is not authority

The browser sends human language to OmegaLLM through:

`POST /api/agent/converse`

The bridge validates the input and fixes the browser principal. OmegaLLM
receives only the validated text, the fixed browser principal id, a bounded
JSON scene view, the child-facing help projection, the host-selected
provider/model record, and the optional transient deictic reference for that
turn. It never receives the authority-kernel object
or the responsible-adult guide.

OmegaLLM returns language and may optionally attach one bounded `goal` object,
for example:

```json
{
  "subject": "cow-1",
  "intent": "move-and-animate",
  "behavior": "look",
  "target": {"kind": "point", "x": 0.42, "y": 0.86}
}
```

That object is data, not a command. The host validates its schema, regenerates
the legal Jev surface from authoritative state, and gives OmegaJev only the
goal, a bounded scene projection, and descriptions of the offered keys.
OmegaJev may return only one supplied key. The selected key then goes through
`Kernel.propose_key()`; the kernel remains the mutation gate.

The causal receipt records the child as the authority/origin
(`requestedBy`), OmegaLLM as the linguistic transformer
(`translatedBy`), and OmegaJev as the selector (`selectedBy`). None of
those provenance fields are consulted for authorization.

## Child-facing documentation is a bounded view

The in-app help source is `web/static/help.json`, with separate `child` and
`adult` branches.

The browser may render both branches to their intended audiences. OmegaLLM
receives **only** a defensive copy of the `child` branch under:

```json
{
  "scene": {
    "child_help": {
      "title": "How StickerBook works",
      "intro": "...",
      "topics": [...]
    }
  }
}
```

This gives conversational Omega a stable source of truth for questions such as
"How do I play?", "What happens if I double-tap?", or "What can you do?".

The child branch intentionally excludes operator setup, API keys, OpenShell,
Docker, repository administration, provider configuration, and policy approval.
The parent guide is not secret; it is simply **outside OmegaLLM's observation
surface**.

Documentation is descriptive data. It cannot grant a capability or authorize a
mutation.

## Responsible-adult inference selection is host state

The powered host exposes a separate adult-only route:

`GET /api/adult/inference` / `POST /api/adult/inference`

This route selects which **already configured** inference lane OmegaLLM uses for
the current bridge session. It is not part of the normal browser state and is
not copied into `scene.child_help`.

Current lanes are:

- Sponsored ASI Cloud — fixed to `minimax/minimax-m3`;
- Anthropic — default `claude-opus-4-8`;
- OpenAI — default `gpt-5.5`;
- OpenRouter — default `z-ai/glm-5.2`, with a bounded model-id field;
- ASI:One — default `asi1-ultra`;
- Off.

The bridge chooses the session lane and passes only the selected
`{provider, model}` record to the OmegaLLM loopback adapter. A child request
cannot override it by adding an inference field, and OmegaLLM cannot choose a
different endpoint, credential, or billing source.

The selector is currently an **audience control rather than authenticated
parental security**. A person with direct access to the local loopback browser
and developer tools can call the adult route. That does not grant world
authority—the kernel remains unchanged—but a deployed product that needs to
protect paid inference from a child would need an authenticated adult boundary.


## Creator drafts are also non-authoritative

`POST /api/creator/draft`

is a second non-authoritative seam. It can return a proposed page or sticker
asset description. Sticker drafts target asset schema v2, where one
StickerDefinition can contain an idle clip plus one or more behavior clips,
and each clip can contain one or many related image frames.

A creator draft does not install itself and cannot grant a behavior that the
world/kernel definition does not already permit.

## Page-image creation is a separate media seam

Child-selected page artwork uses a third non-authoritative path:

`POST /api/creator/page-image`

The browser sends the original image bytes to the local bridge. The bridge
accepts only SVG, PNG, JPEG/JPG, or WebP, enforces an upload-size ceiling, and
does not itself hold a provider credential.

Only when a responsible operator has explicitly configured
`STICKERBOOK_IMAGE_GATEWAY_URL` does the bridge forward the validated image
to a separately started loopback page-image gateway. That process may hold
`OPENROUTER_API_KEY`, but it has no StickerBook principal, kernel object,
legal-action table, or world-mutation interface.

The gateway asks the configured OpenRouter image-editing model to produce two
drafts from the **same original upload**:

- horizontal: exactly **1916 × 717**, named `<stem>.<ext>`;
- portrait: exactly **941 × 1574**, named `<stem>-vertical.<ext>`.

Both jobs use the fixed reframe/outpaint instructions in `web/page_assets.py`:
preserve the original artwork and composition, do not reinterpret it, expand
surrounding background rather than stretching, and add no unrelated objects,
text, or design elements. OpenRouter image parameters differ by model, so the
gateway does not assume a universal custom-size control. It verifies the
intrinsic dimensions of each returned SVG/PNG/JPEG/WebP and rejects a result
unless it is exactly the requested canvas.

Provider output remains media/data. Automated output is restricted to raster
PNG/JPEG/WebP; SVG may be uploaded as source art but model-generated SVG is
rejected until it has a dedicated sanitizer. Generated files are stored only
in ignored local runtime storage until an explicit save/install path exists.
Generation therefore cannot add a page to the governed book or gain authority
over StickerInstances.

The public GitHub Pages profile contains no Python bridge, page-image gateway,
provider credential, or model call. Upload there is a local browser preview
only.

## Voice-first child interface

Normal child-facing play has no persistent chat panel.

When a conversational runtime is connected, a responsible adult can enable
voice for the current browser session. Only then does a small push-to-talk
microphone appear on the active page.

The browser's speech-recognition implementation may use a browser/device speech
service. StickerBook therefore does not silently enable it. The responsible
adult panel states this explicitly.

The recognized text is sent to the local conversational endpoint. A returned
reply may be spoken with the browser's speech-synthesis facility.

## Optional text projection

Voice and text are two projections of the same conversational interface. A
responsible adult may optionally expose the translucent text chat on the play
surface for accessibility. There is no separate adult-panel chat path.

The public mechanical build allows that text surface to be exercised with a
fixed stub reply; no conversational model is called.

## Child deictic page reference

Conversation may carry one optional transient reference alongside the child's
utterance. The browser creates it only from a bare-page tap or rectangular
drag and sends normalized page coordinates:

```json
{"kind":"point","point":{"x":0.71,"y":0.58}}
{"kind":"box","box":{"x1":0.1,"y1":0.2,"x2":0.6,"y2":0.7}}
```

The localhost bridge validates the coordinates, attaches the governed page id,
and gives the reference to conversational Omega only for that turn. It never
enters kernel state and is not automatically included in a Jev observation.
Thus pointing at pixels can help Omega understand what the child means without
silently turning painted background content into governed objects.

## Sticker action substrate

The shipped sticker substrate deliberately separates visual pose from governed
world transforms.

A StickerDefinition declares visual sprite names, clip names, a default/rest
clip, and scale bounds. A StickerInstance carries authoritative position and
scale plus its current clip (still exposed on the historic `animation` wire
field for compatibility). The v4 built-ins use frame sprites for clips; their
clip recipes do not smuggle locomotion through CSS transforms.

Translation, apparent depth, and horizontal facing are world state. Scale is
currently bounded to 0.90–1.10 globally, and the host-generated action table
offers only bounded 0.02 scale steps. Facing is a typed left/right transform
with host-generated FACE choices. The kernel validates both independently.

For OmegaJev movement the host also supplies an **ephemeral local movement
alphabet** each turn (N, NE, E, SE, S, SW, W, NW). Each entry is just another
host-owned candidate coordinate checked by the kernel. The page itself remains
continuous; there are no permanent snap slots. After each selected step the
world is re-observed and a new table is generated, so OmegaJev can form
movement patterns from feedback.

The current local agent authority profiles intentionally contain no sticker
removal capability. Human control retains removal. This is non-representability,
not a prompt instruction.

### Two ways a child can ask OmegaJev to animate

1. **Through OmegaLLM.** Language such as “make the cow look over here” may be
   translated into a bounded goal. OmegaJev can then choose the declared clip
   and/or local movement steps over several turns.
2. **Direct double-click/tap.** The existing child gesture bypasses OmegaLLM
   and enters OmegaJev as a one-turn animation goal. The action surface contains
   only declared animation choices for that sticker plus NOOP. If no Jev runtime
   is connected, StickerBook retains the historical deterministic animation
   toggle so ordinary play still works.

A Jev-selected move performed under the child's authority preserves a clip that
Jev selected previously. A literal human pointer drag still interrupts motion
and settles the sticker to its rest clip.

The bounded scene contains only explicitly declared objects/state. A generated
action key must not reveal an undeclared object merely by naming it. Painted
background pixels remain passive scenery unless OmegaLLM turns a validated
child reference into explicit bounded goal data.

## Movement-pattern memory

A child is not programming an agent. The child is teaching a sticker a way it
likes to move, and StickerBook remembers it:

> "Remember that as your happy dance."

The research invariant is that **learning changes memory, not authority**. A
remembered pattern means only

> when asked for this behavior, these previously accepted action forms
> occurred in this order

and never

> these actions are now permitted.

### Representation

Legal keys have the form `<VERB>:<sticker-id>:<suffix>`, and a suffix alone is
ambiguous: `STEP-E` belongs to `MOVE` while `spin` belongs to `ANIMATE`. A
remembered step therefore keeps its action family and discards only the
transient StickerInstance id:

```text
PatternStep(verb="MOVE",    suffix="STEP-E")
PatternStep(verb="MOVE",    suffix="STEP-N")
PatternStep(verb="ANIMATE", suffix="hop")
```

A `MovementPattern` is an ordered sequence of those fragments plus a stable
id, a child-facing label, the StickerDefinition it applies to, and provenance.
It is frozen data: no coordinates, no command, no capability, nothing
callable. Complete legal keys are never stored, because they name a particular
StickerInstance that may not exist or may not be legal later.

`web/pattern_memory.py` deliberately sits beside the bridge rather than inside
`stickerbook_core`, so the authority kernel cannot acquire pattern awareness by
accident. Pattern memory adds **no kernel mutation primitive**.

### Capture

Only a trace of actions that produced **accepted** kernel receipts can become a
pattern. Rejected, unavailable, malformed or merely proposed actions do not
become learned movement, and a `NOOP` is a decision to stop rather than a way
of moving. Each captured step is cross-checked against its receipt, so a `MOVE`
step cannot be recorded from an `ANIMATE` receipt.

`JevController.remember_trace()` is the seam where OmegaLLM will eventually
land: the child says "remember that as your happy dance", and OmegaLLM turns
that sentence into one bounded host request carrying a label and the trace that
just happened. OmegaLLM never writes arbitrary actions into a pattern.

### Replay

`JevController.replay_pattern()` is **mechanical replay**: the host performs
the remembered forms step by step so pattern safety can be proven without a
live Jev. It is not a macro with authority. For every step:

1. the world is re-read;
2. the current host-owned legal table is rebuilt;
3. the key is re-derived from the stored `(verb, suffix)` plus the **current**
   subject;
4. that exact key must exist in the table as it is right now;
5. it is submitted through the ordinary `Kernel.propose_key()` path;
6. an accepted receipt is required before advancing;
7. an unavailable or refused step stops the replay where it stands.

So stale learned behavior gets no bypass. Two steps east near the eastern edge
execute once and then stop, because the second step is no longer offered. A
clip the current StickerDefinition does not declare never executes. A pattern
learned for one definition is refused on an incompatible one. Ownership and
per-turn budgets remain kernel restrictions.

### A finite action table belongs to one world revision

> A finite action table containing absolute move destinations is valid only
> against the world revision from which that table was constructed. Model
> think-time never refreshes the revision attached to an old choice.

`JevController._move_candidates()` offers eight local steps as **absolute page
destinations**, computed from where the subject is when the table is built.
`Kernel.available_actions()` bakes those coordinates into each `MOVE` key. A
selection made against that table is therefore a claim about *that* world, not
a relative nudge that stays correct later.

This matters because the world lock is deliberately released across chooser
inference. A child can move the same sticker while OmegaJev is thinking. Every
proposal consequently names the revision its own table came from:

```text
table/scene built at revision R
  MOVE key encodes a destination derived from R

world lock released; OmegaJev thinks
child drags the same sticker    -> world becomes R+1

OmegaJev returns a key from the R table
host submits it with based_on_revision=R
kernel answers stale-revision
```

Had the host re-read the revision at submission time, the kernel would have
accepted an R-derived coordinate as current and the child's own gesture would
have been silently undone. Powered pattern execution follows this rule, as do
the ordinary bounded goal loop and mechanical replay. The child is the
higher-authority actor, and a superseded agent proposal is recorded as a
refused step rather than retried over them.

### Two modes, and why Jev still matters

1. **Mechanical replay** (implemented): deterministic host execution, used to
   prove pattern semantics without a live Jev.
2. **Agent-guided** (later): known-pattern context is exposed read-only in the
   Jev scene as `known_patterns`. Jev still selects from the current finite
   legal choices; memory may inform the choice but cannot manufacture one.

`known_patterns` carries bounded declarative entries only — id, label, step
count and typed fragments. It contains no StickerInstance id and no complete
action key, so nothing in it can be submitted to the kernel, and it never adds
a key to the legal table. Pattern memory is not a second decision engine.

### "Remember that" and "Do that again"

Teaching is a conversation, not a programming interface. There is no record
button and no macro editor; the child says what they mean.

```text
child:  "Remember that as your happy dance."
            |
            v
OmegaLLM    interprets: this is a remember request,
            "that" is about Froggy, the name is "happy dance"
            |
            v
host        resolves "that" from ITS OWN record of what actually happened,
            and stores typed fragments in the PatternLibrary
```

```text
child:  "Froggy, do your happy dance."
            |
            v
OmegaLLM    semantic goal: perform known pattern "happy dance" on Froggy
            |
            v
host        resolves the bounded pattern reference
            |
            v
OmegaJev    fresh state + CURRENT finite legal choices + pattern context
            -> selects one offered key, per step
            |
            v
kernel      accepts or refuses each mutation, one receipt at a time
```

OmegaLLM emits `remember-pattern` or `perform-pattern` with a `subject` and a
`label`. It never emits movement, keys or `PatternStep`s. If it tries to
attach anything else, host validation refuses the goal with
`unknown-jev-goal-field`.

#### Governed history gives "that" a safe meaning

`web/governed_history.py` keeps a bounded, host-owned record of governed
actions that really happened: subject, actor, kernel action, accepted or
refused, revision, and which path the input came from (human gesture,
OmegaLLM to OmegaJev, direct gesture to OmegaJev, mechanical replay, pattern
performance). OmegaLLM receives a bounded declarative projection of it as
`recent_actions` and may refer to it. Only the host writes it, and only from
real kernel receipts:

> The host remembers what happened. OmegaLLM interprets the child's reference
> to it. OmegaLLM does not get to rewrite history.

An entry carries a legal-action key only when the action was selected from the
host-owned table. A freehand drag is a real governed mutation and is recorded
for audit, but an arbitrary coordinate has no instance-independent typed form,
so it can never become a learned `PatternStep`. Refused actions stay visible
for audit and are never learnable.

#### The episode rule: what "that" resolves to

OmegaLLM names the subject and the label. It does **not** choose the
historical slice. The host resolves "that" to one deterministic, bounded
episode:

> the latest **contiguous learnable accepted** run of actions for the named
> subject, ending before the remember request.

It is a contiguous run scanned backwards, not a filter, so nothing is silently
reached across. An episode ends at the first of:

| Boundary | Why |
|---|---|
| a switch to another subject | the child's attention moved to a different sticker |
| a non-learnable action on this subject | a refused proposal, a freehand drag with no typed form, or an accepted action outside the remembered verb families, such as a removal |
| the pattern-length limit | memory is bounded; the most recent steps win |
| the edge of the bounded history window | history is bounded |

Every boundary is already observable in the host record. None requires model
judgement, and none is decided by OmegaLLM. So:

```text
frog   MOVE STEP-E
frog   MOVE STEP-N
bird   MOVE STEP-W        <- subject switch ends the frog episode
frog   ANIMATE hop
child: "Remember that as happy dance"
```

"that" is unambiguously `[ANIMATE/hop]`. The two earlier frog moves belong to
an earlier episode.

One deliberate non-boundary: a previous remember does **not** end an episode.
Naming the same run twice is harmless, and tracking it would need host state
that is not already in the record.

#### Replay is non-atomic, and says so

A remembered pattern is a sequence of fresh governed actions, not a
transaction. If step 1 is accepted and step 2 is no longer legal, step 1
remains applied and the replay stops. There is no rollback and no compensating
mutation, because inventing one would be a privilege the child never had.

Every attempt produces a host-side `PatternReplayRecord`: replay id, pattern
id and label, subject, initiating principal, starting revision, mode, and the
ordered attempted steps with each ordinary kernel receipt or, for a step that
could not be submitted, its `unavailableReason`.

Three counts are kept separate, because they answer different questions:

| Field | Meaning |
|---|---|
| `plannedSteps` | steps in the resolved pattern; never varies with what happened |
| `submittedSteps` | steps actually submitted to the kernel |
| `acceptedSteps` | steps that produced an accepted kernel receipt |
| `result` | `completed`, `partial` or `stopped` |
| `stoppedAt` | 1-based pattern step where execution stopped |
| `stoppedReason` | why |

A two-step pattern whose second step is no longer offered records:

```text
plannedSteps:   2
submittedSteps: 1
acceptedSteps:  1
result:         partial
stoppedAt:      2
stoppedReason:  pattern-step-unavailable
```

`stoppedReason` distinguishes two different pieces of evidence.
`pattern-step-unavailable` means the current world never offered the
remembered form. `jev-noop` means it *was* offered and OmegaJev declined it.

That record observes and groups authority events. It does not possess
authority, and the kernel never learns what a "happy dance" is: its receipts
stay ordinary mutation receipts.

#### Two modes, one set of semantics

- **agent** (`perform_known_pattern`): OmegaJev chooses each step from the
  current table, informed by bounded pattern context. This is the powered
  path.
- **mechanical** (`replay_pattern`): the host drives the steps itself. A
  deterministic reference path that proves representation, rebinding, fresh
  legality, kernel authority and partial behaviour without live inference,
  while the OpenShell-hosted loops are blocked.

Both use the same `PatternStep` representation and the same current
legal-action table, and both produce the same record type. `PatternLibrary` is
memory, not a decision engine: it never replaces OmegaJev and never adds an
action to `available_actions`.

#### Patterns transfer; authority does not

A pattern applies to a StickerDefinition, not to ownership of the frog that
first demonstrated it. A child may teach one frog and ask another compatible
frog to perform it. Provenance records who taught it, which instance
demonstrated it and at which revision. Ownership, budgets and every other
principal restriction are still applied independently to each actual action by
the kernel.

### Sticker-drag traces

> **Input history is not world history.**
> **Failure to observe must not become failure to act.**

**Scope first.** This is ONE input type, not StickerBook's gesture ontology.
It is specifically *the observed trajectory of a child dragging a sticker that
is already on the page*, which is why the record structurally requires a
subject and an asset. It is named `StickerDragTrace`, with
`kind = "sticker-drag"`, rather than anything suggesting freehand gesture in
general.

A child drags a sticker. The browser watches a whole trajectory and the
renderer follows it, but on pointer-up only the release point is proposed, and
the kernel authorizes exactly one ordinary `MOVE_STICKER`. Without this the
host remembers only "the sticker ended over there".

#### Three classes of evidence

A retained trace is deliberately mixed, and the mixture is labelled:

| Position | Class | Source |
|---|---|---|
| first sample | **authoritative start** | `TrajectorySample(t=0, dx=0, dy=0)`, bound by the host from the StickerInstance position read *before* the move was proposed |
| interior samples | **observed input** | what the browser reported, validated and decimated. Never a world mutation, never a kernel receipt |
| last sample | **authoritative terminal point** | bound by the host from the StickerInstance position *after* the kernel accepted |

Both anchors are host-derived. The browser's own first and last samples are
not trusted to coincide with them: observed samples at the extremes of
progress (`t <= 0` or `t >= 1`) are dropped precisely because the host binds
those positions itself. So a modified or stale browser cannot produce a trace
whose path claims an origin or destination different from the move the kernel
actually accepted.

`dx`/`dy` are displacement from the authoritative start, not absolute
coordinates, so the same demonstrated shape can later be read against another
sticker starting somewhere else. `t` is monotonic progress; `duration_ms` is
kept separately so speed survives normalising progress.

#### Observation is auxiliary, never a veto

Drag telemetry is auxiliary observation, not authority. If it is malformed,
oversized, badly ordered or otherwise unusable, the observation is **discarded
and never attached to history** -- but the child's move is still adjudicated
by the kernel exactly as before. A sticker does not snap back because
telemetry failed. The response says `dragIgnored` with the reason.

A malformed *move* is still a bad request, and a move the kernel refuses is
still refused. Only the auxiliary observation is tolerant.

#### Bounding, sampling and transport

| Limit | Value |
|---|---|
| retained samples per trace (incl. both anchors) | 32 |
| raw samples accepted per request | 192 |
| browser retention before reduction | 64 |
| drag duration | 20000 ms |
| retained traces | 32 |
| transport ceiling (`MAX_BODY_BYTES`) | 8192 bytes |

The sample cap is chosen to fit the transport: a worst-case legal payload at
192 samples is about 6.6 KB, leaving roughly 1.5 KB of headroom, and the
browser's own 64-sample retention is about 2.3 KB. Progress is rounded to 3
decimal places and coordinates to 4 before transmission -- input compression,
not semantic interpretation.

Both the browser and the host reduce by the same principle: repeatedly drop
the interior point whose removal changes the path least, measured as
perpendicular distance from the line between its neighbours. That keeps the
first point, the last point, the ordering and the major bends, and it observes
the whole gesture. Dropping every other point by index would keep temporal
coverage but could destroy a brief sharp bend or hook before the host's
geometry-aware pass ever saw it -- and once the browser discards that, the
host cannot recover it.

Points are only ever removed, never invented or moved, except for the two
host-bound authoritative anchors. No smoothing, no easing, no curve fitting,
no classification, no inference. We are preserving evidence, not beautifying
it.

#### Honest linkage to governed history

`GovernedHistory` gains `gestureTrace` and `gestureKind` on the one accepted
move, associating a single governed mutation with the demonstration the host
observed. It does not pretend the samples were governed mutations, and
OmegaLLM's projection names the demonstration without receiving the samples.

#### Bounded multimodal interaction record

StickerBook is voice-interface-forward, and a sticker drag is only the first
class of gestural input. Child direction will eventually include pointing,
boxing or circling a region, drawing a path through empty page space, speech
and gesture together, a gesture followed by "do that", and directing one
sticker along a path demonstrated without touching it. The page already has
point/box deictic interaction for OmegaLLM, whose semantics are unchanged
here.

The host records one `InteractionEpisode` per OmegaLLM turn. It contains
the utterance/transcript, optional validated point or box, scene revision,
browser-observed voice/text mode, and at most four host-observed input
references. The client cannot select historical trace IDs. A bounded host
ledger sequences accepted sticker drags and bare-page paths together by host
arrival, then associates the newest four observations since the preceding
linguistic turn. If the marker has left the ledger, retained entries still
carry monotonic sequences, so the same rule applies. The cursor advances even
when inference fails. A failed turn remains in the 24-episode log;
later OmegaLLM turns currently receive only their own episode, so an immediate
retry does not automatically receive the earlier drag. This is input history,
not world history: recording an episode creates no receipt or world revision.

`InputSignal` carries `sticker-drag` or `page-path` summaries. The episode does
not classify geometry or infer relevance. Bounded, validated trajectory samples
remain in the host's `StickerDragLog` or `PagePathLog`; the untouched browser
event stream is not stored. A bare-page drag also retains its existing box
deictic mark: box and path are distinct evidence from one physical input.
Every page-path sample is an observed normalized pointer position, with no
authoritative world anchor and no kernel mutation. Malformed auxiliary path
telemetry is discarded without invalidating the box. The voice/text
mode comes from the browser's physical input channel and is descriptive
metadata only; nothing security-relevant branches on it. No microphone audio
is stored.

The auxiliary observation request carries both the existing box and bounded
path samples from one browser pointer gesture. The host validates their end
corners together and, on success, issues an `input-event-N` token from its
observation sequence. The browser attaches that response only to the box still
pending from the same local pointer gesture. At conversation time,
the host exposes `sourceEvent` on the box only when the token names the latest
eligible page path in the current bounded episode window and the box matches
the pair stored at capture within coordinate rounding.
The page-path signal carries the same host-issued token. A stale, fabricated,
or mismatched claim leaves the validated box intact but unlinked. This checks
the reported correlation; the browser remains the physical input sensor, so
the host cannot independently attest pointer hardware provenance. The token
does not change host arrival chronology or imply what the gesture meant.

#### Provider pattern-intent contract

The real OmegaLLM provider also supports the existing `remember-pattern` and
`perform-pattern` goals. Pattern goals carry only subject, intent, label, and/or
pattern id; remember requires label and perform requires label or id. Labels
are 1..48 trimmed characters, without colon, CR, LF, or tab, and whitespace is
canonicalized as in host memory. Pattern ids are nonempty strings of at most
64 characters without colons. The host resolves memory/history and remains
the final validator. No PatternSteps, action keys, or trajectory samples may
enter these provider goals. This does not enable continuous movement learning.

#### Bounded demonstration binding

OmegaLLM may select one current page-path event with a semantic goal containing
exactly `subject`, `intent: "bind-demonstration"`, and the opaque host-issued
`demonstration: "input-event-N"`. The provider checks the current episode's
page-path signals; the host independently checks the same current episode,
retained path principal/page, and subject. Unrelated old, fabricated, malformed, or
unsupported references fail closed. The host does not select the latest path
or infer meaning from the box. A valid binding reports the selected event and
path reference without calling OmegaJev, changing memory or world state, or
creating a kernel receipt. Retained trajectory samples stay host-side; no
geometry or motor program enters the semantic goal. The legacy HTTP `jev`
result key also holds this host-side semantic result for compatibility.

#### Bounded semantic reference carry

After successful host admission, one `PendingSemanticReference` records
subject, demonstration event, path ref, original source episode, principal,
and page. Its `scene.pendingReference` projection additionally states
`kind: "page-path"`. This is discourse context; `scene.interaction` still
contains only the current turn's input evidence. The provider and host may
admit a current supported page-path event OR exactly the exposed pending
subject/event pair. The client cannot author this slot or its provenance.

One subsequent valid linguistic response consumes it, even if a returned
goal is refused. A successful binding replaces it; rebinding the pending
event renews the slot while preserving its original source episode and other
provenance. Runtime/provider errors and invalid response envelopes preserve
the carry. The new input episode remains recorded and the input cursor still
advances independently. Direct gestures do not consume it. Linguistic turns
are serialized to make this one-turn rule deterministic under concurrency.

There is no host recognition of clarification/cancellation language, no
transcript memory, and no historical episode search. The slot holds no path
samples and does not pin retained geometry against eviction. It adds no
kernel action, receipt, revision, memory pattern, frame, or execution path.

The architecture is unchanged by any of that:

#### Non-executing trajectory references

OmegaLLM may emit exactly:

```json
{"subject":"bird-1","intent":"reference-trajectory","demonstration":"input-event-2","frame":"subject"}
```

`frame` is required and is either `page` or `subject`. No extra fields are
accepted. `bind-demonstration` still identifies evidence only and rejects
frame. Both provider and host admit current page-path evidence or exactly the
exposed pending subject/event pair. The subject must be visible on the current
kernel page. No sticker-drag trajectory references are supported.

Page frame uses q_i = p_i, with no segment from the subject to the path start.
Subject frame uses q_i = s + (p_i - p_0): translation from the first retained
observed point onto the subject's position at resolution, in page axes/units.
Facing and sticker scale do not affect this formula. No rounding, smoothing,
resampling, rotation, reversal, clipping, or clamping is applied. Source times
and duration remain evidence, not a replay schedule; equal times and retained
endpoints other than t=0/1 are preserved.

The frozen host-only `ResolvedTrajectoryReference` fields are `subject`,
`demonstration`, `path_ref`, `frame`, `principal`, `page`, `source_episode`,
`source_start`, `subject_start`, `source_samples`, `resolved_samples`,
`observed_duration_ms`, `source_scene_revision`, and `resolution_scene_revision`.
Points and samples are frozen dataclasses; arrays are tuples of copied retained
observations or derived samples. The source revision is the path's recording
revision; the resolution revision and subject position come from one coherent
host snapshot after inference. That snapshot, the multi-object kernel reads a
choice is made against, and every bridge-reachable kernel mutation
(`propose`, `propose_key`, `begin_turn`) are serialized on one host world
lock. The lock is held only for the world operation: no OmegaLLM or OmegaJev
inference, and no runtime availability probe, ever runs inside it, so model
latency cannot queue a child's own gesture. A bare `kernel.sticker()` lookup
is exempt, returning a frozen instance that cannot be observed half-applied.
Host serialization only orders concurrent work; `based_on_revision` remains
the kernel's own staleness adjudication and is not replaced by it.
Later moves and source-log eviction do not change an already-resolved object.

The bridge keeps one last successful reference for host inspection. Its result
under the legacy `jev` key is `resolved`, with subject, event, path ref, frame,
and a bounded reference summary (starts, count, provenance, duration, revisions).
Sample arrays remain host-side; no resolved geometry enters OmegaLLM scenes.
No neutral result-envelope migration is needed by current consumers.

Pending use consumes carry without renewal. The host dereferences only the
already-admitted path ID, without searching prior episodes. If geometry was
evicted before resolution, it fails with `trajectory-evidence-unavailable`;
no recency fallback occurs. No Jev call, kernel proposal/receipt, world revision,
legal action, or movement memory is created by RESOLVING a reference. Executing
one is a separate host path, described next, that no child-facing intent
reaches yet.

#### Following a demonstrated trajectory

`JevController.follow_trajectory()` is the **mechanical trajectory follower**:
the same relationship to a resolved trajectory that `replay_pattern()` has to a
remembered pattern, a deterministic host path that proves the control loop
without a live chooser. It accepts only an already-resolved `frame: "subject"`
reference. Page-frame references stay valid non-executing data.

```text
ResolvedTrajectoryReference  (frozen observation)
    -> host derives the CURRENT local objective
    -> host builds the CURRENT move_only legal surface
    -> a selector picks one CURRENT legal move
    -> kernel adjudicates an ordinary proposal
    -> fresh world state, and repeat
```

Nothing is precompiled into keys, so a trajectory confers no more power than
being allowed to propose one ordinary move at a time. Progress is a monotonic
index that walks forward past consecutive points already within one
`MOVE_STEP`, and the objective is the first point beyond that. It is never a
nearest-point search: in an out-and-return path the first and last retained
points can be the same coordinate, and a nearest-point rule could call the
whole excursion finished before it began.

Completion, unreachability and the step budget are all host bookkeeping,
determined before the selector is consulted, so none of them can be confused
with a selector declining. The step budget is
`min(48, ceil(1.25 * arc_length / MOVE_STEP))` motor steps; exhaustion is
reported as `partial`, never `completed`. Observed timing stays evidence on the
reference and is not used to schedule anything.

Direct human manipulation of the subject supersedes an attempt, since the child
is the higher-authority actor. That label requires evidence: an accepted
`human-gesture` record for this same subject, newer than the motor snapshot. A
`stale-revision` refusal without it stops neutrally as `world-changed`, because
the same subject can be moved by other controller paths and attributing that to
the child would be fabricated provenance.

`follow_trajectory(..., select=...)` is the seam a powered follower replaces.
The selector receives a bounded declarative snapshot — current position,
progress index, objective, local error vector, the next one or two retained
points, and the honest current action table including `NOOP` — and returns one
offered key. Only real moves carry destinations, so only they compete on
distance. No sample array and no path history is handed over.

```text
child voice/gesture -> OmegaLLM -> bounded semantic goal
                    -> OmegaJev -> current finite legal choices
                    -> kernel
```

OmegaLLM interprets multimodal child direction. OmegaJev remains the bounded
chooser. The kernel remains the authority.

#### Deliberately not yet

A sticker drag is still **not** learnable by the discrete `PatternStep`
mechanism, and "remember that" still resolves only over typed discrete
actions. Collapsing a continuous demonstration into compass steps would
quantise a semantic the child never supplied. A drawn path can now be FOLLOWED
mechanically, but it still cannot be REMEMBERED as continuous movement, and no
child-facing intent asks for it to be followed. How OmegaJev consumes a
trajectory, and how continuous demonstrated movement becomes memory without
false quantisation, are the next decisions.

### Not yet

No persistence across restart, no sharing between children, no Jev-authored or
OmegaLLM-authored patterns, no model-generated executable animation, no
rollback transactions, and no child-facing programming interface. Visual
animation packages remain data and assets, never generated code.

## Runtime attachment

`web/agent_runtime.py` and `web/jev_runtime.py` still default to inert
`Disabled*` adapters and perform no network access unless explicit loopback
runtime URLs are supplied.

The powered launcher attaches:

- OmegaLLM at host loopback port 8761;
- OmegaJev at host loopback port 8762.

Both adapters reject non-loopback URLs. Neither receives the kernel object or a
provider credential.

OpenShell is the containment substrate for those two powered Omega loops, not a
replacement for the StickerBook kernel. They use separate sandboxes, policies,
and provider identities. The dual-Omega OpenShell path is implemented and
mechanically checked, but is not labeled live-host verified until exercised on
the actual WSL2/Docker Desktop/provider host.

GitHub Pages receives neither Python runtime and remains the mechanical static
profile.

The page-image gateway is intentionally **not** an Omega capability. It is a
narrow media transformer started by the operator, and successful image
generation does not imply any permission to save, install, publish, or mutate
a StickerBook world.
