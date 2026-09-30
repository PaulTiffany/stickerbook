# StickerBook

[![Watch the StickerBook music video: I'm Upping My P(HOP)](https://img.youtube.com/vi/vpu4tmhyj04/hqdefault.jpg)](https://youtu.be/vpu4tmhyj04)

**[Watch "I'm Upping My P(HOP)" on YouTube](https://youtu.be/vpu4tmhyj04)** - a three-minute StickerBook music video featuring the six worlds, upgraded stickers, and real powered-runtime proof.

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

## Responsible-adult supervision

**Children must use AI features with a responsible adult supervising.** This is
an experimental research prototype, not a babysitter, educational assessment,
medical service, or emergency resource. AI can be wrong, surprising, or
inappropriate; the authority kernel bounds actions, not the meaning of replies.
An adult should review outputs, choose suitable providers, manage costs, and
stop a session if needed. Do not enter children's names, contact details,
identifying photos, or other sensitive information. Powered text/page images
may reach external inference providers; browser speech may use platform services.
Separate agent memories persist across container recreation. Review
[the supervision and privacy guide](docs/RESPONSIBLE_USE.md) before enabling AI.

**For judges:** [Submission review, evidence boundaries, and unresolved OpenShell disclosure](docs/SUBMISSION_REVIEW.md).

## Research paper

**[Cross-Modal Witnesses: Perceptual Transduction as an Audit Surface for Agentic Alignment](paper/cross_modal_witnesses/main.pdf)**
by Paul Carver Tiffany III. [Source and reproducibility bundle](paper/cross_modal_witnesses/README.md).
Theory and proposed methods are distinguished from synthetic calibration and
four positive runtime observations; no participant results are reported.

## What exists today

| | |
|---|---|
| **`core/`** | Headless authority kernel: principals, sticker ownership, revisions, receipts, deployment ceilings, action budgets, and legal-action tables. Standard library only; mechanically tested. |
| **`web/`** | Child-facing StickerBook surface with a title page, image-forward page gallery, active page, working sticker hotbar, overlay sticker library, mechanical animations, and responsible-adult/developer access. The same renderer supports a governed localhost world and a mechanical public world. |
| **`jev/`** | OmegaJev: typed Jev decision selection inside a bounded Omega path. The model selects from host-provided legal choices; the host validates the choice and the kernel decides. Unit tests plus container/host verification suites. |
| **`runtime/`** | Live-qualified local powered development: separate restricted Docker OmegaLLM/OmegaJev containers, native agent memories, localhost adapters, and a host bridge/kernel. OpenShell is the retained hardened target, not the working local deployment. |
| **`paper/`** | Cross-Modal Witnesses: submission manuscript, compiled PDF, reproducible calibration fixtures, and separately labeled observed runtime evidence. |

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

Both public mechanical mode and powered local mode expose **Farm, Beach,
Playground, Space, School, and Theater**. Powered mode keeps a separate host-owned
kernel, controller, history, interactions, and trajectories for each page.
Switching pages restores that page's state; a delayed response cannot mutate a
different active page. Uploaded/generated page art remains a preview until a
governed page implementation admits it.

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
- `static/assets/` and `static/help.json`
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

Omega/Jev integration is local and bounded. The working development deployment
uses **two restricted ordinary Docker containers** with the kernel on the host.
OmegaLLM handles language and bounded visual interpretation; OmegaJev receives
finite host-owned choices, never images or spatial writing authority. Each agent
has its own native Omega memory. Docker allows direct provider egress and real
credentials inside the relevant agent container; it does **not** reproduce
OpenShell's credential/network mediation. See [local setup](docs/DOCKER_POWERED_LOCAL.md).

<p align="center">
  <img src="assets/_generated_sprite_refresh/cropped/butterfly/wings-up.png" alt="Butterfly sticker in flight" width="140">
  <img src="assets/_generated_sprite_refresh/cropped/fish/swim-a.png" alt="Fish sticker" width="140">
  <img src="assets/_generated_sprite_refresh/cropped/robot/rest.png" alt="Robot sticker" width="140">
</p>

## Visual asset system

Cover art, page backgrounds, and sticker illustrations are now replaceable
files under `web/static/assets/`, selected by
`web/static/assets/manifest.json`.

That means art can be replaced without editing browser logic. For example,
replacing a frog is a file/manifest operation; the StickerDefinition id,
ownership, legal actions, and kernel authority remain separate.

A sticker's visual asset is a **package of named clips**, and each clip may
contain one image or a sequence of related frames. Built-in definitions retain
their named clip vocabulary; powered Sticker Maker generates a validated
four-pose looping clip. Artwork remains data, never executable behavior code.

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
draft metadata. The current powered sticker creator generates one four-pose
sheet, crops and validates it, then presents an explicit draft for acceptance.
Accepted custom stickers enter the current session library; their catalog does
not yet survive a host bridge restart. See [creation limits](docs/LOCAL_PLAY_REPAIRS.md).

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
- double-tap a placed sticker: mechanical clip behavior publicly; ongoing bounded Jev motion and clips locally, interrupted by child control or page exit.

A StickerDefinition is a reusable design. A StickerInstance is one placement
of that design on one page.

## Conversational Omega and voice

The child-facing page is voice-first rather than chat-first.

A connected local conversational runtime can expose a small push-to-talk
control by default in browsers with speech recognition. Tap the microphone to
start listening; microphone permission still belongs to the browser. The
responsible-adult panel can turn voice off for the current session. A text fallback
exists there for accessibility and debugging rather than occupying the child's
play surface.

The same responsible-adult panel also owns the OmegaLLM inference selection for
the current browser session. It can choose **Sponsored ASI Cloud** (MiniMax M3,
fixed when configured), **Anthropic**, **OpenAI**, **OpenRouter**, **ASI:One**,
or **Off**. Non-sponsored configured lanes expose a bounded model-id field;
OpenRouter therefore remains the broad model-routing escape hatch.

This selection is host state, not child language and not Omega state. A child
message cannot name the provider used for its own turn, and OmegaLLM cannot
change its provider, endpoint, credential, or billing source. The browser never
receives provider credentials.

Conversation remains non-authoritative:

**Omega talks. Jev chooses. The kernel decides.**

The conversational endpoint receives validated text plus a bounded JSON scene
view and, when available, a validated page-image observation, not the kernel object. Creator-agent drafts are similarly proposals, not
installed assets or scene mutations.

See [`docs/AGENT-INTERFACE.md`](docs/AGENT-INTERFACE.md) for the interface
contract and voice/privacy boundary.

## In-app documentation

StickerBook now carries two intentionally different in-app documentation
surfaces from `web/static/help.json`:

- a child-facing **?** guide on the play surface, written in simple language
  about dragging, removing, animation, talking/pointing, and what StickerBook
  can and cannot do;
- a **Responsible adult guide** inside the title-page gear panel, covering
  voice/privacy, the OmegaLLM/OmegaJev split, public-versus-powered mode,
  child authority limits, start/stop behavior, and current limitations.

Only the `child` branch is projected into OmegaLLM context. The responsible-
adult branch remains outside the model's observation surface. This is an
audience/view boundary, not a secrecy claim: both branches are static UI data.

For the full research/developer dependency and modification ledger, see
[`docs/TOOLS-AND-MODIFICATIONS.md`](docs/TOOLS-AND-MODIFICATIONS.md).

## Security boundary

The root [`SECURITY.md`](SECURITY.md) is the binding security model.

The important invariant is not that an agent is "safe enough." It is that
agent capability and execution are downstream of explicit authority. Jev
selects from typed choices; Omega executes the bounded path; the kernel
adjudicates.

The public Pages build is intentionally outside that powered path.

The desired hardened OpenShell profile is pinned to **v0.1.2** under
[`openshell/`](openshell/README.md). Its live WSL path is not qualified and is
outside the current development work. The working Docker profile is qualified
for local development only; see [its explicit containment gaps](docs/DOCKER_POWERED_LOCAL.md).

## Running locally

### Powered local development

Follow [`docs/DOCKER_POWERED_LOCAL.md`](docs/DOCKER_POWERED_LOCAL.md): start the
two restricted role containers using ignored, operator-owned credential files,
then start the **host** bridge with explicit localhost runtime URLs. The agent
ports are `127.0.0.1:8761` (OmegaLLM) and `127.0.0.1:8762` (OmegaJev); the documented
local qualification uses bridge port `8757` (the bridge default is `8756`).

`Start StickerBook.cmd` / `Stop StickerBook.cmd` are **legacy OpenShell launchers**;
they are not the current Docker development start/stop path. Do not use them to
recover a Docker session. Stopping the bridge and role containers is independent
of the agents; Docker-managed agent memory volumes survive container recreation.

OpenRouter remains the Jev provider and OmegaLLM fallback. The configured sponsored
ASI Cloud lane uses locked `minimax/minimax-m3`. Keys are never committed or baked
into images. A newly set environment variable requires recreating the affected
container, not just restarting it.

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
| [`docs/AGENT-INTERFACE.md`](docs/AGENT-INTERFACE.md) | Conversational Omega, voice, creator drafts, documentation projection, and authority separation. |
| [`docs/PROJECT-LINEAGE.md`](docs/PROJECT-LINEAGE.md) | Detailed research/developer lineage: Chalked, AlphaClaw, BGI Commons community context, and how those lessons map into StickerBook. |
| [`docs/TOOLS-AND-MODIFICATIONS.md`](docs/TOOLS-AND-MODIFICATIONS.md) | Research/developer ledger of upstream tools, exact pins, local modifications, rationale, trust boundaries, and verification status. |
| [`core/README.md`](core/README.md) | Authority kernel. |
| [`web/README.md`](web/README.md) | Browser, page, and bridge behavior. |
| [`jev/SECURITY.md`](jev/SECURITY.md) | OmegaJev boundaries and verification. |
| [`jev/EXPERIMENT.md`](jev/EXPERIMENT.md) | Experimental record, including failures and retractions. |
| [`openshell/README.md`](openshell/README.md) | Pinned containment layer, policies, provider profiles, and current proof boundary. |
| [`runtime/README.md`](runtime/README.md) | One-command boot/shutdown, dual-Omega loopback seams, and voice-first deployment graph. |
| [`docs/OMEGA_AGENT_MEMORY.md`](docs/OMEGA_AGENT_MEMORY.md) | Separate native Omega memories, child feedback, persistence, and learning limits. |
| [`docs/LOCAL_PLAY_REPAIRS.md`](docs/LOCAL_PLAY_REPAIRS.md) | Live curve/loop fixes, four-frame creation, image drafts, and remaining product limits. |
| [`NOTICE`](NOTICE) | Third-party attribution and upstream modifications. |

## Current direction

The local powered chain has been observed live: child language → OmegaLLM →
bounded goal → OmegaJev offered key → host kernel receipt. All six governed
pages are available. Continuous child-directed motion, bounded multimodal
grounding, separate native agent memory, four-pose sticker drafts, and queued
spoken replies are implemented. Motion quality, inference latency, and visual
target fidelity remain variable; memory is advisory and does not train weights.
Discrete remembered patterns are not full continuous movement-style learning.

See [development status](docs/DEVELOPMENT-STATE.md), [live play repairs](docs/LOCAL_PLAY_REPAIRS.md),
and [the paper](paper/cross_modal_witnesses/main.pdf) for evidence and limits.
No human-subject study or production child-safety certification is claimed.

## Built on

StickerBook draws from and experiments with several projects and prior design
lines, including the developer's earlier AlphaClaw and Chalked work, BGI
Commons/Omega community engagement, SingularityNET Omega, PeTTa, NVIDIA
OpenShell, OpenRouter, and TypeSafe Jev. See
[`docs/PROJECT-LINEAGE.md`](docs/PROJECT-LINEAGE.md) for the detailed human
and research lineage, and [`NOTICE`](NOTICE) for third-party attribution.

StickerBook was made with support from [BGI Commons](https://bgicommons.org/) as part of its **HyperSprints series**. [StickerBook team page](https://bgicommons.org/teams/62).
The project remains independent research; this acknowledgement does not imply
organizational endorsement of its results or child-safety claims.

Omega's source is not vendored here. The tested upstream versions and local
modifications are recorded under `jev/`.

## License

StickerBook-authored code and documentation are MIT, © 2026 Paul Carver
Tiffany III, unless a file states otherwise. See [`LICENSE`](LICENSE).

The MIT grant does **not** relicense the third-party software, runtime
substrates, container/base images, hosted inference services/models, browser
speech/platform APIs, or external deployment services that StickerBook uses.
Those components retain their own licenses and/or service terms. See
[`NOTICE`](NOTICE) for the runtime/tool attribution ledger, including Omega,
NVIDIA OpenShell, PeTTa/MeTTa, Jev/OpenRouter, SWI-Prolog, browser Web Speech
APIs, Docker/WSL2, and related infrastructure.
