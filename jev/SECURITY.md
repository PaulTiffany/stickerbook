# SECURITY — Jev/Omega experiment (component document)

> **This is the component-level document for OmegaJev.**
> The constitutional security model for StickerBook is
> [`../SECURITY.md`](../SECURITY.md). That document defines what must be true;
> this one records, with mechanical evidence, how OmegaJev currently makes
> some of it true — and nothing more. Where the root document marks an
> invariant N/A YET or GAP for OmegaJev, this document does not claim it.

> **Capability does not imply authority.**
> Jev may select only among capabilities explicitly provided by the host.
> Inference, confidence, memory, and recursive operation never expand that set.

Jev's probability and confidence values are **information**. They are not
authorization and never function as a safety certificate. A decision made with
confidence 1.0 has exactly the same authority as one made with confidence 0.1:
the authority comes from the host's action table, not from the model.

This document describes what is **actually enforced** by code and
configuration in this repository. Every boundary below names the mechanism
that enforces it and the command that verifies it. Where something is *not*
enforced, it is listed under "Known gaps" rather than omitted.

Verified on 2026-09-26 against image `omega-jev:experiment`.

---

## 1. The core architecture

```
Omega state/context (a string)
        |
        v
  JevProvider.chat()                providers/jev.py
        |
        v
  OpenRouter Decisions API          via local nginx proxy only
        |
        | typed {"type":"choice","choice":"<ACTION_ID>"}
        v
  jev_core.parse_decision()         rejects anything not a table KEY
        |
        v
  jev_core.compile_action()         dict lookup; returns a fixed literal
        |
        v
  Omega helper.balance_parentheses  -> "((version))"
        |
        v
  stock Omega sread / eval
```

**Jev chooses. The host compiles. Omega executes.**

No byte Jev returns is ever concatenated into, formatted into, or used to
construct the string Omega parses. The only influence Jev has is *which key*
is looked up in a frozen dictionary.

### The authority table

`omega_jev/providers/jev_core.py`:

```python
ACTIONS = {
    "VERSION": "version",
    "NOOP":    "jev-noop",
}
```

A second, equally host-owned set is selectable at run time with
`jevActionSet=butterfly` (the Stage 3 demonstration):

```python
ACTIONS_BUTTERFLY = {
    "BUTTERFLY_FLUTTER": "butterfly-flutter",
    "BUTTERFLY_REST":    "butterfly-rest",
    "NOOP":              "jev-noop",
}
```

The sticker id and the animation names are baked into the skill *names*, in
host source. Both skills take **no arguments**. Jev cannot name a sticker,
an animation, a coordinate or a duration — it selects which of three
pre-authorised motions happens next.

These tables are the authority boundary. Jev cannot add to them, alter a
value, select a set, or cause any string outside the active table to reach
Omega. Enlarging or adding a set is a deliberate, reviewable act by a human
editing source, never a runtime event.

**Only the active set is executable.** The butterfly skills exist as real
MeTTa functions in the image at all times, but `harden_llm_commands()` admits
only the active set's heads:

```
[PASS] butterfly-flutter  blocked while generic set active
[PASS] butterfly-rest     blocked while generic set active
[PASS] butterfly set allows exactly ['butterfly-flutter','butterfly-rest','jev-noop']
[PASS] 'version' blocked while butterfly set active
[PASS] 'shell' still blocked under butterfly set
```

---

## 2. Trust boundaries

| Principal | Authority | Enforced by |
|---|---|---|
| **Developer (Claude/Paul)** | May edit the experiment source tree on the Windows host | Ordinary host file permissions |
| **Build** | May write into the image | Docker build, runs as root at build time only |
| **Omega runtime** | May write **only** `memory/` and `/tmp`; may execute **only** `version` and `jev-noop` | uid 65534 + Landlock + `LLM_COMMANDS` |
| **Jev (the model)** | May select one key from `ACTIONS`. Nothing else. | `jev_core.parse_decision` + `compile_action` |

Developer authority and runtime authority are **separate principals**. The
fact that a developer may edit `providers/jev.py` does not give the running
agent that power: the agent runs as uid 65534 and the file is root-owned.

Verified:

