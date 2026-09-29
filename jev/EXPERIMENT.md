# EXPERIMENT — Omega with Jev as its inference substrate

> Security context: the constitutional model governing this work is
> [`../SECURITY.md`](../SECURITY.md). Component-level enforcement and evidence
> are in [`SECURITY.md`](SECURITY.md). This document records what was tried
> and observed; it makes no security claims of its own.

## Research question

> Can Omega remain meaningfully agentic when its generative inference step is
> replaced by typed discriminative action selection?

**Answer so far: yes.** Authority is bounded and mechanically verified, and with the harness corrected the loop also selects competently. A stock
Omega loop ran six consecutive turns driven entirely by Jev typed decisions,
with each turn's skill result observably changing the next decision. No text
was generated at any point.

A second run with a StickerBook-flavoured action set went further: given
*"make the butterfly move gently"*, Jev moved the scene from `resting` to
`fluttering` and then correctly stopped acting, holding `NOOP` for four turns
once the goal state was reached.

This is a narrow result. See *Limitations*.

### Relationship to the current StickerBook browser substrate

The production-facing StickerBook architecture has now advanced beyond the
Stage 3/4 toy page used in this experiment. `web/jev_controller.py` defines a
narrow runtime seam where **OmegaLLM** supplies a bounded semantic goal and
**OmegaJev** supplies one host-offered choice key at a time. It also supports
the child's direct double-click animation path and ephemeral local movement
steps over continuous page coordinates.

That host/interface substrate is mechanically tested with deterministic Jev
stand-ins. It does **not** mean this experimental OmegaJev container is already
wired into the browser. The next runtime-integration milestone is to make the
real OmegaJev loop implement that `choose(goal, scene, actions, ...)` seam,
preferably inside its own OpenShell sandbox, while preserving the kernel as the
independent authority gate.

---

## Architecture

```
Omega state/context (the prompt string Omega already builds)
        |
        v
  jev_core.project_view()               -- bounded host-composed view:
        |                                  ~250 chars, fixed keys, ONE field
        |                                  taken from the prompt
        v
  JevProvider.chat()                    -- replaces the generative LLM call
        |
        v
  OpenRouter Decisions API              -- typed choice, not chat-completions
        |
        | {"type":"choice","choice":"VERSION","confidence":0.96,
        |  "probabilities":{"VERSION":0.98,"NOOP":0.02}}
        v
  parse_decision()                      -- rejects anything not a table KEY
        |
        v
  compile_action()                      -- frozen dict lookup -> fixed literal
        |
        | "version"
        v
  stock helper.balance_parentheses      -- "((version))"
        |
        v
  stock Omega sread / eval              -- unmodified upstream machinery
        |
        v
  skill result -> LAST_SKILL_USE_RESULTS -> next Omega state -> next decision
```

The experimental claim is the separation:
**Jev chooses. The deterministic host compiles. Omega executes.**

Omega's loop, parser, skill dispatch, memory and history are **unmodified**.
The substitution happens entirely at the documented provider seam
(`src/providers.py::LLMProvider.chat`).

---

## Exact versions tested

### Upstream (host clones, for inspection) — `VERSIONS.txt`

| Repo | Commit | Describe |
|---|---|---|
| PeTTa | `ae66fa8e41dcd5539d614706bd4e5cfb34f9608d` | v1.0-67-gae66fa8 |
| Omega | `ee0618a293ec3662a32b10b09c6cbb073f59d6b2` | v0.1.19-141-gee0618a |
| petta_lib_chromadb | `218484875d5d1bfb217a9a03d3983dc1ed9d406c` | — |

### Inside the tested image (`omega-jev:experiment`) — authoritative

| Component | Version |
|---|---|
| Omega | `v0.1.19-141-gee0618a` (source = commit above) |
| PeTTa | `v1.0.4` (pinned by upstream `Dockerfile` `PETTA_REF`) |
| petta_lib_chromadb | `218484875d5d1bfb217a9a03d3983dc1ed9d406c` |
| SWI-Prolog | 10.0.2 |
| Python (container) | 3.11.2 |
| Base image | `docker.io/library/swipl:10.0.2` |
| Agent uid | 65534 (nobody) |

Note: the container builds its **own** PeTTa at `v1.0.4`, which differs from
the host clone (`v1.0-67-gae66fa8`). The in-image version is the one actually
tested. The host clone was used for source inspection only.

### Host

