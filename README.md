# StickerBook

StickerBook is an interactive scene system, building on AlphaClaw and Chalked,
where users and agents manipulate persistent sticker objects with animation,
state, and behavior. It uses Omega as the agent runtime, Jev for typed
decision selection, and constrained multi-agent control interfaces for
coordinating how stickers act within shared illustrated environments.

The medium comes first: a child should be able to understand StickerBook by
recognizing pictures, moving stickers, and touching obvious visual targets.
Machine agency may inhabit that shared surface without acquiring authority over
it.

> **Capability is not authority.**
> More reasoning, memory, confidence, specialization, recursion, or tool skill
> must never imply more authority.

## What exists today

| | |
|---|---|
| **`core/`** | Headless authority kernel: principals, sticker ownership, revisions, receipts, deployment ceilings, action budgets, and legal-action tables. Standard library only; mechanically tested. |
| **`web/`** | Child-facing StickerBook surface with a title page, image-forward page gallery, active page, working sticker hotbar, overlay sticker library, mechanical animations, and responsible-adult/developer access. The same renderer supports a governed localhost world and a mechanical public world. |
| **`jev/`** | OmegaJev: typed Jev decision selection inside a bounded Omega path. The model selects from host-provided legal choices; the host validates the choice and the kernel decides. Unit tests plus container/host verification suites. |
| **`openshell/` + `runtime/`** | Pinned OpenShell v0.1.2 containment plus governed local orchestration: separate non-root OmegaLLM/OmegaJev sandboxes, role-specific provider profiles, loopback-only runtime adapters, voice-first conversation wiring, and one-command Windows/WSL start/stop. Mechanically checked; live WSL2/OpenShell proof remains a deployment milestone. |

## Child-facing navigation

StickerBook intentionally avoids app-style navigation chrome.

```text
TITLE / COVER
     |
     v
PAGE GALLERY  ---->  + MAKE A PAGE
     |
     v
ACTIVE PAGE
     |
     +---- bottom-left: back to title
     |
     +---- bottom-right: sticker library popup
```

The page gallery is thumbnail-first, like an image browser. The title page is
itself the primary navigation target: touch the cover to open the page gallery.

The current public mechanical book includes four visual pages from the asset
manifest: **Farm, Beach, Playground, and Space**. Each page keeps its own
in-memory StickerInstances during the demo session. The governed localhost world still
only exposes pages that the authority kernel actually implements; additional
art does not silently create governed state.

On an active page, the persistent bottom bar has three parts:

```text
+------------------------------------------------------+
| home |       MY WORKING STICKER SHEET        |  +   |
+------------------------------------------------------+
```

The active artwork is an edge-to-edge stage. StickerBook preserves the complete
native image instead of cropping it to fill an arbitrary phone shape. Any
unused aspect-ratio space is filled with a soft full-bleed copy of the same
artwork rather than decorative margins.

The hotbar is flush to the left, right, and bottom edges. In landscape it owns
a reserved bottom strip, so it never covers the playable image. A child can
remove a placed sticker with the simple gesture "drag it down."

Cover and page assets support landscape and portrait variants. The built-in
playable page artboards are **1916 × 717** and **941 × 1574**, deliberately
excluding the hotbar so child gestures and Omega/Jev actions share one complete
page coordinate surface. The cover uses separate **1916 × 821** and
**941 × 1672** artboards.

The middle is not the complete sticker inventory. StickerBook now distinguishes
three visual layers:

**Library → Sheet → Page**

- **Library**: everything available to use.
- **Sheet / hotbar**: the small set the child has brought to the current page.
- **Page**: placed StickerInstances participating in the scene.

The sticker library appears as a popup over the current page rather than
navigating away. Sticker thumbnails can be dragged from the library into the
hotbar, then from the hotbar onto the page.

The title page also reserves a quiet bottom-right target for responsible-adult
and developer controls. That path is intentionally separate from normal child
navigation.

## Public demo versus powered runtime

These are deliberately different deployment profiles.

### GitHub Pages

Public demo: https://paultiffany.github.io/stickerbook/

The public site is a **mechanical demonstration only**.

It contains no Omega runtime, Jev model call, API key, Python bridge, authority
kernel, privileged backend, or agent process. Dragging and animation are
implemented deterministically in browser memory so the public site can show
the StickerBook medium without pretending a live agent is present.

