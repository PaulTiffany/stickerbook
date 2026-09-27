# StickerBook

An experiment in giving an AI agent bounded authority over a small creative
world.

StickerBook is intended to become a space where a human — potentially a child
— and an agent place and animate stickers together. The reason it exists as a
research project rather than an app is the hard part: **a child must not have
to supervise an AI agent for the system to stay safe.** The boundary has to be
architectural.

> **Capability is not authority.**
> More reasoning, memory, confidence, specialization, recursion or tool skill
> must never imply more authority.

## What exists today

Two components. They are connected to each other, and to nothing else.

| | |
|---|---|
| **`core/`** | A headless **authority kernel**: principals, sticker ownership, revisions, receipts, delegation ceilings, agent budgets, and per-turn generated legal-action tables. No renderer, no network, no model, standard library only. 53 tests. |
| **`jev/`** | **OmegaJev**: an experiment replacing SingularityNET Omega's generative inference step with typed discriminative decisions (OpenRouter's Decisions API / Jev). The agent selects a key from a kernel-generated table; the kernel decides. 40 unit tests plus 4 container/host verification suites. |

## What does not exist yet

No renderer. No browser UI. No GitHub Pages build. No sticker editor, no
multi-agent delegation in a running system, no persistence. The page used in
experiments is a passive backdrop, two backdrop features, and two stickers.

Read the status markers in [`SECURITY.md`](SECURITY.md) before treating any
statement there as a description of running software. It distinguishes
*architectural requirement*, *implemented mechanism*, *verified test* and
*known gap*, and that distinction is load-bearing.

## The shape of it

```
kernel generates the legal actions   ->  {"MOVE:butterfly-1:centre": Command, ...}
the agent selects a KEY              ->  "MOVE:butterfly-1:centre"
the host stages it                   ->  single-use slot; staging is not authorization
Omega executes one fixed command     ->  (sb-apply)   <- zero arguments
the kernel decides                   ->  Receipt(accepted, actor, object, revision)
```

The agent never constructs a command, an object id, a position or an
animation name. In this mode Omega's entire executable vocabulary is one
command with no argument position at all.

## Running the tests

The kernel needs nothing but Python:

```bash
cd core && python -m unittest discover -s tests      # 53 tests
cd jev  && python -m unittest discover -s tests      # 40 tests
```

The OmegaJev verification suites need Docker and a built image; see
[`jev/SECURITY.md`](jev/SECURITY.md) §10 for the exact commands, and
[`jev/EXPERIMENT.md`](jev/EXPERIMENT.md) for what has actually been observed,
including results that were later retracted and why.

Upstream PeTTa/Omega is not vendored here. The exact commits tested are
recorded in [`jev/VERSIONS.txt`](jev/VERSIONS.txt).

## Documents

| File | What it is |
|---|---|
| [`SECURITY.md`](SECURITY.md) | The constitutional security model. Binding on all work here. |
| [`core/README.md`](core/README.md) | The authority kernel. |
| [`jev/SECURITY.md`](jev/SECURITY.md) | OmegaJev's enforced boundaries, with the evidence for each. |
| [`jev/EXPERIMENT.md`](jev/EXPERIMENT.md) | What was tried, what happened, what is still unknown. |
| [`docs/MEDIUM.md`](docs/MEDIUM.md) | What StickerBook is as a medium, and why the medium is the experiment. |
| [`NOTICE`](NOTICE) | Third-party attributions, licenses, and the modifications made to upstream Omega. |

## Status

Early and deliberately small. The security model is implemented and tested;
the product is not built. Nothing here is packaged for use by anyone else
yet, and the child-facing invariant — the one that matters most — is the
least tested, because no child-facing surface exists.

## Built on

This project is a small experiment layered on substantial work by others.

| Project | | |
|---|---|---|
| [SingularityNET Omega](https://github.com/singnet/Omega) | SingularityNET Foundation | Apache-2.0 |
| [PeTTa](https://github.com/trueagi-io/PeTTa) | Patrick Hammer | MIT |
| [petta_lib_chromadb](https://github.com/patham9/petta_lib_chromadb) | Patrick Hammer | no license file upstream |
| [OpenRouter](https://openrouter.ai) Decisions API | | service |
| TypeSafe Jev (`typesafe/jev-1.13`) | | model, via OpenRouter |
| [SWI-Prolog](https://www.swi-prolog.org), [nginx](https://nginx.org) | | base images |

Omega's source is **not** vendored here; it is cloned locally and excluded
from this repository, and the experiment image applies a small set of
documented modifications to it — including one upstream bug fix. Those
modifications are enumerated in [`NOTICE`](NOTICE), as Apache-2.0 requires.
The exact upstream commits tested are in
[`jev/VERSIONS.txt`](jev/VERSIONS.txt).

## License

MIT, © 2026 Paul Carver Tiffany III. See [`LICENSE`](LICENSE).
Third-party attributions are in [`NOTICE`](NOTICE).