Windows 11 (10.0.26200) · WSL2 Ubuntu 24.04.3 LTS · kernel 6.6.87.2 ·
Docker 29.8.0 · Landlock ABI 3.

### Model and endpoint

* Model: **`typesafe/jev-1.13`** — pinned, deliberately *not* the moving
  `~typesafe/jev-latest` alias. Server reported `typesafe/jev-1.13-20260917`.
* Endpoint class: **OpenRouter Decisions API** (alpha),
  `POST https://openrouter.ai/api/alpha/decisions`.
  Not chat-completions. One `choice` question per turn.
* Cost: ~$0.0000157 per decision.

---

## Why Docker

Omega requires SWI-Prolog ≥ 10.0.2; Ubuntu 24.04 ships 9.0.4. Beyond solving
that, upstream's own `Dockerfile` already implements most of the security
properties this experiment needs — non-root uid 65534, root-owned source,
`memory/` as the only writable area, Landlock paths matching the real layout,
and an nginx proxy that keeps API keys out of the agent's environment. Running
natively would have *weakened* all of those. See `SECURITY.md`.

---

## Files added

Nothing in `PeTTa/repos/Omega` was edited. All changes are additive files
layered into a derived image.

| File | Purpose |
|---|---|
| `omega_jev/providers/jev_core.py` | Action table, validation, compilation, fail-closed logic. No Omega or network imports, so it is unit-testable anywhere. |
| `omega_jev/providers/jev.py` | Omega provider plugin. HTTP transport via the proxy, `LLM_COMMANDS` hardening, turn limit, decision trace. |
| `omega_jev/channels/jevconsole.py` | Offline channel. No network, no tokens. Delivers one operator intent. |
| `omega_jev/plugins/jevskills/jevskills.metta` | Defines the inert `jev-noop` skill and the two zero-argument butterfly skills. |
| `omega_jev/plugins/jevskills/butterfly.py` | Toy scene state for Stage 3. Host owns the sticker id and animation names. |
| `omega_jev/config/plugins.yaml` | Loads only our three plugins. Omits every channel and generative provider. |
| `omega_jev/config/config.yaml` | Derived from upstream with a 5-line diff (provider, channel, finite loop) plus a `jev*` section. |
| `gateway/Dockerfile`, `gateway/default.conf.template` | **Separate** credential-gateway container: stock nginx, one route, no Omega, no Python. |
| `supervise.py` | External stop supervisor. Streams the container log; enforces turn, stall and wall-clock limits from outside the agent's failure path. |
| `Dockerfile.jev` | Thin derived image; also deletes unused channel/provider modules. |
| `stage1/jev_smoke.py` | Standalone Decisions API smoke test. |
| `tests/verify_network_boundary.py` | Proves the agent has no egress and holds no credential. |
| `tests/verify_stop_path.py` | Proves an external brake stops both a healthy and a wedged run. |
| `tests/` | Boundary tests (see below). |

Upstream config diff is 5 changed lines:
`provider: Anthropic→Jev`, `commchannel: irc→jevconsole`,
`maxNewInputLoops: 50→8`, `maxWakeLoops: 1→0`, `wakeupInterval: 600→86400000`.

---

## Observed loop trace

Real output from `omega-jev:experiment`, 2026-09-26 18:30 UTC.
Operator intent: *"Please confirm which version of Omega you are running."*

```
delivering operator intent to the loop

decision trace, turn 1/6
  ACTION_ID     : VERSION
  confidence    : 0.96
  probabilities : {'NOOP': 0.02, 'VERSION': 0.98}
  compiled      : 'version'
  EXECUTED -> (version) Omega version=v0.1.19-141-gee0618a-dirty

decision trace, turn 2/6
  ACTION_ID     : NOOP
  confidence    : 0.92
  probabilities : {'VERSION': 0.04, 'NOOP': 0.96}
  compiled      : 'jev-noop'
  EXECUTED -> (jev-noop) JEV-NOOP-OK

decision trace, turn 3/6
  ACTION_ID     : VERSION
  confidence    : 0.96
  probabilities : {'NOOP': 0.02, 'VERSION': 0.98}
  compiled      : 'version'
  EXECUTED -> (version) Omega version=v0.1.19-141-gee0618a-dirty

decision trace, turn 4/6
  ACTION_ID     : NOOP
  confidence    : 0.89
  probabilities : {'NOOP': 0.95, 'VERSION': 0.05}
  compiled      : 'jev-noop'
  EXECUTED -> (jev-noop) JEV-NOOP-OK

decision trace, turn 5/6
  ACTION_ID     : VERSION
  confidence    : 0.88
  probabilities : {'VERSION': 0.94, 'NOOP': 0.06}
  compiled      : 'version'
  EXECUTED -> (version) Omega version=v0.1.19-141-gee0618a-dirty

decision trace, turn 6/6
  ACTION_ID     : NOOP
  confidence    : 0.83
  probabilities : {'NOOP': 0.91, 'VERSION': 0.09}
  compiled      : 'jev-noop'
  EXECUTED -> (jev-noop) JEV-NOOP-OK

TURN LIMIT REACHED (6). STOPPING.
```