The Pages workflow uses an allow-listed artifact containing only:

- `index.html`
- `static/app.js`
- `static/style.css`
- `.nojekyll`

### Localhost

The powered surface runs through `web/bridge.py`. The browser proposes an
action; the Python authority kernel determines what actually happens and
returns authoritative state plus a receipt.

```text
human gesture / agent choice
          |
          v
     proposed action
          |
          v
   authority kernel
          |
     accept / refuse
          |
          v
 authoritative scene state
```

Omega/Jev integration remains local and bounded. Models do not directly mutate
the page. The powered deployment has a pinned OpenShell containment layer under
`openshell/` plus operator-owned boot/shutdown under `runtime/`. OpenShell
constrains the live process/filesystem/network boundary while the StickerBook
kernel remains the authority boundary. The bridge talks to each Omega role only
through explicit loopback adapters; neither sandbox receives the kernel object.

## Visual asset system

Cover art, page backgrounds, and sticker illustrations are now replaceable
files under `web/static/assets/`, selected by
`web/static/assets/manifest.json`.

That means art can be replaced without editing browser logic. For example,
replacing a frog is a file/manifest operation; the StickerDefinition id,
ownership, legal actions, and kernel authority remain separate.

A sticker's visual asset is a **package of named clips**, and each clip may
contain one image or a sequence of related frames. This lets Sticker Maker
eventually emit idle art plus frame sets for behaviors such as fluttering,
hopping, swimming, or other bounded animations without turning generated art
into executable code.

See [`web/static/assets/README.md`](web/static/assets/README.md) for exact
instructions for replacing the cover, adding a page background, or adding a
sticker asset.

## Page and sticker creation

Both creator surfaces expose **Upload** and **Make with StickerBook**.

Page uploads accept SVG, PNG, JPEG/JPG, and WebP. The public Pages demo keeps
an upload as a local browser preview and never sends it to a model. In powered
local mode an operator can separately enable a loopback page-image gateway.
That gateway uses the original upload as the reference for two OpenRouter image
edit jobs: **1916 × 717** horizontal and **941 × 1574** portrait. The naming
contract is `<name>.<ext>` and `<name>-vertical.<ext>`.

The browser and authority-kernel bridge never receive the OpenRouter API key.
The separate image gateway may hold that provider credential but receives no
StickerBook principal, kernel object, or world-mutation authority.

The textual creator-agent seam remains available for proposed page/sticker
draft metadata. Sticker drafts additionally send an animation intent and
request asset schema version 2, whose output is expected to be a validated
visual package with an idle clip and optional movement/frame clips.

Generation returns drafts only. It does not grant authority, mutate the kernel,
install generated executable code, or silently save a generated page.

The intended Sticker Maker output is a validated StickerDefinition visual
package, not arbitrary generated runtime code.

## Main gestures

- touch the title page to open the page gallery;
- touch a page thumbnail to enter it;
- drag a library sticker into the hotbar;
- drag a hotbar sticker onto the page;
- drag a placed sticker to move it;
- drag a placed sticker back to the hotbar to remove it;
- double-tap a placed sticker to bring its declared mechanical animation to life.

A StickerDefinition is a reusable design. A StickerInstance is one placement
of that design on one page.

## Conversational Omega and voice

The child-facing page is voice-first rather than chat-first.

A connected local conversational runtime can expose a small push-to-talk
control, but voice is disabled by default and must be enabled for the current
session from the responsible-adult panel. A text fallback exists there for
accessibility and debugging rather than occupying the child's play surface.

Conversation remains non-authoritative:

**Omega talks. Jev chooses. The kernel decides.**

The conversational endpoint receives validated text plus a normal JSON scene
view, not the kernel object. Creator-agent drafts are similarly proposals, not
installed assets or scene mutations.

See [`docs/AGENT-INTERFACE.md`](docs/AGENT-INTERFACE.md) for the interface
contract and voice/privacy boundary.

## Security boundary

The root [`SECURITY.md`](SECURITY.md) is the binding security model.

The important invariant is not that an agent is "safe enough." It is that
agent capability and execution are downstream of explicit authority. Jev
selects from typed choices; Omega executes the bounded path; the kernel
adjudicates.

