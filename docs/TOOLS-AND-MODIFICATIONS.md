# Tools, upstream modifications, and research/developer guide

This document is the implementation/provenance ledger for StickerBook.

It answers four questions for each important dependency or subsystem:

1. What is it used for?
2. What exact version or upstream revision is StickerBook built/tested against?
3. What did StickerBook change or add?
4. Why was that change necessary, and what authority does the resulting component have?

The short architectural rule is:

> **Capability is not authority.**

StickerBook deliberately combines capable components while keeping world
authority in a small host-owned kernel. A model, runtime, sandbox, provider,
renderer, or communication channel does not gain permission merely because it
can reason, speak, select, execute, or connect.

For license attribution, see [NOTICE](../NOTICE). For the binding security
model, see [SECURITY.md](../SECURITY.md). For recorded upstream revisions and
host/toolchain details, see [jev/VERSIONS.txt](../jev/VERSIONS.txt).

---

## 1. System map

The powered local path is:

~~~text
child
  |
  | browser/device speech recognition OR typed text
  v
web browser
  |
  | /api/agent/converse
  v
Python bridge + StickerBook authority kernel
  |
  | bounded conversation request + child-facing help
  v
OmegaLLM  [OpenShell sandbox]
  |
  | reply + optional bounded semantic goal
  v
host bridge validates goal
  |
  | fresh scene + finite host-owned action descriptions
  v
OmegaJev  [separate OpenShell sandbox]
  |
  | one offered action key
  v
host revalidates key
  |
  v
StickerBook authority kernel
  |
  | accept/refuse + Receipt + authoritative state
  v
browser renderer
~~~

A child's double-click may bypass OmegaLLM and enter OmegaJev directly, but only
through a one-turn animation-only finite action surface.

The public GitHub Pages build is a different profile. It contains the browser
renderer, static assets, and in-app documentation, but no Python bridge,
authority-kernel backend, Omega process, Jev provider call, OpenShell sandbox,
or provider credential.

---

## 2. StickerBook-authored components

These are not third-party dependencies. They are the project-specific control
plane around the upstream tools.

| Component | Location | Purpose | Authority |
|---|---|---|---|
| Authority kernel | core/ | Principals, ownership, legal action tables, revisions, budgets, receipts | **Sole world-mutation authority** |
| Browser/renderer | web/static/ | Child UI, SVG rendering, gestures, voice/text surfaces, in-app help | Proposes actions; renders returned state |
| Python bridge | web/bridge.py | Fixes browser principal, validates request shape, holds kernel, calls runtime seams | Holds kernel; no provider credential |
| OmegaLLM host adapter | web/agent_runtime.py | Loopback-only conversation RPC | No kernel object; no provider credential |
| OmegaJev host adapter | web/jev_runtime.py | Loopback-only finite-choice RPC | No kernel object; no provider credential |
| Jev controller | web/jev_controller.py | Converts validated semantic goals to finite host-owned action tables | Can propose only keys generated from current kernel state |
| In-app help | web/static/help.json | Child and responsible-adult documentation | Descriptive data only; child branch is projected to OmegaLLM |
| Omega RPC channel | runtime/omega/stickerbookrpc.py | Carries one bounded request/result through a real Omega CommChannel | Transport only; does not authorize |
| Omega RPC return skill | runtime/omega/stickerbookrpc.metta | Fixed zero-argument sb-return | Returns staged data only |
| Operator lifecycle | runtime/, root .cmd launchers | Build/verify/start/stop local powered runtime | Trusted operator infrastructure outside both agents |

### Why the kernel remains outside the agent sandboxes

The live browser path intentionally does not move the authority kernel into
OmegaLLM or OmegaJev.

That separation means:

- the language model cannot authorize its own goals;
- Jev cannot enlarge the finite table it receives;
- the model/provider process cannot equate inference success with world success;
- restarting or replacing an agent does not replace the authority policy;
- the independent stop path does not require model cooperation.

---

## 3. SingularityNET Omega

Upstream: https://github.com/singnet/Omega

Recorded revision:
ee0618a293ec3662a32b10b09c6cbb073f59d6b2
(described in the project record as v0.1.19-141-gee0618a).

Role in StickerBook: both OmegaLLM and OmegaJev remain real Omega loops.
StickerBook does not replace Omega with a home-grown loop and merely reuse the
name.