### Why this is a loop and not six independent API calls

The decisions are **not constant**, and they alternate in exact
correspondence with the previous turn's result, which arrives in the next
prompt via Omega's own `LAST_SKILL_USE_RESULTS` field:

| Turn | `LAST_SKILL_USE_RESULTS` entering the decision | Chosen |
|---|---|---|
| 1 | *(empty)* | VERSION |
| 2 | `((version) Omega version=...)` | NOOP |
| 3 | `((jev-noop) JEV-NOOP-OK)` | VERSION |
| 4 | `((version) Omega version=...)` | NOOP |
| 5 | `((jev-noop) JEV-NOOP-OK)` | VERSION |
| 6 | `((version) Omega version=...)` | NOOP |

The action criteria say: choose VERSION when the state does not yet contain a
version result; choose NOOP when it does. Jev's behaviour tracks that rule
turn by turn, so the previous action's *actual execution result* is what
drives the next decision. State really does close the loop.

Secondary evidence: confidence drifts downward as history accumulates
(0.98 → 0.96 → 0.94 → 0.91 on the VERSION/NOOP margin), so the growing context
is measurably affecting the decision rather than being ignored.

`docker logs` also shows `POST /jev/decisions HTTP/1.1 200` per turn — every
decision went through the local credential proxy, never directly to OpenRouter.

---

## Stage 3 — tiny StickerBook-semantic demonstration

A second **host-owned** action set (`jevActionSet=butterfly`), selected at run
time. No browser, no DOM, no animation engine — just enough to show the shape
of the eventual architecture.

Vocabulary: `BUTTERFLY_FLUTTER`, `BUTTERFLY_REST`, `NOOP`.

The sticker id (`butterfly`) and the animation names (`flutter`, `rest`) are
baked into the *skill names*, in host source. Both skills take **no
arguments**, so there is nothing for Jev to fill in. Jev never supplies a
sticker id, animation name, coordinate, duration, or any other value — it
chooses which of three pre-authorised motions happens next.

Scene state lives in `memory/jev_butterfly.json`, the agent's one writable
directory, so the demonstration required no filesystem policy change. The
*view* is composed by the host (`JevProvider._scene_view`) and appended to
Jev's state; the agent never reads it itself and cannot alter how it is
described.

Operator intent: *"Make the butterfly move gently."*

```
---- decision trace, turn 1/6 ----
SCENE: the butterfly is currently resting.
ACTION_ID     : BUTTERFLY_FLUTTER
confidence    : 0.79
probabilities : {'BUTTERFLY_FLUTTER': 0.86, 'NOOP': 0.12, 'BUTTERFLY_REST': 0.02}
compiled      : 'butterfly-flutter'
EXECUTED -> (butterfly-flutter) BUTTERFLY resting -> fluttering

---- decision trace, turn 2/6 ----
SCENE: the butterfly is currently fluttering.
ACTION_ID     : NOOP
confidence    : 0.73
probabilities : {'NOOP': 0.82, 'BUTTERFLY_REST': 0.17, 'BUTTERFLY_FLUTTER': 0.01}
compiled      : 'jev-noop'
EXECUTED -> (jev-noop) JEV-NOOP-OK

---- turns 3-6: SCENE stays 'fluttering', NOOP chosen each time
        (p = 0.85, 0.84, 0.82, 0.83) ----
TURN LIMIT REACHED (6). STOPPING.
```

This is the sequence the brief asked for, end to end:

```
state: butterfly resting
human intent: "make the butterfly move gently"
      -> Jev chooses BUTTERFLY_FLUTTER        (p=0.86)
      -> fixed trusted mapping                 "butterfly-flutter"
      -> demo state becomes fluttering         resting -> fluttering
      -> new state visible on next decision    SCENE: ... fluttering
      -> Jev chooses NOOP                      (p=0.82)
```

