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
by the asset manifest and currently exposes **Farm, Beach, Playground, and
Space**, plus a **+ Make a page** tile. Each public demo page has independent
in-memory StickerInstances for the current session.

The governed localhost profile is intentionally stricter: a visual page asset
does not become a governed page until the authority kernel has page state for
it. Today that means Farm remains the connected governed page.

## Library → sheet → page

The bottom hotbar is the child's working sticker sheet, not the complete
inventory. It is flush to the screen edges and owns a reserved bottom control
strip in both orientations, so it never obscures the governed page surface.

Built-in page artwork is authored directly for that remaining browser rectangle:
**1916 × 717** landscape and **941 × 1574** portrait.
School and Theater ship as text-SVG page assets at those same canonical sizes; they can later be replaced by manually uploaded raster artwork without changing page semantics. The title/cover uses
separate **1916 × 821** and **941 × 1672** artboards because it does not share
space with the hotbar.

The cover, page stage, and gallery thumbnails avoid decorative paper margins.
Playable pages use `meet` fitting so the whole coordinate surface remains
present; gallery thumbnails may crop slightly because they are previews rather
than the governed play surface.

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
microphone for the current session. The optional translucent play-surface text
chat is the single text projection of that same conversation; there is no
separate adult-panel chat box.

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
creators expose **Upload** and **Make with StickerBook**. The installed sticker
catalog is no longer assumed to fit comfortably in one tiled view: the library
has deterministic text search over names, aliases, themes, categories and tags,
plus world/theme and category chips. Search is local catalog filtering, not a
model call. The current built-in catalog contains 33 sticker definitions / 132
initial pose sprites across Farm, Beach, Playground, Space, School, and Theater.

Page uploads accept SVG, PNG, JPEG/JPG, and WebP. On public GitHub Pages the
selected file remains a local browser preview and is never sent to a model. In
powered local mode an operator may separately enable the page-image gateway.
The original upload is then used as the reference for two image-edit jobs:
**1916 × 717** horizontal and **941 × 1574** portrait. Their filenames follow
`<name>.<ext>` and `<name>-vertical.<ext>`.

Sticker creator requests still target draft schema v2. Installed built-in
assets now use visual manifest v4: each definition has catalog metadata, a
sprite dictionary, a default/rest clip, behavior clips that compose those
sprites, and bounded scale metadata. The two version numbers describe different
layers: creator draft interchange versus installed visual assets.

The current built-ins contain 76 definitions with four initial pose sprites
each. Those sprites are a starter pose set, not a claim that every future
sticker must have exactly four. All creator/image seams return drafts only and
do not mutate the authority kernel or install generated media into a governed
page.

## Page gestures

Bare-page gestures also provide temporary conversational pointing: a tap marks
one normalized point and a drag marks one rectangular region. The mark belongs
only to the child's next voice/text conversational turn, then fades. It is not
saved as page state, is not a sticker, and is not automatically visible to Jev.
Starting on a sticker still grabs the sticker, so object manipulation and
background reference remain distinct.

- drag from hotbar to page: place a StickerInstance;
- drag a placed sticker: move it;
- drag a placed sticker downward across the hotbar's top edge and release: remove it from the page;
- while the library is open, drag a hotbar sticker back into the library: remove it from the working sheet;
- double-tap: request animation for that sticker; a connected OmegaJev loop
  chooses from the sticker's declared clips, otherwise the deterministic
  mechanical toggle is used.

Hovering a placed sticker never changes its transform or visual position. The
white die-cut border plus the grab cursor are the hover affordances; exact
placement should not move until the child actually drags.

Removal is intentionally a forgiving **bottom-edge gesture**, not a precision
drop target. Once a moved sticker crosses the hotbar's top edge, a release
farther down still means remove, even if pointer capture reports the release
below the hotbar's visible box.

Letterbox/ambient space around the page is not part of the governed page.
Dropping a moved sticker into that space does not clamp it onto the nearest
edge; the browser redraws the last authoritative in-page position instead.
This is especially relevant to short/wide phone-landscape viewports where
small side margins may remain.

Direct human manipulation interrupts the active behavior clip while the sticker
is held. Grabbing a sticker immediately shows the first frame of its declared
rest clip, so the physical sticker itself does not shift under the pointer. The
drag preserves the exact point where the child grabbed it: beginning a drag
never teleports the sticker's center underneath the pointer. Once the move is
accepted, the authoritative clip is the definition's rest clip. A rest clip
may itself contain subtle non-locomotive frame animation. Without OmegaJev,
double-tap/click toggles between that rest clip and the definition's first
active behavior. With OmegaJev connected, the same gesture supplies a one-turn
animation-only choice surface instead.

## Adult / developer controls

The title-page gear opens a deliberately separate **Responsible adult /
developer** panel. It links directly to the project repository at
`https://github.com/PaulTiffany/stickerbook` and exposes conversational
runtime options without mixing those controls into the child's normal play
surface.

When a conversational Omega runtime is connected, an adult may enable
push-to-talk voice and/or an **accessibility text chat**. The text option adds
a translucent, dismissible chat panel near the top of the play surface. It
uses the same `/api/agent/converse` path as voice, can display voice
transcripts while enabled, and does not gain any additional world-mutation
authority.

The public mechanical demo keeps voice disabled but allows the text chat UI to
be opened and exercised. Its replies are fixed mechanical stub text and no
model is called. This lets the accessibility surface be reviewed on GitHub
Pages without pretending that Omega is connected.

