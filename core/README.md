# stickerbook_core — the authority kernel

The single gate every world mutation passes through, for every principal.

Headless on purpose: **no renderer, no browser, no network, no model, no
dependencies beyond the Python standard library.** If the security model can
be tested without pixels, the seam is in the right place.

```
python -m unittest discover -s tests      # 53 tests, ~3ms
```

## What it is

```
core/
  stickerbook_core/
    model.py    data only  — Principal, StickerInstance, Command, Receipt,
                             AuthorityProfile, the action enumeration
    kernel.py   the gate   — effective_tools, available_actions, propose
  tests/
    test_authority.py      — named against ../SECURITY.md §26
```

The governing rule is [`../SECURITY.md`](../SECURITY.md). This package is its
implementation; that document is authoritative where the two disagree.

## The shape

```
principal + proposed command
        ↓
effective_tools()   profile ceiling ∩ own tools ∩ every ancestor's delegable
        ↓
validate            known action · schema · bounded args · ownership ·
                    revision · budget · expiry
        ↓
apply               the only mutation path; bumps the world revision
        ↓
Receipt             accepted or rejected, always, with an explicit reason
```

Two ways in, both fully validated:

* `propose_key(principal, key, ...)` — the agent path. The host generates a
  context-dependent table of **only currently legal** actions; the agent
  selects a key and never constructs a command. This is the OmegaJev
  frozen-table pattern lifted to StickerBook.
* `propose(command)` — the raw path, for a renderer, bridge or browser. The
  caller is never the trust anchor: a modified browser may propose anything
  and the kernel still refuses.

## Deployment authority profiles

The same kernel has different mechanically enforced postures:

| Profile | Agent authority |
|---|---|
| `pages-demo` | **∅** — no action any agent principal can take |
| `local-single-agent` | bounded sticker actor |
| `local-multi-agent` | several agents with an explicit authority graph |

`pages-demo` is not the powered system with a flag turned off. It is an empty
intersection applied before every other check, so an agent registered with
*every* tool still has no authority. Humans are unaffected.

## Who uses it

OmegaJev is coupled to this kernel in `jevActionSet=stickerbook` mode: Jev
selects a key from `available_actions()`, and Omega executes a single
zero-argument command whose only effect is to hand the staged key here. See
`../jev/SECURITY.md` §3b and `../jev/tests/verify_kernel_coupling.py`.

## What this does not prove

The kernel proves the model is coherent and enforceable. It does **not** prove
any running system is safe. There is still no renderer, no browser and no
human interface, and the coupled path is exercised by one agent, one page and
two stickers. Each future integration must be re-verified against these tests
rather than assumed to inherit them.

The tests are mutation-checked: disabling the ownership check fails 7 of them,
disabling the profile ceiling fails 6.