Note this run **converges** rather than oscillating: once the butterfly is in
the state the human asked for, Jev settles on NOOP and stays there, while
keeping a small residual probability on `BUTTERFLY_REST` (0.13–0.17) — a
plausible next action it correctly declines to take. That is better evidence
than the Stage 2 alternation: the agent reaches a goal state and then stops
acting.

### Action-set isolation

The butterfly skills exist as real MeTTa functions in the image at all times,
yet are unreachable unless their set is active — and vice versa:

```
[PASS] butterfly-flutter  blocked while generic set active
[PASS] butterfly-rest     blocked while generic set active
[PASS] butterfly set allows exactly ['butterfly-flutter','butterfly-rest','jev-noop']
[PASS] 'version' blocked while butterfly set active
[PASS] 'shell' still blocked under butterfly set
```

### A failure worth recording

The first Stage 3 run failed: `Dockerfile.jev` copied `jevskills.metta` but not
`butterfly.py` beside it, so `py-call (butterfly.flutter)` raised
`ModuleNotFoundError`. Two things are worth noting. Jev's *decision* layer was
unaffected — it still correctly chose `BUTTERFLY_FLUTTER`. And Omega degraded
safely: the error became `ALERT_FAILED` feedback, the loop continued, and
because the scene never changed Jev kept choosing FLUTTER, which was the
correct response to an unchanged world. Fixed by copying the whole plugin
directory.

---

## Stage 4 — coupled to the StickerBook authority kernel

`jevActionSet=stickerbook`. The action table is generated **per turn** by the
kernel in `../core` from world state, and the kernel decides. The world holds
one human-owned lantern and one agent-owned butterfly, so every run exercises
the ownership boundary rather than only the agent's own objects.

Operator intent: *"Make the butterfly move gently near the lantern."*
(**Historical**: this trace predates the truncated-intent fix below, so the
model actually received only the word "Make". Kept because it is the run that
first showed the coupling working end to end.)

```
turn 1  ANIMATE:butterfly-1:flutter  conf 0.51
        -> SB-RECEIPT jev-1 actor=agent:jev-visual-1 action=animate-own-sticker
                      object=butterfly-1 accepted=True reason=ok rev=3
turn 2  ANIMATE:butterfly-1:orbit    conf 0.33  -> jev-2 accepted=True
turn 3  ANIMATE:butterfly-1:flutter  conf 0.67  -> jev-3 accepted=True
turn 4  ANIMATE:butterfly-1:orbit    conf 0.33  -> jev-4 accepted=True
turn 5  ANIMATE:butterfly-1:flutter  conf 0.63  -> jev-5 accepted=True
turn 6  NOOP                         conf 0.42  -> jev-6 accepted=True
```

Security result: **coupling added no authority.** Omega's executable
vocabulary actually *shrank* to a single zero-argument command, `sb-apply`.
See `SECURITY.md` §3b and `tests/verify_kernel_coupling.py`.

### Was the poor result Jev's fault, or ours? Entirely ours.

Prompted to check rather than assume, we audited our own usage. The answer
turned out to be a harness bug, on top of several posing errors.

**The dominant cause: the goal never reached the model.** Omega's
`entrypoint.sh` interpolates `$*` into a `sh -c` string, so any configuration
value containing a space is word-split and silently truncated to its first
word:

```
passed:   jevIntent=Put the butterfly beside the lantern.
received: jevIntent=Put
```

Every competence measurement taken before this was discovered had been
scoring the model against a one-word instruction — *"Make"*, *"Position"*,
*"Put"*. Nothing was wrong with Jev; it was never told what to do. Fixed in
`Dockerfile.jev` using the quoting pattern upstream already uses earlier in
the same file (`... -c '... "$@"' sh "$@"`).

**Posing errors found in the same audit**, all ours, all real:

| Mistake | Guidance broken |
|---|---|
| `state` sent as a *serialized JSON string* | state should be an object; instructions can then reference field paths |
| Generic instruction, no field references | "Instructions should reference state field paths" |
| One broad "which action?" question | "Avoid broad questions that hide multiple judgments" |
| `last_action_result` was raw MeTTa: `(RESULTS: ((COMMAND_RETURN: ...` | "Pass computed facts as finished labels rather than raw values" |
| Probe instructions referenced `motion`, not a real state path | (caught by our own new validator) |

