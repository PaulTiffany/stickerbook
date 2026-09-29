# Dual-Omega play interface

StickerBook separates linguistic interpretation, embodied decision selection,
and authority.

> **OmegaLLM translates. OmegaJev chooses. The kernel decides.**

OmegaLLM and OmegaJev are intended to be two separate Omega agent loops.
OmegaLLM bridges the child's language/voice/deictic reference into a bounded
semantic goal. It does **not** prescribe a motor program. OmegaJev receives the
goal plus fresh world feedback and repeatedly selects one key from a small
host-owned action table. This lets movement patterns be discovered as sequences
of local choices rather than being secretly hard-coded by the language model.

## Conversation is not authority

The browser sends human language to OmegaLLM through:

`POST /api/agent/converse`

The bridge validates the input and fixes the browser principal. OmegaLLM
receives only the validated text, the fixed browser principal id, a bounded
JSON scene view, the child-facing help projection, the host-selected
provider/model record, and the optional transient deictic reference for that
turn. It never receives the authority-kernel object
or the responsible-adult guide.

OmegaLLM returns language and may optionally attach one bounded `goal` object,
for example:

```json
{
  "subject": "cow-1",
  "intent": "move-and-animate",
  "behavior": "look",
  "target": {"kind": "point", "x": 0.42, "y": 0.86}
}
```

That object is data, not a command. The host validates its schema, regenerates
the legal Jev surface from authoritative state, and gives OmegaJev only the
goal, a bounded scene projection, and descriptions of the offered keys.
OmegaJev may return only one supplied key. The selected key then goes through
`Kernel.propose_key()`; the kernel remains the mutation gate.

The causal receipt records the child as the authority/origin
(`requestedBy`), OmegaLLM as the linguistic transformer
(`translatedBy`), and OmegaJev as the selector (`selectedBy`). None of
those provenance fields are consulted for authorization.

## Child-facing documentation is a bounded view

The in-app help source is `web/static/help.json`, with separate `child` and
`adult` branches.

The browser may render both branches to their intended audiences. OmegaLLM
receives **only** a defensive copy of the `child` branch under:

```json
{
  "scene": {
    "child_help": {
      "title": "How StickerBook works",
      "intro": "...",
      "topics": [...]
    }
  }
}
```

This gives conversational Omega a stable source of truth for questions such as
"How do I play?", "What happens if I double-tap?", or "What can you do?".

The child branch intentionally excludes operator setup, API keys, OpenShell,
Docker, repository administration, provider configuration, and policy approval.
The parent guide is not secret; it is simply **outside OmegaLLM's observation
surface**.

Documentation is descriptive data. It cannot grant a capability or authorize a
mutation.

## Responsible-adult inference selection is host state

The powered host exposes a separate adult-only route:

`GET /api/adult/inference` / `POST /api/adult/inference`

This route selects which **already configured** inference lane OmegaLLM uses for
the current bridge session. It is not part of the normal browser state and is
not copied into `scene.child_help`.

Current lanes are:

- Sponsored ASI Cloud — fixed to `minimax/minimax-m3`;
- Anthropic — default `claude-opus-4-8`;
- OpenAI — default `gpt-5.5`;
- OpenRouter — default `z-ai/glm-5.2`, with a bounded model-id field;
- ASI:One — default `asi1-ultra`;
- Off.

The bridge chooses the session lane and passes only the selected
`{provider, model}` record to the OmegaLLM loopback adapter. A child request
cannot override it by adding an inference field, and OmegaLLM cannot choose a
different endpoint, credential, or billing source.

The selector is currently an **audience control rather than authenticated
parental security**. A person with direct access to the local loopback browser
and developer tools can call the adult route. That does not grant world
authority—the kernel remains unchanged—but a deployed product that needs to
protect paid inference from a child would need an authenticated adult boundary.


## Creator drafts are also non-authoritative

`POST /api/creator/draft`

is a second non-authoritative seam. It can return a proposed page or sticker
asset description. Sticker drafts target asset schema v2, where one
StickerDefinition can contain an idle clip plus one or more behavior clips,
and each clip can contain one or many related image frames.

A creator draft does not install itself and cannot grant a behavior that the
world/kernel definition does not already permit.

## Page-image creation is a separate media seam

Child-selected page artwork uses a third non-authoritative path:

`POST /api/creator/page-image`

The browser sends the original image bytes to the local bridge. The bridge
accepts only SVG, PNG, JPEG/JPG, or WebP, enforces an upload-size ceiling, and
does not itself hold a provider credential.

Only when a responsible operator has explicitly configured
`STICKERBOOK_IMAGE_GATEWAY_URL` does the bridge forward the validated image
to a separately started loopback page-image gateway. That process may hold
`OPENROUTER_API_KEY`, but it has no StickerBook principal, kernel object,
legal-action table, or world-mutation interface.

The gateway asks the configured OpenRouter image-editing model to produce two
drafts from the **same original upload**:

- horizontal: exactly **1916 × 717**, named `<stem>.<ext>`;
- portrait: exactly **941 × 1574**, named `<stem>-vertical.<ext>`.