```
[PASS] cannot modify own source (POSIX)
       PermissionError: '/PeTTa/repos/Omega/providers/jev.py'
```

---

## 3. What Jev can execute

The complete executable vocabulary of the running system is **two commands**
(generic set, the default):

```
['jev-noop', 'version']
```

or **three** under the Stage 3 butterfly set:

```
['butterfly-flutter', 'butterfly-rest', 'jev-noop']
```

* `version` — stock Omega skill; returns a version string.
* `jev-noop` — added by this experiment (`plugins/jevskills/jevskills.metta`);
  defined as `(= (jev-noop) JEV-NOOP-OK)`. It takes no arguments, touches no
  file, and runs no command. It exists so "do nothing" is a real action rather
  than something powerful borrowed for the purpose.

### Disabled Omega capabilities

Stock Omega allows 16 commands. The following are **mechanically unreachable**
in Jev mode — not discouraged by prompt text, but blocked in code:

`shell`, `metta`, `read-file`, `write-file`, `write-file-b64`, `append-file`,
`delete-file`, `get-io-policy`, `websearch`, `send`, `remember`, `query`,
`episodes`, `pin`, `search`

**Mechanism 1 — the action table.** Jev can only return a key of `ACTIONS`.
Any other value fails closed (`jev_core.parse_decision`).

**Mechanism 2 — the allowlist.** `providers/jev.py::harden_llm_commands()`
clears Omega's global `helper.LLM_COMMANDS` and `helper.STATIC_LLM_COMMANDS`
and replaces them with exactly the command heads our table can emit. Anything
else that reaches Omega's parser becomes `(Error UNKNOWN_SKILL_CALL ...)` and
is never evaluated. This runs at plugin load *and* again in `start()`, before
the first decision.

`STATIC_LLM_COMMANDS` is replaced, not just `LLM_COMMANDS`, because upstream's
`remove_llm_command()` deliberately refuses to remove built-ins — so removing
`shell` through the stock API is impossible by design.

**The vocabulary cannot grow at run time.** Omega *can* normally extend its own
command set: `add-skill` calls `helper.add_llm_command()`, and `add-skill` is
reachable from the `metta` skill. The claim is that no action in any Jev table
reaches that path. Verified (root `SECURITY.md` §2, test 6):

```
[PASS] executing every side-effecting action leaves the allowlist unchanged
       -- ['jev-noop', 'version']
[PASS] 'metta' (the route to add-skill) is not reachable
[PASS] every action literal is a bare zero-argument command head
       -- ['butterfly-flutter', 'butterfly-rest', 'jev-noop', 'version']
```

The last check matters independently: because every literal is a bare command
head with no argument position, there is nowhere for an argument to be
smuggled even if validation were bypassed.

**Mechanism 3 — deletion.** `Dockerfile.jev` deletes the channel and provider
modules entirely, so a future mistake in `plugins.yaml` still cannot reach
Telegram, Slack, IRC, Mattermost, WebSocket, or any generative LLM provider.

