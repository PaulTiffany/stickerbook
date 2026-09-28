# Conversational Omega interface

StickerBook separates conversation, decision selection, and authority.

> **Omega talks. Jev chooses. The kernel decides.**

These are different interfaces and should remain different even if one model
or process eventually participates in more than one role.

## Conversation is not authority

The browser can send human language to the local conversational runtime through:

`POST /api/agent/converse`

The bridge validates the input and fixes the acting principal. The runtime
receives only:

- the validated text;
- the fixed browser principal id;
- a JSON scene view returned by the normal browser view.

It does **not** receive the authority-kernel object through this interface.

The response is language only. It does not mutate scene state and it does not
become a kernel command merely because Omega suggested something.

If a conversational Omega wants an in-world action, that action must enter the
same bounded path as other machine action: legal choices, typed selection,
host validation, and kernel adjudication.

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
currently bounded to 0.90–1.10 globally, and the host-generated agent action
table offers only bounded 0.02 scale steps. Facing is a typed left/right
transform with host-generated FACE choices. The kernel validates both
independently.

The current local agent authority profiles intentionally contain no sticker
removal capability. Human control retains removal. This is non-representability,
not a prompt instruction.

Jev integration is still a future experiment. When connected, its scene view
must contain only explicitly declared objects/state, and a generated action key
must not reveal an undeclared object merely by naming it. The intended play
delegation is Child > OmegaLLM > OmegaJev, while the authority kernel remains
the independent gate beneath all three.

## Default runtime

`web/agent_runtime.py` ships with `DisabledAgentRuntime`.

It advertises no creator or conversational capability and performs no network
access. GitHub Pages never receives this Python runtime at all; Pages remains
the mechanical static profile.

A future local Omega adapter should implement the same small interface rather
than reaching around the bridge into the kernel.

The page-image gateway is intentionally **not** an Omega capability. It is a
narrow media transformer started by the operator, and successful image
generation does not imply any permission to save, install, publish, or mutate
a StickerBook world.