### 3.1 Upstream changes in the derived OmegaJev image

The changes below are applied in the derived image; StickerBook does not commit
them back into the upstream Omega repository.

#### A. Entrypoint quoting fix

Change: Omega's final command construction interpolated "$*" inside a
sh -c command, causing configuration values containing spaces to be split.
StickerBook patches that line using the quoting pattern already used elsewhere
in the upstream entrypoint.

Why: an operator intent such as a natural-language sentence was silently
truncated to its first word. This was a correctness bug discovered during the
Jev experiment, not a capability expansion.

Evidence: [jev/EXPERIMENT.md](../jev/EXPERIMENT.md).

#### B. Replace Omega configuration/plugin manifests

Change: config/config.yaml and config/plugins.yaml are replaced in the derived
role images.

Why: StickerBook must explicitly select the role-specific provider,
communication channel, finite-loop settings, disabled wake behavior, and
minimal plugin set. Depending on upstream defaults would make reachable
capability larger and harder to audit.

#### C. Disable the in-agent nginx startup in OpenShell-derived images

Change: the legacy nginx startup hook is replaced with a no-op and its
configuration template removed.

Why: credential mediation belongs outside the agent workload. In the older
verified Docker-network experiment it lives in a separate gateway container; in
the new OpenShell path the provider boundary holds the real secret.

#### D. Delete unused channel/provider modules

The OmegaJev derived image removes unused modules such as Telegram, Slack, IRC,
Mattermost, WebSocket, and generative providers that are not part of that role.

The OmegaLLM image likewise includes only its bounded conversation provider and
the StickerBook RPC channel/return skill.

Why: absence is stronger than "please do not use this plugin." Removed
capabilities cannot be reached accidentally through configuration drift.

### 3.2 StickerBook additions layered into OmegaJev

Important StickerBook-authored additions include:

- jev/omega_jev/providers/jev.py
- jev/omega_jev/providers/jev_core.py
- jev/omega_jev/providers/sb_bridge.py — legacy in-container kernel experiment
- jev/omega_jev/channels/jevconsole.py — legacy operator experiment channel
- jev/omega_jev/plugins/jevskills/
- runtime/omega/stickerbookrpc.py
- runtime/omega/stickerbookrpc.metta

### 3.3 StickerBook additions layered into OmegaLLM

The dedicated language-role image adds:

- llm/omega_llm/providers/stickerbook_llm.py
- llm/omega_llm/config/config.yaml
- llm/omega_llm/config/plugins.yaml
- the shared stickerbookrpc Omega channel
- the fixed sb-return skill

The OmegaLLM image deliberately contains no StickerBook authority kernel and
no Jev provider.

### 3.4 Why sb-return exists

In browser-service mode, model-selected data must never become executable
program text.

Both role providers therefore stage a bounded JSON result and return exactly
one executable Omega command:

~~~text
sb-return
~~~

It is zero-argument.

For OmegaJev, every offered StickerBook action key maps to that same literal.
The selected key is returned as data to the host, where it is rechecked against
the current host table before the kernel sees it.

This is intentionally different from the older in-container kernel experiment,
where the fixed target is sb-apply.

---

## 4. PeTTa and MeTTa

PeTTa upstream: https://github.com/trueagi-io/PeTTa

Two revisions matter and must not be conflated:

- host source inspection record: ae66fa8e41dcd5539d614706bd4e5cfb34f9608d;
- in-image tested PeTTa: v1.0.4, pinned by the upstream Omega Dockerfile.

StickerBook does not patch PeTTa in this integration. Omega uses PeTTa as its
efficient MeTTa implementation on top of SWI-Prolog.

MeTTa/Hyperon role: Omega's symbolic skills and loop machinery are expressed
through this stack. StickerBook's sb-return is a deliberately tiny MeTTa skill
because the project wants the Omega execution seam to remain real while keeping
its executable vocabulary narrow.

---

## 5. petta_lib_chromadb

Recorded revision:
218484875d5d1bfb217a9a03d3983dc1ed9d406c

This library is part of the upstream Omega layout/build used for memory support.

StickerBook does not modify it.

Important licensing note: the recorded revision had no LICENSE file in the
repository when inspected. StickerBook does not vendor or redistribute its
source here. See [NOTICE](../NOTICE) before redistributing a built image that
contains it.

