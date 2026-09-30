# Local powered development (2026-09-29)

For the optional speech-only parallel response, see
[Conversation acknowledgement](CONVERSATION_ACKNOWLEDGEMENT.md). It is off by
default, adds a separate OpenRouter call, and does not change the Omega goal loop.

Ordinary Docker is a local development path. OpenShell remains the desired
hardened runtime. The browser calls the host bridge/kernel; the host separately
calls OmegaLLM and OmegaJev on loopback. Neither agent receives the host kernel
or mutation authority. Public GitHub Pages continues using its mechanical stub.
Governed local play exposes the six existing pages with separate page worlds.
Both agents now retain separate native Omega memory; see
[Omega agent memory](OMEGA_AGENT_MEMORY.md) for scope and live qualification.

## Shared RPC state defect

Omega executes the channel using `spec_from_file_location` / `exec_module`
without registering it in `sys.modules`. Providers normally import
`stickerbookrpc`, executing the same source again. Channel role and provider
readiness previously belonged to different module objects.

`runtime/omega/stickerbookrpc_state.py` now owns one `RpcState` object. Both
executions of the channel import that module normally by the same canonical
name from Omega's channels search path. Python caches that state module once
per interpreter. All locks, request staging, readiness, role, and server
lifecycle state are shared; the HTTP implementation and public RPC functions
remain in the channel. Role mismatch validation remains intact. There is no
persistence of RPC process state, IPC, global registry in builtins, or change
to Omega's loader. The separate native memory backend persists agent experience.

`web/tests/test_rpc_module_identity.py` reproduces the unregistered plugin load,
starts the real HTTP channel, normally imports the provider-facing module, and
checks readiness and role over HTTP for both roles. It also exercises request
delivery/result staging across the two objects, rejects a mismatched role, and
starts a subprocess that proves fresh empty state. It checks the existing
12-decision host budget and rejects 13.

Live qualification additionally exposed and fixed:

- The MeTTa return-skill filename did not match `stickerbookrpc-skill` in the
  plugin declarations, leaving `sb-return` unevaluated.
- The OmegaLLM plugin name did not match `stickerbook_llm.py`.
- RPC Jev instructions referenced legacy `operator_intent` instead of the
  actual bounded `goal` and `scene` fields.
- RPC validation allowed six turns while existing host patterns and powered
  trajectories have twelve-decision caps. The transport now accepts that cap;
  host motor/decision budgets and execution behavior are unchanged.

## Start

Build the pinned baseline using the existing repository instructions first.
Then, from WSL with Docker available:

```sh
sh runtime/start-local-docker.sh /absolute/path/jev.env /absolute/path/llm.env
STICKERBOOK_OMEGA_LLM_URL=http://127.0.0.1:8761 \
STICKERBOOK_OMEGA_JEV_URL=http://127.0.0.1:8762 \
STICKERBOOK_PORT=8757 python3 web/bridge.py
```

The Jev env file needs only `OPENROUTER_API_KEY`. The separate LLM file may
contain `ASI_API_KEY` and `OPENROUTER_API_KEY`, preserving the configured
OpenRouter fallback. Use existing local credentials; never commit these files.
`.dockerignore` excludes env files and local runtime artifacts from build
contexts. Credentials are injected at container creation, never baked into
images. Updating an environment variable requires recreating the affected
container. The launcher recreates both agents; for a credential-only LLM
refresh, recreate only `stickerbook-llm-local` with the same run restrictions.

The launcher builds derived `:local` images and uses explicit `jevTransport=direct`.
Internal RPC binding is explicitly `0.0.0.0` for Docker publication; the default
channel binding remains `127.0.0.1` for the hardened runtime.

## Verified containment

Both containers run as `65534:65534`, with all capabilities dropped,
`no-new-privileges`, a read-only root filesystem, 2 CPU, 2 GiB memory, and a
256 PID limit. No bind mounts, repository mount, Docker socket, host network,
or privileged mode are used. Writable locations are explicit:

