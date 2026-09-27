# web — the farm page

A localhost, human-only renderer for one StickerBook page, backed by the
existing Python authority kernel in [`../core`](../core).

```bash
cd web && python bridge.py          # then open http://127.0.0.1:8756/
```

No dependencies beyond the standard library. No agent, no model, no
credential, no outbound network: the server binds loopback only.

## The path a drag takes

```
pointer drag
    -> browser POSTs {sticker, command_id, point, based_on_revision}
    -> bridge snaps the POINT to a host-owned slot        (farm.snap_to_slot)
    -> bridge builds the Command with a FIXED actor       (bridge.py)
    -> kernel validates ownership, slot, revision, budget (../core)
    -> kernel accepts or refuses, and issues a Receipt
    -> bridge returns receipt + authoritative state
    -> browser redraws from that state
```

## What the browser is trusted with

Reporting where the pointer went, and which sticker was grabbed. That is all.

## What it is explicitly not trusted with

| | Enforced by |
|---|---|
| Its own identity — an `actor` field in the body is ignored | `BROWSER_PRINCIPAL` is a constant in `bridge.py` |
| Naming a slot | it sends a point; `farm.snap_to_slot` chooses |
| Choosing an action | the endpoint issues exactly one command type |
| Being believed about success | every response carries authoritative state, and the renderer draws that, never its own proposal |

A refused drag is not an error state. The cow is yours; the butterfly belongs
to an agent principal, and the kernel refuses to let you move it even though
no agent is running. Watch the receipts panel: that refusal is the boundary
working.

## Page model

```
farm page
├── passive backdrop        barn · pond · tree · fence
│     scenery. Not kernel objects. Nothing can act on them, so the
│     authority kernel is never told they exist.
└── stickers                cow-1 (human) · butterfly-1 (agent)
      governed. Owned. The only things any principal can act on.
```

Slots (`by-the-barn`, `under-the-tree`, `by-the-pond`, `by-the-fence`,
`in-the-field`) are host-owned named positions and the only legal
destinations. Pixel coordinates exist here and in the browser as presentation
and input detail; they are never authority.

## Tests

```bash
cd web && python -m unittest discover -s tests      # 28 tests
```

They run a real server on an ephemeral loopback port, because the seam is
the thing being tested. UI behaviour is not evidence. Test classes map to the
questions the milestone set out to answer, including that the bridge contains
no ownership logic of its own — asserted by reading its source.
