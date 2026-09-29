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
by the asset manifest and currently exposes **Farm, Beach, Playground, Space,
School, and Theater**, plus a **+ Make a page** tile. Each public demo page has independent
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
model call. The current built-in catalog contains 76 sticker definitions, each
with four initial pose sprites, across Farm, Beach, Playground, Space, School,
and Theater.

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

In powered localhost mode, the same bare-page drag also sends a bounded
`PagePathTrace` to the host as observed input. This retains its pointer route
without changing the existing box mark. Its points are observed page-space
fractions, not authoritative world anchors; no sticker or kernel state changes.
Malformed path telemetry is ignored while the box remains usable.

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

The title-page gear opens a deliberately separate **Responsible adult** panel.
Research/developer links are grouped in their own footer inside that panel rather
than being presented as part of the parent guide. It links directly to the project repository at
`https://github.com/PaulTiffany/stickerbook` and exposes conversational
runtime options without mixing those controls into the child's normal play
surface.

When a conversational Omega runtime is connected, an adult may enable
push-to-talk voice and/or an **accessibility text chat**. The text option adds
a translucent, dismissible chat panel near the top of the play surface. It
uses the same `/api/agent/converse` path as voice, can display voice
transcripts while enabled, and does not gain any additional world-mutation
authority.

The same panel contains **StickerBook talking brain**, a responsible-adult
session control for OmegaLLM inference. It reads the secret-free provider
catalog from `GET /api/adult/inference` and updates the current bridge session
through `POST /api/adult/inference`.

Current lanes are Sponsored ASI Cloud, Anthropic, OpenAI, OpenRouter, ASI:One,
and Off. Sponsored ASI Cloud is preferred automatically when configured and is
model-locked to `minimax/minimax-m3`. Other configured lanes expose a bounded
model-id field so the adult may select a provider-supported model. Unconfigured
lanes remain visible but disabled.

Provider/model selection is deliberately **not** part of normal `/api/state`
and is not copied into the child-facing `scene`. Child conversation payloads
cannot override it; the bridge supplies the selected lane separately when it
calls OmegaLLM.

The public mechanical demo keeps voice disabled but allows the text chat UI to
be opened and exercised. Its replies are fixed mechanical stub text and no
model is called. This lets the accessibility surface be reviewed on GitHub
Pages without pretending that Omega is connected.

The developer receipts panel opened with `?dev=1` has its own **×** control.
Closing it removes the `dev` query flag from the current URL and returns to
the normal child title surface without requiring a manual reload.

## In-app help and audience separation

`web/static/help.json` is the checked-in source for two different in-app
documentation audiences:

- `child` — rendered from the play-surface **?** button;
- `adult` — rendered inside the Responsible adult / developer panel.

The child guide explains play mechanics and bounded AI behavior in simple
language. It intentionally contains no API-key, Docker, OpenShell, repository,
provider, or policy-approval instructions.

The parent guide explains voice/privacy, the OmegaLLM/OmegaJev split, the
authority kernel, public-versus-powered deployment, child authority limits,
start/stop behavior, and current implementation limits.

The bridge treats documentation as a view capability. For conversational turns
it builds a private conversation scene from the ordinary browser state plus:

```json
{"child_help": { ... }}
```

Only the `child` branch is copied there. The `adult` branch is never sent to
OmegaLLM. This is mechanically tested in
`web/tests/test_help_content.py`.

The public Pages build ships the same static help data so the explanatory UI
can be reviewed without a live agent.

## Dual Omega / creator seams

The child-facing agent architecture has two separate Omega loops:

- **OmegaLLM** receives voice/text/deictic context, the child-facing help
  projection, and may return language plus one bounded semantic goal.
- **OmegaJev** receives that goal with fresh governed scene state and chooses
  one key at a time from a finite host-generated action surface.

`/api/agent/converse` is therefore not a command endpoint. OmegaLLM cannot
supply coordinates as executable arguments or invoke the kernel. If it attaches
a goal, the host validates the goal, constructs bounded Jev choices, and applies
only a Jev-selected host key through `Kernel.propose_key()`.

The child may also reach OmegaJev without OmegaLLM by double-clicking/tapping a
sticker. That creates a one-turn animation-only goal; Jev may choose only one
declared clip key or NOOP.

### Movement-pattern memory