The current StickerBook authority design does not treat memory as permission.
Even if Omega memory becomes richer, current kernel state still determines
authorization.

---

## 6. TypeSafe Jev

Service/model: typesafe/jev-1.13 through OpenRouter's Decisions API.

Role: discriminative typed selection among a host-supplied finite set.

StickerBook does not ask Jev to generate shell commands, code, coordinates, or
free-form tool arguments. The Jev provider constructs a typed Decisions API
request in which the meaningful output is one action identifier already owned
by the host.

### StickerBook-specific work around Jev

jev_core.py mechanically validates posing rules before a request is sent.
Among other things, it enforces:

- bounded object state rather than serialized prompt blobs;
- real instructions rather than question IDs;
- explicit descriptions for finite choices;
- explicit NOOP fallback where required;
- valid referenced state paths;
- typed answer parsing;
- fail-closed behavior for malformed/unknown results.

Why: a badly posed typed request can silently degrade decision quality even
when it remains security-bounded. The project therefore treats correct posing
as a mechanically testable interface property rather than a prompt-writing
habit.

### Live browser-service difference

The older Stage 4 experiment coupled Jev to an in-container StickerBook kernel
through sb-apply.

The current browser-service mode keeps the real browser kernel on the host:

~~~text
host finite table -> Jev chooses key -> sb-return -> host validates key -> kernel
~~~

That prevents the model sandbox from owning both selection and authorization.

---

## 7. NVIDIA OpenShell

Upstream: https://github.com/NVIDIA/OpenShell

Pinned release: v0.1.2
Pinned commit: 6648bd0c290efbc41ba131ee9831ee45cd431f94

Pin file: [openshell/PIN.env](../openshell/PIN.env)

StickerBook does not modify or vendor OpenShell source.

### What StickerBook adds around OpenShell

- openshell/policies/omega-llm.yaml
- openshell/policies/omega-jev.yaml
- openshell/providers/openrouter-omega-llm.yaml
- openshell/providers/openrouter-omega-jev.yaml
- pinned install helper
- role-specific service launchers
- operator lifecycle under runtime/
- non-root derived Omega role images

### Why there are two policies/providers

OmegaLLM and OmegaJev cooperate but have different roles. They should not
inherit one ambient sandbox simply because they participate in one child turn.

Each base policy starts with no network allow rules. The matching OpenRouter
provider contributes the approved provider endpoint.

The provider profiles bind egress to the kernel-resolved SWI executable:

~~~text
/usr/lib/swipl/bin/x86_64-linux/swipl
~~~

The boot script independently verifies that canonical identity and refuses to
start if the built image resolves swipl somewhere else.

### Why OpenShell is not the authority system

OpenShell answers containment questions such as:

- which files/process identity the workload has;
- where network traffic may go;
- how provider credentials are substituted;
- whether policy expansion requires operator approval.

It does not answer:

> May this StickerBook principal move this sticker right now?

That question remains in the StickerBook authority kernel.

### Approval behavior

Service launch explicitly requests:

~~~text
--approval-mode manual
~~~

Agent-authored policy expansion is not automatically approved.

### Verification status

The checked-in dual-Omega OpenShell path is **IMPLEMENTED + mechanically
checked, NOT YET LIVE-HOST VERIFIED**.

Do not inherit the verified status of the older Docker/nginx OmegaJev network
experiment.

---

## 8. OpenRouter

Service: https://openrouter.ai

StickerBook currently uses OpenRouter in three conceptually separate ways:

1. OmegaJev: Decisions API — POST /api/alpha/decisions
2. OmegaLLM: chat completion endpoint — POST /api/v1/chat/completions
3. Optional page-image gateway: an operator-selected image editing model

The first two provider credentials are held by separate OpenShell provider
instances in the powered runtime. The agent workload receives an OpenShell
placeholder; the real credential remains at the provider boundary.

The optional page-image gateway is a separate process from the authority bridge
and receives media rather than a kernel/principal object.

### Model configuration

- Jev default/configured model: typesafe/jev-1.13
- OmegaLLM current default: z-ai/glm-5.2

