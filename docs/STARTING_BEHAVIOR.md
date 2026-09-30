# Advisory starting behavior

`web/starting_behavior.py` gives the shared sticker vocabulary small descriptive
starting tendencies: flowing curved flight, hopping with landing pauses,
swimming/paddling, short animal walks, scuttles, rolling/bouncing, floating,
and usually stationary expressive poses. Human figures and unknown/custom
definitions use the stationary/expressive fallback, with travel still available
when the child invites it. The module suggests at most three clips, all present
in the sticker's actual definition, and returns a fresh bounded dictionary.

OmegaLLM sees tendencies for the stickers present in its scene. OmegaJev sees
the active subject's tendency alongside current motion, target and remembered
patterns. Each entry explicitly says child direction and learned preferences
override the starting tendency. Host and provider context trimming remove the
generic tendency before child-taught patterns or native recall.

These are advisory priors, not motor macros, authoritative rules, new action
keys, coordinates or weight training. Legal tables, receipts, gesture provenance
and child interruption remain unchanged. New artwork does not automatically
acquire an inferred animal category. The child can still direct its behavior.

## Live qualification, September 30, 2026

An isolated Farm Butterfly recalled three native memories and chose CONTINUE
with flutter, then CONTINUE repeatedly: 20 accepted eastward positions in six
seconds. Starting tendencies did not guarantee a curved course there.

A fresh Butterfly on Beach initially recalled no memories. It chose
CURVE-LEFT+CLIP-flutter followed by CURVE-LEFT repeatedly, with decisions taking
0.305–0.440 seconds. Seventeen accepted positions traced a curve from
`(0.50,0.50)` through `(0.576590,0.472596)` to `(0.633069,0.353181)`.
The host stopped the test through the normal child-grab path. Later decisions
recalled newly recorded experiences. This is evidence of a curved course, not
proof of generally organic or diverse play, or of trained model weights.

The actual spoken reply now queues behind an acknowledgement already speaking.
Only audio delivery waits; the validated action path does not. Page exit and
voice disable still clear speech. Executable tests assert two queued utterances,
no intervening cancellation, busy-state ownership and page-exit cancellation.
Audio and visual motion were not manually observed in a browser this session.

523 web + 81 core + 40 Jev = **644 passing tests**. All shared definitions have
bounded advisory priors and declared clips; custom fallback, context precedence,
native memory preservation and the browser speech queue are covered.

Only Jev was recreated for its memory-priority change; named volumes and Docker
restrictions were preserved. OmegaLLM and existing host worlds stayed running.
Preview: `http://localhost:8765/?dev=1`, with the isolated Beach test state.
