# StickerBook governed runtime

This directory is operator infrastructure for the powered localhost book. It is
outside both agent authority graphs.

The normal Windows path is intentionally boring:

1. double-click **`Start StickerBook.cmd`** at the repository root;
2. use StickerBook in the browser opened at `http://127.0.0.1:8756/`;
3. double-click **`Stop StickerBook.cmd`** when finished.

The first powered start may build the pinned Omega base image and ask once for
an OpenRouter API key if the two OpenShell provider instances do not exist yet.
Input is hidden. The launcher does not write that credential into the
repository, `.stickerbook-runtime/`, command arguments, or bridge process.
OpenShell owns the provider credential after creation. Later starts reuse those
provider instances.

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
        |      OpenRouter provider profile: LLM only
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

**IMPLEMENTED + mechanically checked, NOT YET LIVE-HOST VERIFIED.**

CI checks Python/shell syntax, browser/runtime seam tests, voice-seam regression
tests, and `openshell/verify.py`. CI does not run Paul's WSL2/Docker Desktop
host, possess his OpenRouter provider, or launch the actual OpenShell sandboxes.

The first successful local powered start should therefore be treated as a
deployment verification event, not as something CI has already proved. Verify
at minimum:

- both health endpoints report the intended role;
- OpenRouter succeeds through each role-specific provider;
- unrelated destinations such as GitHub and PyPI remain denied in each
  sandbox;
- the process sees only the OpenShell credential placeholder, never the real
  secret;
- SWI's canonical executable matches the profile;
- OmegaJev can return only an offered key;
- the kernel still issues the final acceptance/refusal receipt;
- Stop StickerBook tears the system down without agent cooperation.