Verified (`tests/verify_in_container.py`, against Omega's **real** parser):

```
[PASS] shell            blocked  -- ((Error UNKNOWN_SKILL_CALL "shell whoami"))
[PASS] metta            blocked  -- ((Error UNKNOWN_SKILL_CALL "metta (shell \"whoami\")"))
[PASS] delete-file      blocked  -- ((Error UNKNOWN_SKILL_CALL "delete-file /tmp/x.txt"))
... every stock command except 'version' blocked (15 of 15)
[PASS] 'version'  -> ((version))
[PASS] 'jev-noop' -> ((jev-noop))
```

### No LLM fallback

There is no fallback to an unrestricted model, and this is structural rather
than a policy statement: `config/plugins.yaml` does not load `openai`,
`openaiapi`, `openrouter`, `asione` or `mockprovider`, and `Dockerfile.jev`
deletes those files. No other provider is registered, so there is nothing to
fall back *to*.

---

## 3b. Kernel mode: coupling to the StickerBook authority kernel

With `jevActionSet=stickerbook` the action table is no longer a fixed dict in
this repository. It is generated **per turn** by the authority kernel in
`../core` from actual world state, and the kernel — not this adapter — decides.

```
kernel generates table   ->  {"ANIMATE:butterfly-1:flutter": Command, ...}
Jev selects a KEY        ->  "ANIMATE:butterfly-1:flutter"
sb_bridge.stage(key)     ->  single-use slot; records, does not judge
Omega executes           ->  (sb-apply)      <- ONE zero-argument command
kernel.propose_key()     ->  Receipt(accepted, actor, object, revision)
```

**The executable vocabulary shrinks to one command.** `harden_llm_commands`
is called with the single literal `sb-apply`, so Omega's allowlist in this
mode is exactly `{sb-apply}` — a command with no argument position. Jev cannot
name a sticker, an anchor or an animation: those appear only inside
host-generated keys, and the key never becomes part of an executable string.

`sb_bridge` is deliberately *not* `import!`-ed by the MeTTa plugin. `py-call`
resolves it through Python's normal import machinery, which returns the same
module object the provider imported. A second module instance would silently
split the staging slot and the kernel from the ones the provider uses.

Staging does **not** pre-validate. An illegal or stale key is carried through
to the kernel so the refusal is receipted rather than dropped here — see §7.

Verified in `tests/verify_kernel_coupling.py` (38 checks).

---

## 3c. Enforced Decisions-API usage

Posing mistakes are silent quality failures: the request succeeds, the answer
is worse, and nothing reports it. We made five of them, plus a harness bug
that truncated the operator's goal to its first word (see `EXPERIMENT.md`),
so correct usage is now **mechanical** rather than remembered.
`jev_core.validate_request` runs on every request and refuses:

| Rule | Rejects |
|---|---|
| state must be an object, never serialized JSON | `state="{...}"` as a string |
| state must be bounded | over 4000 bytes |
| instructions must be real, and not the question id | `"action"`, `"which action?"` |
| backticked field paths must exist in state | `` `motion` `` when state has no such path |
| a choice needs >= 2 options with real descriptions | an option described by its own key |
| a choice must offer an explicit `NOOP` fallback | forcing an arbitrary pick |
| a `noul` must describe both sides | `{"true": ...}` only |
| a `score` must list its levels | a non-list |

A violation raises `JevPosingError`, a subclass of `JevFailClosed`, so a
malformed request **fails closed before it is sent**: nothing is executed and
the trace records `posing error: ...`. Thirteen cases are covered in
`tests/test_jev_core.py::TestPosingIsEnforced`, each one a mistake actually
made here.

This is a quality mechanism, not a security one: a badly posed request was
never able to exceed the action table. It is listed here because the same
principle applies -- enforce the property, do not rely on remembering it.

**Probes carry no authority.** Additional `noul` questions are answered in
the same round trip and recorded in the decision trace for inspectability.
Only the `action` answer is ever actuated, and a probe cannot overwrite the
action question (tested).

---

## 4. Network boundary

### Verified gateway profile (`jevTransport=gateway`)

**Allowed destination: exactly one, and the agent has no other route.**

```
http://jev-gateway:8080/jev/decisions  ->  https://openrouter.ai/api/alpha/decisions
```

The gateway is a **separate container** (`gateway/Dockerfile`: stock nginx,
no Omega, no Python, no agent code). Two networks enforce the split: the
agent runs only on `jev-internal`, a Docker *internal* network with no
external route; the gateway bridges `jev-internal` and `jev-egress`.

The agent therefore cannot reach the Internet at all — this no longer depends
on which skills it holds. Verified in `tests/verify_network_boundary.py`:
openrouter.ai, github.com and pypi.org are all unreachable from the agent's
network, the gateway is reachable, the gateway publishes no ports and refuses
any path outside `/jev/`.

`gateway/default.conf.template` keeps two routes where upstream's proxy had 13
routes to two (`/jev/`, `/health`). Removed: `/anthropic/`, `/openai/`,
`/asicloud/`, `/asione/`, `/openaiapi/`, `/openclaw/...`, `/openrouter/`,
`/telegram/`, `/mattermost/`, `/slack/`, `/slack-files/`.

No Telegram, Slack, Mattermost, IRC, WebSocket or web search is reachable:
the credentials do not exist, the proxy routes do not exist, and the client
code has been deleted from the image.

---

## 5. Secret handling

### Verified gateway credential profile

**The API key is never in the agent's container at all in gateway mode.**

Since the gateway was separated, `OPENROUTER_API_KEY` is not passed to the
agent container in any form — verified against both the image config and a
running container. What follows describes the additional upstream protections
that remain in force for `jevTransport=gateway`.

1. The key is supplied to the **gateway** container only, as
   `OPENROUTER_API_KEY`. It is never passed to the agent container.
2. The gateway's nginx substitutes it into its own generated config, in its
   own container, on its own filesystem.
3. Upstream's `entrypoint.sh` still **scrubs the environment** in the agent
   container — `exec env -i $env_args` — passing only an allowlist of
   variables. `OPENROUTER_API_KEY` is not on that allowlist, so even if it
   were passed by mistake the agent process would not inherit it.
4. The agent posts to `http://jev-gateway:8080/jev/decisions` with **no**
   `Authorization` header. The gateway injects it.

This is upstream Omega's own design, preserved. It was deliberately *not*
loosened: adding `OPENROUTER_API_KEY` to the entrypoint's `SAFE_VARS` would
have been the easy way to make the experiment run, and would have handed the
credential to the agent.

Verified:

```
[PASS] cannot read generated nginx.conf (holds the API key)
       PermissionError: '/opt/nginx/nginx.conf'
[PASS] OPENROUTER_API_KEY absent from this environment
```

The key is never written to source, JSON, YAML, `.env`, a log, a test fixture,
or a commit. It is stored as a Windows user environment variable and passed to
Docker with `-e OPENROUTER_API_KEY` (name only, value from the environment).

**To remove the key when finished:**

```powershell
[Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", $null, "User")
```

### OpenShell provider profile (`jevTransport=openshell`)

**IMPLEMENTED + mechanically checked, NOT YET LIVE-HOST VERIFIED.** The
OpenShell deployment mode is a separate containment profile; it does not inherit
the gateway profile's mechanical verification above.

The base sandbox policy contains no network rules. The attached
StickerBook-specific provider contributes the sole OpenRouter endpoint. The real
provider secret remains at the OpenShell boundary. OmegaJev sees only the
provider placeholder in `OPENROUTER_API_KEY` and presents that placeholder to
`https://openrouter.ai/api/alpha/decisions`; OpenShell substitutes the real
credential only on the approved route.

The derived `Dockerfile.openshell` runs uid/gid 65534 and bypasses the legacy
nginx startup. No StickerBook repository or Docker socket is mounted into the
sandbox.

OpenShell authorizes egress against the kernel-resolved executable identity.
The pinned SWI image is built with `CMAKE_INSTALL_PREFIX=/usr`, and the
provider profile now authorizes only:

```text
/usr/lib/swipl/bin/x86_64-linux/swipl
```

The operator launcher independently checks `readlink -f $(command -v swipl)`
inside both derived role images and refuses to start if it differs. A live
sandbox must still observe that identity before this status advances to
VERIFIED.

#### Browser service mode: `jevActionSet=stickerbook-rpc`

The live browser path deliberately does **not** use the legacy in-container
StickerBook kernel coupling. The authoritative kernel stays in
`web/bridge.py`.

The host sends OmegaJev only:

- one validated semantic goal;
- a bounded fresh scene;
- the finite host-owned action-description map;
- the current turn and host-bounded maximum (at most six).

Every offered key is mapped inside the provider to exactly the same executable
literal, `sb-return`. Jev's typed decision identifies one offered key; that key
is staged as data, Omega executes the fixed zero-argument return skill, and the
host validates the returned key against its current table before calling the
kernel.

Thus the live service executable vocabulary is **`{sb-return}`**, not
`{sb-apply}`. `sb-apply` remains the legacy in-container kernel experiment.
The browser-service model cannot put a sticker id, coordinate, animation name,
or action key into executable text.

The communication channel itself is a real Omega `CommChannel`
(`runtime/omega/stickerbookrpc.py`), bound to sandbox loopback. OpenShell
forwards host `127.0.0.1:8762` to it. Only one request may be active at a time,
matching Omega's sequential loop.

OpenShell service creation uses `--approval-mode manual`. The agent cannot
approve policy expansion, modify the provider, edit orchestration, mount the
repository, or acquire Docker authority.

The two gateway-profile statements that must not be generalized remain:

- the OpenShell sandbox may reach its policy-approved OpenRouter endpoint;
- OmegaJev can observe the OpenShell placeholder value, though not the real
  OpenRouter secret.

Required live proof is documented in `../runtime/README.md`: successful
Decisions API use, denied unrelated egress, placeholder-only secret visibility,
canonical executable identity, offered-key-only selection, host/kernel receipt,
and external teardown.

---

## 6. Filesystem boundary

Writable by the running agent:

* `/PeTTa/repos/Omega/memory` — the dedicated experimental state directory
* `/tmp`, `/var/tmp`, `/dev/shm`, `/dev/null`
* `/memory-transfer`, `/opt/huggingface`, `/opt/sentence_transformers`

Everything else, including the agent's own source code and the security
policy itself, is read-only or inaccessible.

Two independent mechanisms:

* **POSIX** — the agent runs as uid 65534; source is root-owned.
* **Landlock** (Linux kernel sandbox, `profile/policy.yaml`, applied at
  startup by `applySecurityPolicy`).

Landlock is genuinely enforcing here, not silently degraded. The proof is
`/run/lock`, which is world-writable (mode 1777) but absent from
`policy.yaml`, so only Landlock can deny it:

```
[PASS] CAN write /run/lock before Landlock (POSIX allows it)  -- opened for append
[PASS] LANDLOCK ALONE now denies /run/lock
       PermissionError: '/run/lock/landlock_probe2.txt'
```

No host directory is mounted into the container. Paul's home directory, the
`C:` drive, unrelated repositories and personal files are simply not present
in the container's filesystem. The Docker socket is not exposed,
`--privileged` is not used, host networking is not used, and the agent does
not run as root.

---

## 7. Failure behaviour — everything fails closed

Every abnormal condition returns `FAIL_CLOSED_OUTPUT` (`""`), which Omega's
`balance_parentheses` compiles to `"()"` — the empty expression, over which the
loop iterates **zero** commands.

| Condition | Result |
|---|---|
| Unknown / invented ACTION_ID | no execution |
| Malformed or non-JSON response | no execution |
| Wrong answer type (`noul`, `score`) | no execution |
| Extra non-typed fields (possible prose) | no execution |
| Network failure | no execution |
| Timeout (30s) | no execution |
| HTTP error | no execution |
| Argument smuggled into the choice | no execution |

Verified: `tests/test_jev_core.py` (18 tests) and
`[PASS] fail-closed output compiles to '()'`.

---

## 7b. Receipts

In kernel mode every agent action produces a structured receipt carrying
causal provenance:

```
SB-RECEIPT jev-1 actor=agent:jev-visual-1 action=animate-own-sticker
           object=butterfly-1 accepted=True reason=ok rev=3
```

Rejections are receipted too, which was **not** true when the coupling was
first written: the bridge pre-validated the key and dropped illegal ones
silently, so a refusal left only a log line. The coupling test caught it. The
kernel is now the single decision point and issues the refusal itself. Seven
forged keys — a human-owned target, tools not held, an undeclared animation,
a path traversal, a shell-injection attempt — each yield
`accepted=False reason=unknown-action-key`.

Receipts are held in kernel memory for the life of the run. They are not yet
persisted or exported.

---

## 8. Finite operation

* **`supervise.py` is the brake** — a separate host process enforcing a turn
  count, a stall timeout and a wall-clock deadline, sharing no process, pipe
  or failure mode with the agent. See §11 and root `SECURITY.md` §19.
* In legacy standalone modes, `jevMaxTurns: 6` remains an in-process
  **backstop**, not the brake. After 6 decisions the provider exits.
* In `stickerbook-rpc` browser-service mode the Omega process is resident and
  does not use a cumulative provider turn counter. Each host goal supplies
  `turn` / `max_turns`, the RPC channel rejects values above six, and the
  host rebuilds a fresh finite table on every turn.
* `wakeupInterval: 86400000` and `maxWakeLoops: 0` — autonomous waking and
  "keep thinking while idle" are effectively disabled.
* The channel (`jevconsole`) delivers a single operator-supplied intent once,
  then returns `""` forever. Nothing external can inject new input.
* Runs are human-triggered, in the foreground, with `--rm`.

---

## 9. How to stop the experiment

It stops itself after 6 turns. To stop it sooner:

```powershell
docker stop omega-jev-run          # graceful
docker rm -f omega-jev-run         # forced
```

To confirm nothing is running:

```powershell
docker ps --filter name=omega-jev
```

Empty output means stopped. Because the container runs with `--rm`, nothing
persists after exit except the image itself.

---

## 10. How to verify these restrictions are actually active

All three are runnable now and exit non-zero on any failure.

```powershell
# 1. Adapter boundary, 18 tests, no container or network needed
cd C:\src\stickerbook\jev
python -m unittest discover -s tests -v

# 2. Real runtime: allowlist, blocked skills, deleted modules
docker run --rm -i --entrypoint python3 omega-jev:experiment - `
    < tests\verify_in_container.py

# 3. Real runtime: filesystem boundary as the agent user
docker run --rm -i --user 65534 -w /PeTTa --entrypoint python3 `
    omega-jev:experiment - < tests\verify_filesystem_boundary.py

# 4. Network split: agent has no egress, gateway holds the key
#    (needs the gateway running -- see "Running it" below)
python tests/verify_network_boundary.py

# 5. Stop path: the supervisor halts both a healthy and a wedged run
#    (~2-3 minutes; starts and removes containers)
python tests/verify_stop_path.py
```

### Running it

```powershell
# one-time: images and networks
docker build -t jev-gateway:1 gateway
docker build -t omega-jev:experiment -f Dockerfile.jev omega_jev
docker network create jev-egress
docker network create --internal jev-internal

# the gateway holds the key; the agent never sees it
$env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY","User")
docker run -d --name jev-gateway --network jev-egress -e OPENROUTER_API_KEY jev-gateway:1
docker network connect jev-internal jev-gateway

# supervised run -- note that no credential is passed to the agent
python supervise.py --max-turns 4 -- jevActionSet=butterfly "jevIntent=Make the butterfly move gently."
```

Tear down with `docker rm -f jev-gateway` and
`docker network rm jev-internal jev-egress`.

---

## 11. Known gaps — not yet enforced

Listed because a boundary that is only claimed is not a boundary.

1. **The provider secret is visible via `docker inspect`** — now on the
   *gateway* container only, which holds no StickerBook authority and no
   agent code. This is an operator-host exposure, not agent authority, but a
   stronger secret-delivery design is required before broader distribution.

   *Closed since the previous revision:* container egress is now blocked by
   an internal Docker network (§4), the credential gateway is a separate
   container (§4, §5), and the brake is an external supervisor rather than an
   in-process counter (§8).

2. **The key is visible to the host via `docker inspect`.** Passing `-e`
   records the value in the container's config on Paul's machine. It is not
   visible to the agent, but it is visible to anyone who can run Docker there.

3. **Omega's prompt text still advertises removed skills — in the logs
   only.** Jev no longer receives that text: it is handed a bounded view
   (`jev_core.project_view`) whose `available_actions` field is exactly the
   active table's keys, and the absence of `shell`, `write-file`, `metta` and
   `websearch` from the view is tested. But Omega still constructs the
   `SKILLS:` string internally and it appears in the container log's
   `CHARS_SENT` line, which can mislead a human reading raw logs.

4. **Landlock is `best_effort`.** Verified enforcing on this kernel (WSL2
   6.6.87.2, Landlock ABI 3). On a kernel without Landlock it would degrade
   silently, leaving only POSIX. Re-run verification #3 on any new host.

5. **`-t` (TTY) is required.** Without it nginx cannot open `/dev/stderr` and
   the container fails to start. This is an upstream expectation
   (`usermod -a -G tty www-data`), not a change we made.

6. **No StickerBook, browser, DOM or child-facing surface exists yet.** None of
   the eventual child-safety properties are implemented or claimed here.