The OmegaLLM model string is configuration, not a reproducibility guarantee
equivalent to the OpenShell/Omega commit pins. If exact model-revision
reproducibility becomes necessary, add an explicit model-version record rather
than silently treating a provider alias as immutable.

---

## 9. SWI-Prolog

Base image: official swipl:10.0.2

Omega/PeTTa run inside SWI-Prolog.

StickerBook does not patch SWI-Prolog. It does, however, depend on the canonical
kernel-resolved executable identity for OpenShell egress policy:

~~~text
/usr/lib/swipl/bin/x86_64-linux/swipl
~~~

This is why the launcher checks readlink -f rather than assuming that
/usr/bin/swipl is the identity the kernel sees.

---

## 10. Browser, SVG, and Web Speech APIs

StickerBook's child UI uses browser-native HTML/CSS/JavaScript and SVG. No
front-end framework is required for the current renderer.

### Speech recognition

The browser checks the standard SpeechRecognition interface and the
webkitSpeechRecognition compatibility name.

Speech recognition is human input I/O, not an agent permission.

The browser/device may use its own speech service. StickerBook receives the
resulting transcript and sends that text through the same
/api/agent/converse path used by accessibility text chat.

Raw microphone audio is not passed by StickerBook to OmegaLLM.

### Speech synthesis

Replies can be spoken using SpeechSynthesisUtterance and
window.speechSynthesis.

Again, this is output I/O only. TTS has no StickerBook mutation authority.

### Child-facing help

web/static/help.json contains separate child and adult branches.

The browser can render both, but the Python bridge projects only the child
branch into OmegaLLM under scene.child_help.

The child branch deliberately omits API keys, OpenShell/Docker setup,
repository administration, provider configuration, and other operator
instructions.

The adult branch is not secret; it is simply outside the OmegaLLM observation
surface.

---

## 11. Python bridge and standard library

The authority kernel and browser bridge intentionally use a small Python
surface, largely standard library modules.

That is a design choice: the answer to

> May principal P perform action A on object O now?

should not depend on model inference, a large web framework, or a remote
service.

The bridge uses Python's built-in HTTP server and binds loopback only for the
powered local UI.

---

## 12. Docker Desktop and WSL2

The recorded development host is Windows 11 with WSL2 Ubuntu and Docker
Desktop. Exact recorded toolchain values live in
[jev/VERSIONS.txt](../jev/VERSIONS.txt).

These are operator/deployment tools, not agent tools.

Neither Omega role receives the Docker socket.

The normal development-host lifecycle is:

- Start StickerBook.cmd
- Stop StickerBook.cmd

The Windows wrappers enter WSL and invoke the checked-in trusted operator
scripts.

A failed boot tears down partial StickerBook runtime state. Shutdown stops the
tracked bridge and waits for both named sandboxes to disappear.

---

## 13. nginx: legacy verified credential-gateway profile

The older OmegaJev experiment uses a separate nginx container as a narrow
credential gateway.

Base image: official nginx:1.27-alpine

StickerBook narrows the gateway to the Jev Decisions route and health behavior
rather than exposing Omega's broader upstream proxy route set.

The agent runs on an internal Docker network with no general Internet route;
the gateway bridges that network to provider egress.

This path is retained because it has useful runtime verification evidence. It
is not the normal dual-Omega browser-service architecture.

Do not confuse:

- legacy gateway profile: runtime-verified OmegaJev experiment;
- new OpenShell profile: dual-role powered target, implemented and
  mechanically checked, pending live-host proof.

---

## 14. Landlock

Omega's older filesystem experiment uses Linux Landlock through its security
policy stack. The recorded WSL2 host exposed Landlock ABI 3 and the OmegaJev
verification suite demonstrated a denial that POSIX permissions alone would
not have produced.

OpenShell also has its own containment policy model and Landlock compatibility
setting in the checked-in policies.

Landlock is containment. It does not replace StickerBook's principal/ownership
authorization.

---

## 15. GitHub Actions and GitHub Pages

### Actions

CI currently checks, among other things:

- browser JavaScript syntax;
- in-app help JSON validity;
- authority-kernel tests;
- web/bridge/runtime adapter tests;
- child/adult help audience tests;
- OmegaLLM/OmegaJev/RPC Python syntax;
- operator shell syntax;
- static OpenShell integration contract.

### Pages

The public Pages artifact is explicitly assembled from allow-listed static
content.