| Location | Storage |
| --- | --- |
| `/tmp` | 128 MiB |
| `/PeTTa/chroma_db` | Separate per-agent Docker named volume, uid/gid 65534 |
| `/PeTTa/repos/Omega/memory` | Separate per-agent Docker named volume, uid/gid 65534 |

The `/tmp` tmpfs is `nosuid,nodev`. Native memory survives container recreation;
typed record caps are not volume disk quotas. Agents use separate bridge networks
`stickerbook-jev-local` and `stickerbook-llm-local`; they do not coordinate with
each other. Published ports are exclusively `127.0.0.1:8762` and
`127.0.0.1:8761`. The host bridge coordinates both.

Direct provider egress is a local containment downgrade: provider credentials
exist in each relevant agent's environment, and Docker does not reproduce
OpenShell's credential replacement, network mediation, or its policy boundary.
Docker daemon administrators can inspect container credentials. Read-only
filesystems and finite kernel authority do not remove those gaps.

## Live results

Both health endpoints report `ok: true` and their correct role. OmegaJev uses
OpenRouter's Decisions API with `typesafe/jev-1.13`. One offered-key selection
returned `hop`, validated against the host table, in 0.711 seconds (another
run: 0.569 seconds).

OmegaLLM's sponsored lane uses the existing `asicloud` configuration with locked
`minimax/minimax-m3`; a frog-hop turn returned the bounded animate goal in
9.518 seconds. The host accepted the resulting Jev hop receipt; total time was
11.523 seconds. OpenRouter / `z-ai/glm-5.2` was independently exercised first:
language turn 1.436 seconds, whole semantic action 3.483 seconds.

| Product check | Result | Wall time |
| --- | --- | --- |
| OpenRouter discrete remember | Saved one-step `happy dance` | 1.959 s |
| OpenRouter discrete perform | Completed; one accepted landing step | 2.294 s |
| ASI discrete remember | Saved one-step `happy dance` | 14.802 s |
| ASI initial discrete perform | Model claimed memory absent; no goal/mutation | 31.370 s |
| ASI final discrete remember | Saved powered one-step hop demonstration | 6.176 s |
| ASI clarified discrete perform | Completed; one accepted hop, Jev 0.538 s | 7.296 s |
| ASI bind demonstrated path | Bound current path to frog; no motor decisions | 5.986 s |
| ASI reference trajectory | Resolved subject frame; no motor decisions | 9.176 s |
| ASI short powered trajectory | Completed; two accepted east moves | 14.330 s |

The ASI trajectory spent 12.503 seconds translating language, then made two Jev
decisions taking 0.531 and 1.277 seconds. The frog moved from `(0.50,0.50)` to
`(0.56,0.50)` to `(0.62,0.50)`. The host marked completion within its existing
reach tolerance of the last demonstrated waypoint `(0.68,0.50)`. The 500 ms
demonstration is a geometric course, not a promise to replay its timing.
Position evidence shows two discrete rightward steps separated by provider
latency. No browser was connected to the automation surface, so visual
appearance was not directly verified.

The clarified ASI replay used the exact saved label and asked the host to
resolve it. It followed a single-decision powered landing reset, making the
remembered hop legal again. Another language-driven preparation had alternated
hop/land until its existing six-turn cap, illustrating why model choice and
accepted kernel receipts must be reported separately from reassuring replies.

Earlier refused runs were diagnostic, not successful product checks: a
remember request without eligible gesture history was refused, a landing
replay when landing was unavailable was refused, and a path referenced after
its one-turn carry was consumed was unavailable. Testing then used a real
powered discrete demonstration, a legal replay starting state, and a fresh
current path. These existing lifetime/authority rules were preserved.

The host bridge is available on `http://127.0.0.1:8757/` (8756 was already in
use). Its `/api/state` reports conversational agent and Jev controller true.
The live HTTP bridge is selected to the locked ASI lane; "Make the cow chew"
completed in 12.079 seconds with an accepted host kernel chew receipt followed
by NOOP. OpenRouter remains available in the responsible-adult selector.
Validation: 428 web tests, 40 Jev core tests, and 81 authority core tests pass
(549 total). No governed page expansion or drag-mechanics retesting was done.
