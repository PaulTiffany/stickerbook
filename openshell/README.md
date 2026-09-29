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

StickerBook is pinned to:

- OpenShell release `v0.1.2`
- commit `6648bd0c290efbc41ba131ee9831ee45cd431f94`
- release date 2026-09-28

The pin lives in `PIN.env`. The installer is fetched by immutable commit and
is instructed to install that exact release:

```bash
bash openshell/install-pinned.sh
```

The normal StickerBook launcher performs this check itself. Manual installation
is therefore an operator/debug path rather than a normal child-facing startup
step.

## Two sandboxes, not one ambient agent

The powered architecture uses separate sandbox identities:

- **OmegaLLM**: child language -> reply + optional bounded semantic goal
- **OmegaJev**: fresh bounded world view + finite host action table -> one key

They do not share an authority object, repository mount, writable source tree,
provider instance, or general Internet connection.

Base policies:

- `policies/omega-llm.yaml`
- `policies/omega-jev.yaml`

Both contain `network_policies: {}`. Provider egress is contributed only by
explicit provider profiles.

OmegaJev attaches one required profile:

- `providers/openrouter-omega-jev.yaml` — Jev Decisions API.

OmegaLLM may attach several independently credentialed profiles:

- `providers/asicloud-omega-llm.yaml` — Sponsored ASI Cloud;
- `providers/anthropic-omega-llm.yaml` — Anthropic;
- `providers/openai-omega-llm.yaml` — OpenAI;
- `providers/openrouter-omega-llm.yaml` — OpenRouter;
- `providers/asione-omega-llm.yaml` — ASI:One.

A profile is attached only when its OpenShell provider instance exists or its
credential is available for first creation. All profiles bind egress to the
same kernel-resolved SWI executable
`/usr/lib/swipl/bin/x86_64-linux/swipl`; each permits only its declared API
host. The boot launcher independently checks `readlink -f` in both built
images and refuses to start if the identity differs.

Real provider credentials remain at their OpenShell provider boundaries. The
OmegaLLM sandbox receives only OpenShell placeholders for the configured
providers. The browser receives neither placeholders nor real secrets.

## The live service seam

Both roles remain actual Omega loops. StickerBook adds one narrow Omega
communication channel, `runtime/omega/stickerbookrpc.py`, plus one fixed
zero-argument skill, `sb-return`.

```text
host bridge --loopback HTTP--> stickerbookrpc channel
                                |
                                v
                           normal Omega loop
                                |
                    role-specific bounded provider
                                |
                                v
                            (sb-return)
                                |
host bridge <--bounded JSON-----+
```

The channel never parses free-form Omega output into authority. A provider may
stage one bounded JSON response; Omega can only execute `sb-return` in the
service role.

OmegaLLM's image contains no StickerBook authority kernel and no Jev provider.
OmegaJev's live RPC mode receives the host action-description table and maps
every offered key to the same fixed executable literal `sb-return`. The
selected key remains data, is returned to the host, checked again against the
current table, and is then separately judged by the kernel.

The host forwards are bound only to:

- `127.0.0.1:8761` — OmegaLLM
- `127.0.0.1:8762` — OmegaJev

The browser talks to `web/bridge.py`, not directly to those ports.

## Normal start and stop

The intended operator path is at the repository root:

- **`Start StickerBook.cmd`**
- **`Stop StickerBook.cmd`**

The Windows start wrapper enters WSL and runs `runtime/start.sh`. That script
verifies Docker/OpenShell, prepares the exact pinned Omega baseline if needed,
builds current role images, checks canonical SWI identity, creates or reuses
the two role-specific OpenShell providers, starts/health-checks both sandboxes,
then starts the authority bridge with explicit loopback runtime URLs.

On first provider creation only, the launcher may prompt for
`OPENROUTER_API_KEY` with hidden input. It does not save the secret in the
repository or runtime state.

For direct operator/debug use, the role launchers are:

```bash
bash openshell/run-omega-llm-service.sh
bash openshell/run-omega-jev-service.sh
```

The older `run-omega-jev.sh` remains the original standalone OpenShell Jev
slice and is not the browser service launcher.

Shutdown is external to the agents: the bridge process is stopped, local
forwards are stopped, and both named sandboxes are deleted. Neither Omega loop
must cooperate.

See `runtime/README.md` for the full lifecycle.

## Voice-first relationship

OpenShell does not add a voice agent. Browser/device STT converts speech to the
same text conversation request used by accessibility chat. OmegaLLM replies
through that one seam, and browser/device TTS may speak the returned text.

Voice I/O has no world-mutation authority. An OmegaLLM goal must still pass
host validation -> OmegaJev finite selection -> kernel authorization.

## Current proof boundary

**IMPLEMENTED + CI/mechanically checked, NOT YET LIVE-HOST VERIFIED.**

Implemented in the branch:

- immutable OpenShell release/commit pin;
- separate no-network base policies and provider identities;
- canonical SWI executable binding in both provider profiles;
- non-root OmegaLLM and OmegaJev OpenShell images;
- explicit OpenShell provider-placeholder transports;
- adult-selectable OmegaLLM provider routing across configured ASI Cloud,
  Anthropic, OpenAI, OpenRouter and ASI:One profiles;
- real Omega RPC channel + fixed `sb-return` skill;
- loopback-only host runtime adapters;
- OmegaJev browser-service mode over finite host-owned choices;
- bounded OmegaLLM conversational provider;
- one-command Windows/WSL start, stop and status lifecycle;
- browser voice/text regression contract;
- static CI contract checks in `openshell/verify.py`.

Still requiring a real local deployment proof:

- OpenShell v0.1.2 startup on the actual WSL2/Docker Desktop host;
- successful OpenRouter/Jev call and successful calls through whichever
  OmegaLLM provider profiles are configured/selected;
- observed canonical SWI identity in the running sandbox;
- denial of unrelated destinations such as GitHub and PyPI;
- confirmation that only the provider placeholder, not the real secret, is
  visible to the workload;
- end-to-end child voice/text -> OmegaLLM -> OmegaJev -> kernel receipt;
- independent Stop StickerBook teardown.

Static artifacts do not inherit the **VERIFIED** status of the older
split-container OmegaJev gateway experiment.

## Operator rules

OpenShell policy is operator-owned.

- no agent-driven policy auto-approval;
- no read-write StickerBook repository mount;
- no Docker socket inside an agent sandbox;
- no policy/provider/orchestration mutation from either Omega loop;
- no repository credential in play;
- `--approval-mode manual` on service creation.

A proposed policy expansion is still only a proposal. **Capability is not
authority.**