The public Pages build is intentionally outside that powered path.

For the powered localhost path, OpenShell is pinned to **v0.1.2**
(commit `6648bd0c290efbc41ba131ee9831ee45cd431f94`). Separate policies are kept
for OmegaLLM and OmegaJev; neither base policy grants network access. Provider
access is contributed explicitly at the OpenShell boundary. See
[`openshell/README.md`](openshell/README.md).

## Running locally

### Powered governed runtime — normal path

On the Windows host, double-click **`Start StickerBook.cmd`**. The launcher
uses WSL2 + Docker Desktop, verifies/builds the pinned runtime, starts the
separate OmegaLLM and OmegaJev OpenShell sandboxes, health-checks them, starts
the authority bridge, and opens `http://127.0.0.1:8756/`.

The first powered start may ask once for the OpenRouter API key if the
role-specific OpenShell providers have not yet been created. The key is not
written into repository/runtime state. Later starts reuse the OpenShell
providers.

Double-click **`Stop StickerBook.cmd`** to stop the bridge and delete both
StickerBook sandboxes without requiring agent cooperation.

This path is **implemented and CI/mechanically checked, but not yet claimed as
live-host verified**. See [`runtime/README.md`](runtime/README.md).

### Bridge-only development path

```bash
cd web
python bridge.py
# open http://127.0.0.1:8756/
```

Without explicit runtime URLs, both Omega adapters remain inert. Add `?dev=1`
to show revision, acting principal, verdicts, and receipts. Add
`?mechanical=1` to preview the public adapter locally.

## Tests

```bash
cd core && python -m unittest discover -s tests
cd ../web && python -m unittest discover -s tests
cd ../jev && python -m unittest discover -s tests
```

Browser JavaScript is syntax-checked in GitHub Actions.

## Documents

| File | What it is |
|---|---|
| [`SECURITY.md`](SECURITY.md) | Constitutional security model and implementation status. |
| [`docs/MEDIUM.md`](docs/MEDIUM.md) | Why the sticker-book medium is itself the experiment. |
| [`docs/AGENT-INTERFACE.md`](docs/AGENT-INTERFACE.md) | Conversational Omega, voice, creator drafts, and authority separation. |
| [`core/README.md`](core/README.md) | Authority kernel. |
| [`web/README.md`](web/README.md) | Browser, page, and bridge behavior. |
| [`jev/SECURITY.md`](jev/SECURITY.md) | OmegaJev boundaries and verification. |
| [`jev/EXPERIMENT.md`](jev/EXPERIMENT.md) | Experimental record, including failures and retractions. |
| [`openshell/README.md`](openshell/README.md) | Pinned containment layer, policies, provider profiles, and current proof boundary. |
| [`runtime/README.md`](runtime/README.md) | One-command boot/shutdown, dual-Omega loopback seams, and voice-first deployment graph. |
| [`NOTICE`](NOTICE) | Third-party attribution and upstream modifications. |

## Current direction

The foundational local substrate is now represented in code: child voice/text
enters OmegaLLM, bounded goals enter OmegaJev, typed host-owned keys return to
the authority kernel, and operator-owned orchestration starts/stops the two
OpenShell sandboxes plus the bridge. The remaining infrastructure milestone is
live-host verification of that exact graph on WSL2/Docker Desktop.

After that proof, work can move back toward StickerBook behavior itself —
movement-pattern learning, richer child-directed animation, and creator
features — without granting either Omega loop a second authority system.

Persistence, accounts, social discovery, powered Sticker Maker behavior, and
broader multi-agent delegation remain separate future work.

## Built on

StickerBook draws from and experiments with several projects and prior design
lines, including AlphaClaw, Chalked, SingularityNET Omega, PeTTa, NVIDIA
OpenShell, OpenRouter, and TypeSafe Jev. See [`NOTICE`](NOTICE) and the relevant component documents
for exact third-party licensing and version information.

Omega's source is not vendored here. The tested upstream versions and local
modifications are recorded under `jev/`.

## License

MIT, © 2026 Paul Carver Tiffany III. See [`LICENSE`](LICENSE).
Third-party attributions are in [`NOTICE`](NOTICE).
