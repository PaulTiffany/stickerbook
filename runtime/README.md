# StickerBook governed runtime

> **Current status (September 30, 2026):** Local powered development uses separate
> restricted ordinary Docker containers, with the kernel on the host. See
> [the current operator instructions](../docs/DOCKER_POWERED_LOCAL.md).
> The OpenShell launch/provisioning instructions below are an archived hardened
> target record, not the current working start path. OpenShell work is stopped.
> Docker is not equivalent to OpenShell containment.


This directory is operator infrastructure for the powered localhost book. It is
outside both agent authority graphs.

The archived OpenShell Windows launcher path is:

1. double-click **`Start StickerBook.cmd`** at the repository root;
2. use StickerBook in the browser opened at `http://127.0.0.1:8756/`;
3. double-click **`Stop StickerBook.cmd`** when finished.

On a host where pinned OpenShell v0.1.2 is not yet installed, the first start
installs it. That writes a system package, so Linux asks once for **your Linux
account password**. That prompt belongs to the operating system, not to
StickerBook: it is not an API key, and StickerBook neither stores nor forwards
it. The launcher prints an explanation before the prompt appears. OpenShell
runs its gateway as a systemd user service, so a WSL distribution needs
`systemd=true` under `[boot]` in `/etc/wsl.conf`; the launcher checks this and
says so rather than failing obscurely.

The first powered start may build the pinned Omega base image and ask once for
an **OpenRouter API key**. OpenRouter remains required because OmegaJev uses the
Jev Decisions API. The launcher may then ask for an optional **Sponsored ASI
Cloud** key for OmegaLLM; Enter skips it. Input is hidden.

The launcher does not write those credentials into the repository,
`.stickerbook-runtime/`, command arguments, or bridge process. OpenShell owns
provider credentials after creation. Later starts reuse provider instances.

Anthropic (`ANTHROPIC_API_KEY`), OpenAI (`OPENAI_API_KEY`), and ASI:One
(`ASIONE_API_KEY`) are optional OmegaLLM lanes. If their environment
variables are present while the matching OpenShell provider is first created,
or the provider already exists, they are attached to the OmegaLLM sandbox and
appear in the Responsible Adult selector.

## Boot graph

```text
operator launcher (trusted)
        |
        +-- verify Docker + pinned OpenShell
        +-- verify/build pinned Omega baseline
        +-- build current role images
        +-- verify canonical SWI executable identity
        |
        +-- OpenShell sandbox: OmegaLLM
        |      127.0.0.1:8761
        |      parent-selectable provider profiles:
        |      ASI Cloud / Anthropic / OpenAI / OpenRouter / ASI:One
        |
        +-- OpenShell sandbox: OmegaJev
        |      127.0.0.1:8762
        |      OpenRouter provider profile: Jev Decisions only
        |
        +-- host StickerBook bridge/kernel
               127.0.0.1:8756
```

The two agent ports are OpenShell forwards bound to host loopback. Inside each
sandbox the `stickerbookrpc` Omega communication channel also binds loopback.
The browser does not call either sandbox directly; `web/bridge.py` owns those
calls.

## What crosses each seam

OmegaLLM receives only:

- child text produced by voice recognition or accessibility text entry;
- the fixed browser principal id;
- a JSON scene view;
- an optional one-turn deictic reference.
- the **host-selected inference provider/model**, carried separately from the
  child scene.

It may return child-facing `reply` text and one schema-bounded semantic
`goal`. It does not receive the authority kernel.

OmegaJev receives only:

- the host-validated goal;
- fresh bounded scene state;
- the finite host-owned action-description table;
- the current bounded turn and maximum turn count.

It may return only one choice key. The host checks that key against its current
table and the authority kernel independently accepts or refuses the resulting
proposal.

Both are real Omega loops. `runtime/omega/stickerbookrpc.py` is an Omega
communication channel: one host request becomes one new Omega message, the role
provider stages one bounded JSON result, and Omega executes the fixed
zero-argument `sb-return` skill to complete the request. Free-form Omega
channel output is never parsed into authority.

## Responsible-adult inference routing

The bridge owns one inference selection for the current browser/server session.
Its default order is:

1. Sponsored ASI Cloud / `minimax/minimax-m3`, when configured;
2. OpenRouter / `z-ai/glm-5.2`;
3. the first other configured OmegaLLM lane;
4. Off, if no conversational provider is available.

The adult panel may switch among configured ASI Cloud, Anthropic, OpenAI,
OpenRouter, ASI:One, and Off without restarting Omega. Non-sponsored lanes may
use a bounded provider-supported model id; sponsored ASI Cloud is intentionally
locked to its sponsored MiniMax model.

This control does not grant StickerBook world authority. It only determines
which already-configured inference endpoint receives the next bounded OmegaLLM
request. The child cannot set it through conversation, and OmegaLLM cannot
change it itself.