A child can teach a sticker a way it likes to move. `web/pattern_memory.py`
holds a bounded, in-memory library of `MovementPattern`s: ordered
`PatternStep(verb, suffix)` fragments that keep the action family and discard
the transient StickerInstance id.

**Learning changes memory, not authority.** Only traces whose kernel receipts
were *accepted* can be remembered. Replay re-reads the world, rebuilds the
legal table, re-derives each key against the current subject, and requires an
accepted receipt before advancing, so a remembered step that is no longer
legal simply stops. Pattern memory adds no kernel mutation primitive and never
widens the choice surface; `known_patterns` in the Jev scene is read-only,
declarative, and contains no complete action key.

"Remember that as your happy dance" and "Froggy, do your happy dance" run
through the ordinary architecture. OmegaLLM emits a bounded `remember-pattern`
or `perform-pattern` goal carrying only a subject and a label -- never
movement, keys or steps. `web/governed_history.py` keeps the bounded
host-owned record of what actually happened, so the host resolves "that" from
real kernel receipts rather than from anything the model says. Recall goes to
OmegaJev, which picks each step from the current finite legal table.

The host resolves "that" deterministically: the latest contiguous learnable
accepted run for the named subject, ending at a switch to another subject, a
non-learnable action, the pattern-length limit, or the history window.
OmegaLLM never picks the slice.

Replay is non-atomic: if a later step is no longer legal the earlier accepted
steps stay applied and the attempt stops. Every attempt produces a host-side
`PatternReplayRecord` that groups ordinary kernel receipts without holding any
authority itself, keeping `plannedSteps`, `submittedSteps` and `acceptedSteps`
separate, plus `result` (`completed` / `partial` / `stopped`), `stoppedAt` and
`stoppedReason`.

### Sticker-drag traces

**Input history is not world history.** Dragging a sticker shows the browser a
whole trajectory but asks the kernel for exactly one `MOVE_STICKER` at the
release point. `web/sticker_drag.py` keeps the demonstration as a bounded
`StickerDragTrace` with three labelled classes of evidence: a host-bound
authoritative start (`t=0, dx=0, dy=0`), observed interior samples, and a
host-bound authoritative terminal point taken from the accepted move. The
browser's own first and last samples are not trusted to coincide with those
anchors.

This is **one input type, not a gesture ontology** — hence `kind =
"sticker-drag"`. Pointing, boxing a region, path drawing in empty space and
speech-plus-gesture are different input types and are not modelled here.

**Failure to observe must not become failure to act.** Unusable telemetry is
discarded and never reaches history, but the child's move is still adjudicated
normally; the response carries `dragIgnored` with the reason. A malformed
*move* is still a bad request.

No intermediate pointer position becomes a kernel receipt, and the kernel is
unchanged. Limits: 32 retained samples, 192 raw accepted, 64 retained by the
browser, 20 s, sized to fit the 8192-byte body ceiling. Both browser and host
reduce by dropping the interior point that changes the path least, so a brief
sharp bend survives. A sticker drag is still deliberately not learnable as a
discrete `PatternStep`.

See `docs/AGENT-INTERFACE.md` for the full seam.

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

Each `/api/agent/converse` turn records a bounded host-owned interaction
episode. The browser supplies the transcript or typed text, optional point or
box, and descriptive `input_mode` (`voice` or `text`). The host stamps the
episode ID, sequence and scene revision, then associates the newest four
accepted sticker-drag and page-path observations since the previous linguistic
turn in host arrival order. The browser cannot select historical trace IDs.
OmegaLLM receives these
facts without retained trajectory samples or geometry labels. A failed inference
still records the input and advances the input cursor; the current episode is
the only interaction record supplied to that OmegaLLM call. Recording does
not mutate the world. Audio is never retained by this record.

A successful bare-page observation posts its existing box with its bounded
path samples and receives a host-issued `sourceEvent` token. The browser adds
that token only to the still-pending box. The host carries it into the episode
only if it identifies the latest eligible retained path and matches the box
stored with that path. Two gestures before speech therefore produce two
different tokens, while a failed path observation leaves its box unlinked.

```bash
cd web
python -m unittest discover -s tests
```

The test suite runs a real bridge on an ephemeral loopback port to exercise
the browser/kernel seam. GitHub Actions also syntax-checks `static/app.js`.