It includes:

- index.html
- static/app.js
- static/style.css
- static/help.json
- static image/data assets

It does not ship Python runtime code, Omega, Jev, OpenShell, credentials, or the
authority-kernel backend.

The public UI may display the responsible-adult explanation, but live controls
that require the powered runtime remain unavailable.

---

## 16. Modification matrix

| Upstream/tool | StickerBook modification/addition | Why |
|---|---|---|
| Omega | Entrypoint quoting patch | Preserve natural-language config values containing spaces |
| Omega | Replace role config/plugins | Minimize and make reachable capability explicit |
| Omega | Disable in-agent nginx in OpenShell role images | Keep real credentials outside agent process |
| Omega | Delete unused channels/providers | Make removed capabilities absent, not merely discouraged |
| Omega | Add stickerbookrpc channel | Preserve real Omega loop while giving host a narrow bounded seam |
| Omega | Add fixed sb-return skill | Keep model-selected data out of executable text |
| OmegaJev | Add Jev typed provider/core | Typed finite discriminative selection instead of generative executable output |
| OmegaLLM | Add bounded JSON conversation provider | Separate language mediation from actuation |
| OpenShell | No upstream source patch; local policies/providers/orchestration | Contain each role without creating a second authority system |
| OpenRouter | No service patch; separate role endpoints/providers | Keep inference transport separate from world authorization |
| PeTTa | No project patch | Used as Omega's MeTTa execution engine |
| SWI-Prolog | No project patch | Runtime for PeTTa/Omega; canonical path is policy identity |
| Web Speech APIs | No vendor patch | Voice/text are two projections of the same human conversation seam |
| nginx legacy gateway | Narrow gateway routes/config | Credential isolation for the older verified Jev profile |

---

## 17. What has deliberately not been merged into one component

Several separations are intentional and should survive future refactors:

- OmegaLLM is not OmegaJev.
- language translation is not authorization.
- discriminative selection is not authorization.
- OpenShell containment is not StickerBook authority.
- provider credential possession is not StickerBook authority.
- renderer state is not authoritative state.
- child documentation is not operator documentation.
- public Pages is not a disabled copy of the powered backend.
- generated media drafts are not automatically installed governed content.
- memory is not permission.
- a successful model response is not proof that a world action succeeded.

If a future implementation collapses one of those distinctions, the change
should be treated as an architectural security review, not a routine cleanup.

---

## 18. Verification ledger

Use the status terms in the root security document precisely.

| Surface | Current status | Evidence |
|---|---|---|
| Authority kernel | **VERIFIED** for named core invariants | core/tests/ |
| Browser/kernel host seam | **VERIFIED** for named bridge behaviors | web/tests/ |
| Child/adult documentation projection | **VERIFIED** at host/static seam | web/tests/test_help_content.py |
| Voice uses same conversation seam as text | **VERIFIED** statically | web/tests/test_voice_contract.py |
| Legacy OmegaJev Docker/nginx profile | **VERIFIED** for its named runtime claims | jev/tests/verify_*.py |
| Dual-Omega OpenShell artifacts | **IMPLEMENTED + mechanically checked** | CI + openshell/verify.py |
| Dual-Omega OpenShell on actual WSL2/provider host | **NOT YET LIVE-HOST VERIFIED** | Requires local deployment proof |
| Public Pages powered-agent absence | Build-target property, mechanically assembled | .github/workflows/pages.yml |

A green component test does not automatically upgrade a different deployment
profile to VERIFIED.

---

## 19. Where to read next

- [SECURITY.md](../SECURITY.md) — binding authority/security model
- [AGENT-INTERFACE.md](AGENT-INTERFACE.md) — OmegaLLM/OmegaJev browser interfaces
- [runtime/README.md](../runtime/README.md) — powered boot/shutdown lifecycle
- [openshell/README.md](../openshell/README.md) — containment and provider boundary
- [jev/SECURITY.md](../jev/SECURITY.md) — OmegaJev-specific evidence
- [jev/EXPERIMENT.md](../jev/EXPERIMENT.md) — experimental history and corrected failures
- [NOTICE](../NOTICE) — licenses and third-party attribution
- [jev/VERSIONS.txt](../jev/VERSIONS.txt) — recorded revisions/toolchain