Both jobs use the fixed reframe/outpaint instructions in `web/page_assets.py`:
preserve the original artwork and composition, do not reinterpret it, expand
surrounding background rather than stretching, and add no unrelated objects,
text, or design elements. OpenRouter image parameters differ by model, so the
gateway does not assume a universal custom-size control. It verifies the
intrinsic dimensions of each returned SVG/PNG/JPEG/WebP and rejects a result
unless it is exactly the requested canvas.

Provider output remains media/data. Automated output is restricted to raster
PNG/JPEG/WebP; SVG may be uploaded as source art but model-generated SVG is
rejected until it has a dedicated sanitizer. Generated files are stored only
in ignored local runtime storage until an explicit save/install path exists.
Generation therefore cannot add a page to the governed book or gain authority
over StickerInstances.

The public GitHub Pages profile contains no Python bridge, page-image gateway,
provider credential, or model call. Upload there is a local browser preview
only.

## Voice-first child interface

Normal child-facing play has no persistent chat panel.

When a conversational runtime is connected, a responsible adult can enable
voice for the current browser session. Only then does a small push-to-talk
microphone appear on the active page.

The browser's speech-recognition implementation may use a browser/device speech
service. StickerBook therefore does not silently enable it. The responsible
adult panel states this explicitly.

The recognized text is sent to the local conversational endpoint. A returned
reply may be spoken with the browser's speech-synthesis facility.

## Optional text projection

Voice and text are two projections of the same conversational interface. A
responsible adult may optionally expose the translucent text chat on the play
surface for accessibility. There is no separate adult-panel chat path.

The public mechanical build allows that text surface to be exercised with a
fixed stub reply; no conversational model is called.

## Child deictic page reference

Conversation may carry one optional transient reference alongside the child's
utterance. The browser creates it only from a bare-page tap or rectangular
drag and sends normalized page coordinates:

```json
{"kind":"point","point":{"x":0.71,"y":0.58}}
{"kind":"box","box":{"x1":0.1,"y1":0.2,"x2":0.6,"y2":0.7}}
```

The localhost bridge validates the coordinates, attaches the governed page id,
and gives the reference to conversational Omega only for that turn. It never
enters kernel state and is not automatically included in a Jev observation.
Thus pointing at pixels can help Omega understand what the child means without
silently turning painted background content into governed objects.

## Sticker action substrate

The shipped sticker substrate deliberately separates visual pose from governed
world transforms.

A StickerDefinition declares visual sprite names, clip names, a default/rest
clip, and scale bounds. A StickerInstance carries authoritative position and
scale plus its current clip (still exposed on the historic `animation` wire
field for compatibility). The v4 built-ins use frame sprites for clips; their
clip recipes do not smuggle locomotion through CSS transforms.

Translation, apparent depth, and horizontal facing are world state. Scale is
currently bounded to 0.90–1.10 globally, and the host-generated action table
offers only bounded 0.02 scale steps. Facing is a typed left/right transform
with host-generated FACE choices. The kernel validates both independently.

For OmegaJev movement the host also supplies an **ephemeral local movement
alphabet** each turn (N, NE, E, SE, S, SW, W, NW). Each entry is just another
host-owned candidate coordinate checked by the kernel. The page itself remains
continuous; there are no permanent snap slots. After each selected step the
world is re-observed and a new table is generated, so OmegaJev can form
movement patterns from feedback.

The current local agent authority profiles intentionally contain no sticker
removal capability. Human control retains removal. This is non-representability,
not a prompt instruction.

### Two ways a child can ask OmegaJev to animate

1. **Through OmegaLLM.** Language such as “make the cow look over here” may be
   translated into a bounded goal. OmegaJev can then choose the declared clip
   and/or local movement steps over several turns.
2. **Direct double-click/tap.** The existing child gesture bypasses OmegaLLM
   and enters OmegaJev as a one-turn animation goal. The action surface contains
   only declared animation choices for that sticker plus NOOP. If no Jev runtime
   is connected, StickerBook retains the historical deterministic animation
   toggle so ordinary play still works.

A Jev-selected move performed under the child's authority preserves a clip that
Jev selected previously. A literal human pointer drag still interrupts motion
and settles the sticker to its rest clip.

The bounded scene contains only explicitly declared objects/state. A generated
action key must not reveal an undeclared object merely by naming it. Painted
background pixels remain passive scenery unless OmegaLLM turns a validated
child reference into explicit bounded goal data.

## Runtime attachment

`web/agent_runtime.py` and `web/jev_runtime.py` still default to inert
`Disabled*` adapters and perform no network access unless explicit loopback
runtime URLs are supplied.

The powered launcher attaches:

- OmegaLLM at host loopback port 8761;
- OmegaJev at host loopback port 8762.

Both adapters reject non-loopback URLs. Neither receives the kernel object or a
provider credential.

OpenShell is the containment substrate for those two powered Omega loops, not a
replacement for the StickerBook kernel. They use separate sandboxes, policies,
and provider identities. The dual-Omega OpenShell path is implemented and
mechanically checked, but is not labeled live-host verified until exercised on
the actual WSL2/Docker Desktop/provider host.

GitHub Pages receives neither Python runtime and remains the mechanical static
profile.

The page-image gateway is intentionally **not** an Omega capability. It is a
narrow media transformer started by the operator, and successful image
generation does not imply any permission to save, install, publish, or mutate
a StickerBook world.