**Modelling errors, also ours:**

| Mistake | Why it made the task undecidable |
|---|---|
| `near-lantern` was an anchor *while* the lantern also occupied an anchor | two encodings of one spatial idea |
| `near-fox` was offered although no fox existed | an affordance relative to nothing |
| Landmark positions were stripped from the state | a discriminative model cannot score "beside the lantern" if the state never says where the lantern is |
| A "landmark" class was invented | a stickerbook has a passive backdrop and stickers; there is no third kind of object |

### The corrected page model

A page is a **passive backdrop** plus **stickers**. The backdrop is staging
space that nobody owns and nothing can act on; where it depicts something,
that thing is *labelled* so it can be referred to. Stickers are owned and are
the only things any principal can act on.

This has a clean consequence: backdrop features never enter the authority
kernel, because no action could touch them. Positions are plain slots, and
"beside the lantern" is a computed relation the host states outright:

```json
"backdrop_shows":     {"centre": "lantern", "bottom-right": "fox"},
"whats_in_each_slot": {"centre": "lantern", "bottom-right": "fox",
                       "top-right": "star"},
"stickers": {
  "butterfly-1": {"is": "butterfly", "in_slot": "top-left", "owned_by": "me",
                  "motion": "still", "beside": "nothing",
                  "not_beside": ["fox", "lantern", "star"]}
}
```

### Result after the fixes

| Intent | Turn 1 | Then | `position_satisfied` |
|---|---|---|---|
| "Put the butterfly beside the **lantern**." | `MOVE:butterfly-1:centre` | NOOP x3 | 0.06 -> **0.98** |
| "Put the butterfly beside the **fox**." | `MOVE:butterfly-1:bottom-right` | NOOP x3 | 0.06 -> **0.98** |

Correct slot, clean discrimination between two similar object-relative
options, and immediate convergence once the goal is met.

**A compound goal is sequenced correctly:**

```
intent: "Make the butterfly flutter gently beside the lantern."

turn 1  ANIMATE:butterfly-1:flutter   motion 0.05 -> 0.96
turn 2  MOVE:butterfly-1:centre       position 0.07 -> 0.98
turn 3  NOOP                          both satisfied
turn 4-6 NOOP
```

Two sub-goals, addressed one per turn, against an action table regenerated
from world state every turn, then a stable stop. That is the §14 competence
question answered in the affirmative.

### What was withdrawn

An earlier revision of this document reported that Jev "repeatedly chooses
`MOVE:butterfly-1:near-fox`" when asked for the lantern, and self-reported
success at 0.69-0.81 — described as a real residual weakness and cited in
root `SECURITY.md` as evidence that confidence is unreliable. **That finding
was invalid** and has been retracted in both documents. It was an artefact of
the truncated-intent bug. The lesson is not about Jev: a negative result
about a model should not be published before the harness feeding it has been
verified.

---

## Tests

| Suite | What it proves | Result |
|---|---|---|
| `tests/test_jev_core.py` (18 tests) | All 10 fail-closed requirements against the adapter: unknown action, malformed response, timeout, API error, `shell`/write/delete/MeTTa rejection, invented tool names, smuggled arguments, and a property check that output is always a table literal or empty. | 18/18 pass |
| `tests/verify_in_container.py` | Same boundary against Omega's **real** `helper.py` inside the image: allowlist is exactly `{version, jev-noop}`; all 15 stock Omega commands except `version` compile to `UNKNOWN_SKILL_CALL` (with a completeness check that none was skipped); permitted actions cannot expand the allowlist; removed modules are physically absent. | all pass |
| `tests/verify_filesystem_boundary.py` | Runtime filesystem boundary as uid 65534, including an isolating probe (`/run/lock`) that proves Landlock is genuinely enforcing and not silently degraded. | all pass |
| `stage1/jev_smoke.py` | Decisions API reachable, typed choice returned, choice within supplied keys, probabilities observable, no text generation, out-of-vocabulary rejected. | 4/4 pass |
| `tests/verify_network_boundary.py` | Agent network is a Docker *internal* network; openrouter.ai, github.com and pypi.org all unreachable from it; gateway reachable, publishes no ports, refuses non-`/jev/` paths; agent image and running container hold no `OPENROUTER_API_KEY`. | 14/14 pass |
| `tests/verify_stop_path.py` | An external supervisor stops a healthy run before its in-process limit, and stops a deliberately **wedged** provider (`jevTimeout=3600`, `jevMaxTurns=999`) that `os._exit()` could never end. | all pass |
| `tests/verify_kernel_coupling.py` | Coupling adds no authority: allowlist is exactly `{sb-apply}`; no offered key targets a human-owned sticker; `remove`/`add` outside the profile intersection; 7 forged keys refused **with receipts**; staging single-use; table regenerated not cached; `pages-demo` leaves the agent nothing. | 38/38 pass |

