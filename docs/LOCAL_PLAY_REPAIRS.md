# Live local play and image creation repairs

Docker logs from the live session showed OmegaLLM timing out and refusing
responses with no usable content. Neither Omega container had exited. The
creator was independently unwired: its adapter always advertised false and
returned `creator-agent-unavailable`.

## Motor and loop changes

The existing LEFT/RIGHT choices changed heading once, then continued straight
for up to six ticks. New CURVE-LEFT/RIGHT choices bend by a host-defined 5.625
degrees on each tick. Endpoints use a finite 64-heading refinement of the
existing 16-heading representation. No model coordinates or command strings
are accepted. Each continuation still has at most six 250ms ticks, independently
accepted/refused by the kernel. Curves retain the body's current heading when
an inference returns, so motion during think-time is not rewound. Target-relative
steering uses the same finer heading refinement. Clips remain independent.

Jev's unused post-input loops are reduced from eight to one; polling sleep is
100ms rather than one second. The generated history prompt is disabled for both
RPC providers, which already ignore it. Their separate native Omega stores and
bounded recall remain enabled and persisted. No memory volumes were deleted.

ASI Cloud still uses locked `minimax/minimax-m3`. Its request now explicitly
selects low reasoning effort and permits 4096 completion tokens, because
reasoning also consumes that budget. Visible replies remain capped at 1000
characters and goals retain the existing schema. A probe succeeded with these
settings; this is not a guarantee of low latency. Empty content and exhausted
output budget receive distinct bounded diagnostics and child-facing messages.
Parsing is not weakened and failed responses never become mutations. OpenRouter
GLM-5.2 remains an explicit text fallback.

## Four-frame sticker creation

The child has one creation path: describe a sticker and receive four poses for
a looping animation. The still/move/frames selectors are removed.

OmegaLLM's container handles a separate bounded `/create` image-draft request
using its existing OpenRouter credential. This does not use MiniMax as an image
generator or expose the key to the host/browser. The selected image model is
`openai/gpt-image-1-mini`, using the documented
[OpenRouter Image API](https://openrouter.ai/docs/guides/overview/multimodal/image-generation).
The [image model catalog](https://openrouter.ai/api/v1/images/models) advertises
transparent output and reference-image support for this model.

One transparent 2-by-2 sprite sheet supplies consistent successive poses.
The container decodes the PNG with Pillow, bounds source dimensions to 4096,
splits the four cells, and produces four 256-square PNG frames. The host accepts
only bounded PNG data and expected dimensions, writes UUID-named files beneath
its existing generated-art directory, and returns same-origin preview URLs.
No model URL, asset identifier, script, capability, or owner is imported.

The child explicitly chooses **Add to my stickers**. The host assigns the design
ID and fixed `none/rest/play` vocabulary. Generation and design acceptance
produce no sticker placements or movement receipts. Placing the design uses the
ordinary child proposal and kernel receipt. Jev can combine its legal `play`
clip with its legal body steering, exactly as for existing stickers.

The image job has its own 320-second client deadline and 10MiB response bound;
it does not block conversational decisions, state reads, or child gestures.
Only one image-generation job can run at once. Drafts are limited to eight and
accepted designs to 32 per page session. Image creation does not change Docker
mounts, networks, user, capabilities, or root filesystem restrictions.

Page description generation now returns landscape and portrait raster artwork
with previews and save links. These are drafts, not new governed book registry
entries. The existing separate upload/reframe gateway remains an optional path.
Public Pages still neither calls providers nor accepts real generated designs.

Accepted generated designs are retained across browser reloads in the host page
session, but their catalog does not yet survive bridge restart. PNG files remain
under ignored `web/generated_pages`; this directory has no physical disk quota.
Generated poses can vary in alignment/quality: the fixed grid is mechanically
split, not a learned animation rig. Full persistent custom-book editing remains
future work.

## Live results and limits

- A transparent purple dragon produced four poses in 13.672 seconds.
- A blue bird produced four poses in 14.227 seconds, entered the library, and
  was placed through an accepted child kernel receipt.
- A woodland page produced 1916-by-717 and 941-by-1574 artwork in 36.566 seconds.
- "Butterfly, swoop around the cow" translated successfully in 35.195 seconds.
  Jev selected target approach then curves, with 0.318–0.648 second decisions.
  Its accepted positions traced an arc, but not a neatly cow-centered orbit.
- "Stop the butterfly and leave it landed" succeeded in 18.088 seconds, with
  an accepted `land` clip receipt.
- After the live-heading curve fix, double-tap selected CURVE-LEFT + flutter,
  then more CURVE-LEFT choices in 0.333–0.574 seconds. Seventeen accepted moves
  smoothly changed their geometric heading from east toward north and west.
  A grab stopped play in 3ms. The browser still interpolates accepted endpoints;
  interpolation generates no additional receipts.

The browser connector exposed no available browser, so these results prove the
actual receipt geometry and raster output, not a fresh visual assessment of
browser smoothness. Language latency is still variable and occasionally slow.
Target fidelity, behavioral diversity, and child-taught continuous style are
not solved by adding curves. This remains local powered development with
ordinary Docker, not OpenShell-equivalent containment.