The developer receipts panel opened with `?dev=1` has its own **×** control.
Closing it removes the `dev` query flag from the current URL and returns to
the normal child title surface without requiring a manual reload.

## Dual Omega / creator seams

The child-facing agent architecture has two separate Omega loops:

- **OmegaLLM** receives voice/text/deictic context and may return language plus
  one bounded semantic goal.
- **OmegaJev** receives that goal with fresh governed scene state and chooses
  one key at a time from a finite host-generated action surface.

`/api/agent/converse` is therefore not a command endpoint. OmegaLLM cannot
supply coordinates as executable arguments or invoke the kernel. If it attaches
a goal, the host validates the goal, constructs bounded Jev choices, and applies
only a Jev-selected host key through `Kernel.propose_key()`.

The child may also reach OmegaJev without OmegaLLM by double-clicking/tapping a
sticker. That creates a one-turn animation-only goal; Jev may choose only one
declared clip key or NOOP.

Creation remains separate:

- `/api/creator/draft` returns proposed asset/page draft metadata;
- `/api/creator/page-image` accepts a validated raw image upload and, only
  when an operator-enabled local image gateway is present, returns horizontal
  and portrait page-image draft metadata.

Creator/media seams receive no kernel object and cannot install themselves.
The shipped OmegaLLM and OmegaJev runtime adapters remain inert by default, but
may be explicitly attached to the governed loopback services with
`STICKERBOOK_OMEGA_LLM_URL` and `STICKERBOOK_OMEGA_JEV_URL`. Those adapters
refuse non-loopback URLs and carry no provider credential or kernel object.
Public GitHub Pages ships neither Python runtime nor provider credential.

## Governed localhost path

```text
pointer gesture
    -> browser POSTs a proposal:
         /api/place
         /api/propose-move
         /api/remove
         /api/animate
         /api/resize
         /api/facing
    -> bridge validates request shape and fixes the actor
    -> authority kernel validates values, ownership, revision, budget
    -> kernel accepts or refuses and issues a Receipt
    -> browser redraws from authoritative state
```

The browser is trusted to report pointer input and which sticker was grabbed.
It is not trusted to choose identity, bypass ownership, establish success, or
mutate authoritative state.

Assisted play uses the parallel bounded path:

```text
child language -> OmegaLLM goal -> OmegaJev finite choice -> Kernel.propose_key
child double-click ----------------^  (animation-only for one turn)
```

OmegaJev movement is expressed as ephemeral local N/NE/E/SE/S/SW/W/NW steps.
After each selected step StickerBook re-observes authoritative state and builds
a fresh table; OmegaLLM does not precompile a movement sequence.

Add `?dev=1` for revision, acting principal, last verdict, and receipt stream.

**If Python changes, restart the bridge.** Static HTML/CSS/JS are read per
request, but the kernel is imported once at startup.

For the complete powered path, use the repository-root
`Start StickerBook.cmd`; it starts the two OpenShell-contained Omega loops
before attaching the bridge. For bridge-only development:

```bash
cd web
python bridge.py
# http://127.0.0.1:8756/
```

With no runtime URL environment variables, the bridge remains model-inert.
Add `?mechanical=1` to exercise the same public mechanical adapter locally.

### Optional local page-image gateway

Page generation is deliberately a separate process from the bridge. Choose an
OpenRouter image model that supports reference-image editing, then start the
gateway. Exact pixel-size controls vary by model, so StickerBook keeps the
required canvas dimensions in the fixed prompt and mechanically rejects any
returned image that is not exactly 1916 × 717 or 941 × 1574:

```bash
cd web
export OPENROUTER_API_KEY="..."
export STICKERBOOK_OPENROUTER_IMAGE_MODEL="<editing-capable-model>"
python image_gateway.py
```

In another shell, opt the bridge into that loopback service:

```bash
cd web
export STICKERBOOK_IMAGE_GATEWAY_URL="http://127.0.0.1:8757"
python bridge.py
```

On Windows PowerShell, use `$env:NAME="value"` instead of `export`.

The browser never receives the OpenRouter key. The bridge itself does not hold
the key or make provider requests; it validates the upload and hands the image
to the separately started loopback gateway. Generated page drafts are kept as raster PNG/JPEG/WebP media under ignored
local runtime storage (`web/generated_pages/`) until a future explicit
save/install operation exists. SVG is accepted as source artwork and remains
supported for trusted static assets, but model-generated SVG is not served
until a sanitizer exists.

## Page model

The connected farm page still separates passive scenery from governed objects:

```text
farm page
├── passive backdrop   barn · pond · tree · fence
└── StickerInstances   governed, owned, receipt-producing
```

Positions are page-relative fractions. Sticker scale and horizontal facing are
separate authoritative world transforms. Scale is currently bounded to
0.90–1.10; facing is left/right and renders by mirroring the same sticker
package around its center. Pixels remain presentation and input detail, never
authority. Position bounds still govern the sticker center. The Jev substrate
now generates bounded local movement candidates for that center; full
die-cut-footprint containment remains a separate refinement before treating
edge navigation as visually complete.

## Tests

```bash
cd web
python -m unittest discover -s tests
```

The test suite runs a real bridge on an ephemeral loopback port to exercise
the browser/kernel seam. GitHub Actions also syntax-checks `static/app.js`.
