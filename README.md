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
| **`core/`** | Headless authority kernel: principals, sticker ownership, revisions, receipts, deployment ceilings, action budgets, and legal-action tables. Standard library only. 67 tests. |
| **`web/`** | Child-facing StickerBook surface with a title page, image-forward page gallery, active page, working sticker hotbar, overlay sticker library, mechanical animations, and responsible-adult/developer access. The same renderer supports a governed localhost world and a mechanical public world. |
| **`jev/`** | OmegaJev: typed Jev decision selection inside a bounded Omega path. The model selects from host-provided legal choices; the host validates the choice and the kernel decides. 40 unit tests plus container/host verification suites. |

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

On an active page, the persistent bottom bar has three parts:

```text
+------------------------------------------------------+
| home |       MY WORKING STICKER SHEET        |  +   |
+------------------------------------------------------+
```

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
the page.

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

Both creator surfaces now offer two explicit routes:

- **Upload**: choose existing artwork from the device.
- **Make with StickerBook**: describe the desired page or sticker to a future
  local creator agent.

The public Pages demo does not pretend that an agent is connected. Selecting
the assisted path explains that powered creation belongs in the local runtime.

The browser-side contract is already defined for that future runtime. Page
drafts send a textual prompt. Sticker drafts additionally send an animation
intent and request asset schema version 2, whose output is expected to be a
validated visual package with an idle clip and optional movement/frame clips.

This seam returns a draft only. It does not grant authority, mutate the kernel,
or install generated executable code.

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

## Security boundary

The root [`SECURITY.md`](SECURITY.md) is the binding security model.

The important invariant is not that an agent is "safe enough." It is that
agent capability and execution are downstream of explicit authority. Jev
selects from typed choices; Omega executes the bounded path; the kernel
adjudicates.

The public Pages build is intentionally outside that powered path.

## Running locally

```bash
cd web
python bridge.py
# open http://127.0.0.1:8756/
```

Add `?dev=1` to show revision, acting principal, verdicts, and receipts.
Add `?mechanical=1` to preview the public adapter locally.

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
| [`core/README.md`](core/README.md) | Authority kernel. |
| [`web/README.md`](web/README.md) | Browser, page, and bridge behavior. |
| [`jev/SECURITY.md`](jev/SECURITY.md) | OmegaJev boundaries and verification. |
| [`jev/EXPERIMENT.md`](jev/EXPERIMENT.md) | Experimental record, including failures and retractions. |
| [`NOTICE`](NOTICE) | Third-party attribution and upstream modifications. |

## Current direction

The immediate product problem is the shared visual medium, not more autonomous
capability. The UI should remain recognizable to a child before we expand
agent behavior.

The next agent integration should expose bounded, legal sticker behavior on the
same page without creating a second authority system.

Persistence, accounts, social discovery, powered Sticker Maker behavior, and
broader multi-agent delegation remain separate future work.

## Built on

StickerBook draws from and experiments with several projects and prior design
lines, including AlphaClaw, Chalked, SingularityNET Omega, PeTTa, OpenRouter,
and TypeSafe Jev. See [`NOTICE`](NOTICE) and the relevant component documents
for exact third-party licensing and version information.

Omega's source is not vendored here. The tested upstream versions and local
modifications are recorded under `jev/`.

## License

MIT, © 2026 Paul Carver Tiffany III. See [`LICENSE`](LICENSE).
Third-party attributions are in [`NOTICE`](NOTICE).
