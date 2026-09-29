# StickerBook + OpenShell

This directory is the deployment-containment layer for the powered localhost
runtime. It does **not** replace StickerBook's authority kernel.

The invariant remains:

```text
child -> OmegaLLM -> bounded semantic goal -> OmegaJev -> typed action key
                                                     |
                                                     v
                                          StickerBook kernel
                                          authorize / apply / receipt
```

OpenShell sits around the live Omega processes. It constrains filesystem access,
process identity, provider credentials, and network egress. It does not decide
which sticker action is legal.

## Pin

StickerBook is pinned to the stable OpenShell release:

- release: `v0.1.2`
- commit: `6648bd0c290efbc41ba131ee9831ee45cd431f94`
- release date: 2026-09-28

The pin lives in `PIN.env`. Do not replace it with `main`, `dev`,
`latest`, or another moving alias.

The installer is fetched by immutable commit and is told to install the exact
release tag:

```bash
bash openshell/install-pinned.sh
```

OpenShell documents Windows with WSL2 as experimental. StickerBook's tested host
already uses Windows 11 + WSL2 Ubuntu + Docker Desktop, so the integration is
kept explicitly local and inspectable rather than treated as a production
deployment claim.

## Two sandboxes, not one ambient agent

The architecture reserves separate policies and provider identities for:

- `OmegaLLM`: child language -> bounded semantic goal
- `OmegaJev`: bounded world view + finite action table -> typed action key

They must not share an ambient writable filesystem, an authority object, or a
general Internet connection merely because they cooperate on one turn.

The policy files are:

- `policies/omega-llm.yaml`
- `policies/omega-jev.yaml`

Both base policies contain **no network allow rule**. OpenRouter access is added
only by the matching OpenShell provider profile, which restricts the destination
to `openrouter.ai:443` and the workload binary to SWI-Prolog.

The provider profiles are:

- `providers/openrouter-omega-llm.yaml`
- `providers/openrouter-omega-jev.yaml`

The real OpenRouter secret remains at the OpenShell boundary. A sandbox sees
only the OpenShell provider placeholder and can use it only through the
policy-approved provider route.

## OmegaJev runnable slice

The first live slice is OmegaJev, because StickerBook already has a bounded Jev
provider experiment and authority-kernel coupling.

Build the existing experiment image first, then run:

```bash
bash openshell/run-omega-jev.sh
```

The script:

1. builds `stickerbook-omega-jev:openshell` from
   `jev/Dockerfile.openshell`;
2. lints/imports the StickerBook-specific OpenRouter provider profile;
3. creates an OpenShell provider from the host's `OPENROUTER_API_KEY`;
4. creates the Jev sandbox with `policies/omega-jev.yaml`;
5. starts Omega with `jevTransport=openshell`.

The OpenShell image has a non-root `USER 65534:65534` and a separate
entrypoint. It does not start the older nginx credential gateway. The existing
Docker gateway path remains in the repository as a previously verified
experiment and fallback test path; the OpenShell transport is an additional
deployment mode, not a rewrite of the Jev decision semantics.

## Current proof boundary

Implemented in this branch:

- immutable OpenShell release/commit pin;
- separate OmegaLLM and OmegaJev policies;
- separate provider profiles;
- non-root OmegaJev OpenShell image;
- explicit `jevTransport=openshell` transport;
- provider-placeholder credential use;
- static CI contract checks in `openshell/verify.py`.

Not yet established:

- a live OmegaLLM process behind `web/agent_runtime.py`;
- a live OmegaJev process behind `web/jev_runtime.py`;
- OpenShell-enforced inter-process messaging between those two live loops;
- end-to-end browser -> OmegaLLM -> OmegaJev -> kernel tests;
- runtime proof that the exact SWI-Prolog canonical executable path in the
  built image matches the provider binary allowlist.

That last check matters because OpenShell matches the kernel-resolved executable
path, not merely a symlink name. Before treating the provider policy as
verified, inspect the built sandbox with `readlink -f $(command -v swipl)`
and tighten the profile to that canonical path if necessary.

## Operator rules

OpenShell policy is operator-owned. The agent gets no repository-write,
policy-write, shell, browser-automation, plugin-installation, or arbitrary
network authority from this integration.

Do not enable agent-driven policy auto-approval. A proposed policy expansion is
still only a proposal. Human/operator authorization remains outside both Omega
loops.

Do not mount the StickerBook repository read-write into either live agent
sandbox. Runtime state belongs in the explicitly writable memory/temp paths,
and world mutation still occurs only through the host authority kernel.