The panel is currently an **audience control, not authenticated parental
security**. A person with direct access to the local browser/devtools can call
the loopback adult endpoint. That is acceptable for the current local research
profile, but paid-provider protection for a deployed child account would need a
separate authenticated adult boundary.

## Voice-first path

Voice does not create another agent or action interface:

```text
browser/device STT
      -> transcript
      -> /api/agent/converse
      -> OmegaLLM
      -> optional bounded goal
      -> OmegaJev
      -> kernel

OmegaLLM reply
      -> browser/device TTS
```

Speech recognition and speech synthesis are browser/device I/O. They possess no
StickerBook authority. The adult-controlled push-to-talk toggle and the
accessibility text chat use the same conversation function.

## Start / stop semantics

`runtime/start.sh`:

- requires Docker Desktop to be reachable from WSL;
- installs/repairs the project OpenShell v0.1.2 pin when necessary;
- checks OpenShell status;
- accepts a cached `omega-jev:baseline` only when its Omega version identifies
  the pinned source and SWI resolves to the authorized canonical executable;
- otherwise fetches exactly Omega commit
  `ee0618a293ec3662a32b10b09c6cbb073f59d6b2` and builds it;
- rebuilds the current OmegaLLM/OmegaJev role images using Docker cache;
- verifies SWI resolves to
  `/usr/lib/swipl/bin/x86_64-linux/swipl`;
- creates/reuses the two role-specific OpenShell providers;
- replaces only the two named StickerBook sandboxes;
- waits for each role health endpoint;
- starts the host authority bridge with explicit loopback runtime URLs;
- reports READY only when the bridge sees both conversational Omega and Jev.

`runtime/stop.sh` stops the tracked bridge from outside the agents, stops the
two loopback forwards, and deletes the two StickerBook sandboxes. Neither agent
has to cooperate.

`runtime/status.sh` reports the three loopback services and OpenShell status.

Local logs and the pinned upstream checkout live under
`.stickerbook-runtime/`, which is gitignored.

## Operator boundary

The launcher may instantiate capabilities already reviewed in the repository.
The Omega loops may not edit this launcher, Docker configuration, provider
profiles, OpenShell policies, repository files, or their own capability set.
OpenShell approval mode is explicitly `manual`.

No repository directory or Docker socket is mounted into either agent sandbox.

## Verification status

**Live-host deployment status: PARTIALLY VERIFIED on 2026-09-29.**

Two claims are kept apart here, because they are not the same claim:
**mechanically verified architecture is not a live-host verified agent graph.**
CI checks Python/shell syntax, browser/runtime seam tests, voice-seam
regression tests, and `openshell/verify.py`. CI does not run a WSL2/Docker
Desktop host, possess an OpenRouter provider, or launch real OpenShell
sandboxes.

First live-host attempt: Windows 11 + WSL2 (Ubuntu) + Docker Desktop, kernel
`6.6.87.2-microsoft-standard-WSL2`.

Verified on that host:

- Docker reachable from WSL (29.8.0);
- the launcher installed pinned OpenShell v0.1.2 itself, from a commit-pinned
  installer whose checksum was verified;
- the OpenShell gateway started and authenticated over mTLS;
- provider profiles imported and re-applied cleanly, and the OpenRouter and
  Sponsored ASI Cloud provider instances were created with their credentials
  held by OpenShell, not by this repository;
- the cached Omega baseline satisfied its pinned-source identity check, and
  all four role images built;
- the canonical SWI identity check passed for both role images
  (`/usr/lib/swipl/bin/x86_64-linux/swipl`);
- failed-boot cleanup and `runtime/stop.sh` both left no sandbox, forward,
  loopback listener or bridge process behind.

Blocked, and therefore unverified:

- OpenShell sandbox provisioning fails with `ControlSupervisorStartFailed`:
  `seccomp notification probe / notification launcher disappeared`;
- the same failure reproduces from a bare local image with **no** StickerBook
  policy and **no** provider attached, so it is not produced by this
  repository's configuration;
- the OpenShell gateway itself remains healthy across the failure, and
  cleanup still succeeds.

Upstream NVIDIA/OpenShell issue #3842 reports the same failure text on the same
WSL2 kernel family. Our reproduction matches that report. We have not
independently confirmed the mechanism that report suspects, and no fix for it
exists in v0.1.2.

Because no sandbox ever started, all of the following remain unverified and
must not be assumed:

- both health endpoints reporting the intended role;
- OpenRouter succeeding through each role-specific provider;
- unrelated destinations such as GitHub and PyPI being denied in each sandbox;
- the workload seeing only the OpenShell credential placeholder, never the
  real secret;
- SWI's canonical executable as observed inside a running sandbox;
- OmegaJev returning only an offered key;
- the kernel issuing a final acceptance/refusal receipt over a live turn.

Powered execution status: **BLOCKED_UPSTREAM / LIVE GRAPH UNVERIFIED.**
Development continues against the headless kernel, the bridge-only runtime,
the mechanical browser path, and deterministic test doubles.
