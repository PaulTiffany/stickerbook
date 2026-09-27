# web — the farm page

A localhost, human-only sticker book page, backed by the existing Python
authority kernel in [`../core`](../core). See
[`../docs/MEDIUM.md`](../docs/MEDIUM.md) for what this is trying to be.

Maximal play surface, minimal persistent chrome. The only permanent
interface is the page and the hot-bar beneath it:

    +-------------------------------+
    |                               |
    |          ACTIVE PAGE          |
    |                               |
    +---------------------------+---+
    |  butterfly cow duck hen + | = |
    +---------------------------+---+
        sticker hot-bar          menu

The grammar is four gestures and nothing else:

    drag a sticker      "I want this here."
    double-tap          "Bring this to life."
    +                   "I want another thing."
    menu                "I want another world, or the book."

Navigation and the sticker library open as sheets that REPLACE play rather
than shrinking it. On a phone the answer to limited space is less visible
machinery, not smaller machinery. Nothing numeric is shown.

Add `?dev=1` for the proof harness: revision, acting principal, the last
verdict, and the receipt stream.

**If you change Python, restart the bridge.** Static files are read per
request, so the browser picks up HTML/CSS/JS immediately -- but the kernel
is imported once at startup. A running bridge will happily serve a new page
on top of old logic. Starting a second bridge now fails loudly rather than
leaving the old one answering.

```bash
cd web && python bridge.py          # then open http://127.0.0.1:8756/
```

No dependencies beyond the standard library. No agent, no model, no
credential, no outbound network: the server binds loopback only.

## The path a drag takes

```
pointer drag
    -> browser POSTs a proposal:
         /api/place        {asset, command_id, point}    from the tray
         /api/propose-move {sticker, command_id, point}   around the page
         /api/remove       {sticker, command_id}          back to the tray
         /api/animate      {sticker, command_id}          bring it to life
    -> bridge validates the SHAPE and fixes the actor      (bridge.py)
    -> kernel validates the VALUES: position, ownership,
       revision, budget                                    (../core)
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
| The position it claims | the kernel checks the coordinate is on the page |
| Choosing an action | each endpoint issues exactly one command type |
| Being believed about success | every response carries authoritative state, and the renderer draws that, never its own proposal |

A refused drag is not an error state: the sticker simply does not go, which
is what a real sticker does when it will not stick. In `?dev=1` the receipt
says why.

## Page model

```
farm page
├── passive backdrop        barn · pond · tree · fence
│     scenery. Not kernel objects. Nothing can act on them, so the
│     authority kernel is never told they exist.
└── stickers                cow-1 (human) · butterfly-1 (agent)
      governed. Owned. The only things any principal can act on.
      The tray offers cow, butterfly, duck and hen, in unlimited supply.
```

Positions are coordinates, fractions of the page. A sticker may go
anywhere on it. Pixel values are presentation and input detail, never
authority.

## Tests

```bash
cd web && python -m unittest discover -s tests      # 52 tests
```

They run a real server on an ephemeral loopback port, because the seam is
the thing being tested. UI behaviour is not evidence. Test classes map to the
questions the milestone set out to answer, including that the bridge contains
no ownership logic of its own — asserted by reading its source.
