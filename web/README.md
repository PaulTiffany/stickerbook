# web — StickerBook browser surface

The browser surface is shared by two intentionally different worlds:

- **localhost**: browser gestures are proposals to the Python authority kernel;
- **GitHub Pages**: a deterministic mechanical world with no live agent,
  credential, kernel, or privileged backend.

The renderer and child-facing navigation are the same in both profiles.

## Navigation

StickerBook is image-forward rather than app-menu-forward:

```text
cover
  |
  v
page gallery  ---->  page creator / uploader
  |
  v
active page
  |
  +---- home button -> cover
  |
  +---- sticker-library button -> popup over the page
```

The title page is one large visual hit target. Touching it opens the page
gallery. A small bottom-right title-page target is reserved for responsible
adult / developer controls.

The gallery is thumbnail-first. In the public mechanical profile it is driven
by the asset manifest and currently exposes **Farm, Beach, Park, and Space**,
plus a **+ Make a page** tile. Each public demo page has independent in-memory
StickerInstances for the current session.

The governed localhost profile is intentionally stricter: a visual page asset
does not become a governed page until the authority kernel has page state for
it. Today that means Farm remains the connected governed page.

## Library → sheet → page

The bottom hotbar is the child's working sticker sheet, not the complete
inventory. It is flush to the screen edges. In landscape, StickerBook reserves
a bottom control strip for it so the hotbar does not obscure the playable page
image. In portrait, the image remains maximized while preserving the complete
native composition.

The cover, page stage, and gallery thumbnails avoid decorative paper margins.
Full pages stay uncropped; gallery thumbnails may crop slightly because they
are previews rather than the playable scene.

```text
STICKER LIBRARY
      |
      | drag / tap
      v
WORKING SHEET (hotbar)
      |
      | drag
      v
ACTIVE PAGE
```

The sticker library floats above the page while leaving the hotbar available,
so a child can drag a sticker thumbnail from the larger library into the
working sheet.


When a local conversational runtime is connected, the child-facing language
interface is voice-first: a responsible adult may enable a small push-to-talk
microphone for the current session. The text fallback stays inside the
responsible-adult panel.

The hotbar has three regions:

```text
+----------------------------------------------------+
| home |        working sticker sheet        |  +   |
+----------------------------------------------------+
```

- **home** returns directly to the title page;
- the **middle** is the current small set of stickers;
- **+** opens the larger sticker library.

The library also contains a **+ Make a sticker** path. Both page and sticker
creators expose **Upload** and **Make with StickerBook**. The assisted path is
an explicit seam for a future local creator agent; the public Pages demo does
not fake an agent connection.

Sticker draft requests target asset schema v2: a validated visual package with
an idle clip and optional behavior clips containing one or many related frames.
The creator seam returns drafts only and does not mutate the authority kernel.

## Page gestures

- drag from hotbar to page: place a StickerInstance;
- drag a placed sticker: move it;
- drag a placed sticker back to the hotbar: remove it from the page;
- while the library is open, drag a hotbar sticker back into the library: remove it from the working sheet;
- double-tap: toggle the definition's declared mechanical animation.

Direct human manipulation suspends animation while the sticker is held.

## Conversational / creator agent seams

The browser has two non-authoritative agent endpoints:

- `/api/agent/converse` returns language;
- `/api/creator/draft` returns proposed asset/page draft metadata.

Neither endpoint is a kernel command path. The runtime receives the fixed
browser principal and a JSON scene view, not the kernel object. Machine actions
still belong on the legal-choice / Jev / kernel path.

The shipped `agent_runtime.py` is disabled and inert. It advertises no agent
capabilities until a local runtime adapter is explicitly connected.

## Governed localhost path

```text
pointer gesture
    -> browser POSTs a proposal:
         /api/place
         /api/propose-move
         /api/remove
         /api/animate
    -> bridge validates request shape and fixes the actor
    -> authority kernel validates values, ownership, revision, budget
    -> kernel accepts or refuses and issues a Receipt
    -> browser redraws from authoritative state
```

The browser is trusted to report pointer input and which sticker was grabbed.
It is not trusted to choose identity, bypass ownership, establish success, or
mutate authoritative state.

Add `?dev=1` for revision, acting principal, last verdict, and receipt stream.

**If Python changes, restart the bridge.** Static HTML/CSS/JS are read per
request, but the kernel is imported once at startup.

```bash
cd web
python bridge.py
# http://127.0.0.1:8756/
```

Add `?mechanical=1` to exercise the same public mechanical adapter locally.

## Page model

The connected farm page still separates passive scenery from governed objects:

```text
farm page
├── passive backdrop   barn · pond · tree · fence
└── StickerInstances   governed, owned, receipt-producing
```

Positions are page-relative fractions. Pixels remain presentation and input
detail, never authority.

## Tests

```bash
cd web
python -m unittest discover -s tests
```

The test suite runs a real bridge on an ephemeral loopback port to exercise
the browser/kernel seam. GitHub Actions also syntax-checks `static/app.js`.