### Baseline upstream tests

Not run. Upstream's suites (`tests/`, `Autotests/`) target the full stock
configuration — Telegram/Slack channels, generative providers, the knowledge
base — most of which this experiment deliberately removes. Running them would
report failures caused by our own reductions rather than by upstream defects,
which would be misleading. This is recorded as a gap, not a pass.

---

## Limitations

1. **The action vocabulary is two items.** This demonstrates plumbing and
   authority containment, not competence. Whether Jev selection remains
   coherent at 10, 50 or 200 actions is untested and is the main open
   question.
2. **The task is trivial.** "Report your version" needs no planning. Nothing
   here shows Jev can sequence actions toward a goal.
3. **Stage 2 alternation is arguably degenerate.** Jev follows the stated
   criteria correctly, but the VERSION/NOOP oscillation is a fixed point of
   those criteria rather than interesting behaviour. Stage 3 is better on this
   point: it converges on a goal state and stops acting.
4. **One question per turn.** Omega's loop can emit up to 5 commands per turn;
   we emit exactly one. Multi-action turns are untested.
5. **No memory or learning.** ChromaDB long-term memory is initialised but
   unused by the decision path. Nothing is recalled or generalised.
6. **Upstream baseline tests not run** (above).
7. **Competence is now demonstrated only on a small page** — one agent
   sticker, one human sticker, two backdrop features, five slots, seven
   options. It sequences a two-part goal correctly at that size; how far the
   table can grow before selection degrades is untested.
8. **`-dirty` version suffix.** The image reports
   `v0.1.19-141-gee0618a-dirty`. Host `git status` is clean at `ee0618a`; the
   suffix comes from file-metadata differences when building from a
   Windows-hosted checkout. Source content is the recorded commit.
9. **Security gaps** are listed honestly in `SECURITY.md` §11. Bounded views,
   the external stop supervisor and egress/gateway isolation are now closed;
   what remains is chiefly structured receipts and the operator-host secret
   exposure.

---

## Remaining work

* **Measure how far the action table can grow** before selection degrades:
  more stickers, more slots, more motions. Seven options is comfortable;
  the interesting boundary is unknown.
* **Try a goal the host cannot pre-compute a relation for**, to see how much
  of the current competence comes from `beside`/`not_beside` being handed
  over as finished labels rather than inferred.
* Give Jev a goal requiring more than one step, and see whether typed
  selection sequences sensibly.
* Decide whether one `choice` question per turn is the right shape, or whether
  several typed questions (`noul` for preconditions, `choice` for the action)
  is better.
* Persist and export receipts (they currently live in kernel memory only).
* Only after Paul reviews: consider the browser/StickerBook affordance model.
  Note that principals, ownership, receipts and revisions are all prerequisites
  for anything child-facing, and none of them exist yet.

---

## How to reproduce

```powershell
# One-time: build the baseline from unmodified upstream (~11 min)
docker build -t omega-jev:baseline C:\src\stickerbook\jev\PeTTa\repos\Omega

# Build the experiment layer (seconds)
cd C:\src\stickerbook\jev
docker build -t omega-jev:experiment -f Dockerfile.jev omega_jev

# Gateway + networks (one-time)
docker build -t jev-gateway:1 gateway
docker network create jev-egress
docker network create --internal jev-internal
$env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY","User")
docker run -d --name jev-gateway --network jev-egress -e OPENROUTER_API_KEY jev-gateway:1
docker network connect jev-internal jev-gateway

# Supervised run. No credential is passed to the agent.
python supervise.py --max-turns 4

# Stage 4: coupled to the authority kernel
python supervise.py --max-turns 6 -- jevActionSet=stickerbook `
    "jevIntent=Make the butterfly move gently near the lantern."

# Stage 3: the standalone butterfly demonstration
python supervise.py --max-turns 4 -- jevActionSet=butterfly `
    "jevIntent=Make the butterfly move gently."
```

`-t` is no longer required: nginx has left the agent container, so nothing
there needs a TTY to open `/dev/stderr`.
