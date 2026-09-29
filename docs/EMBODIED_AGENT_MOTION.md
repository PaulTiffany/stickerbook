# Embodied local motion

## Phase A: observe existing governed motion

The old UI awaited the entire semantic/Jev request, then destroyed/recreated
sticker nodes at the final state. Accepted intermediate positions were invisible.
The browser now observes `/api/state?watch=1` every 125 ms during powered requests.
These fast reads omit repeated provider health probes. Sticker identity and clip
players are reconciled; each accepted positional endpoint is tweened over 220 ms.
Frame coordinates are presentation only: no kernel proposals, receipts, or agent
scene facts originate from interpolation. Lower revisions and departed-page
responses are ignored. A held sticker has exclusive pointer-owned presentation.
Page selection/exit cancels pending frames and invalidates outstanding observers.

Before changing Jev semantics, a real ASI/OpenRouter request ?Butterfly, swoop
toward that square? took 16.838 seconds. Renderer observations:

| elapsed ms | revision | Butterfly x,y |
|---:|---:|---|
| 61 | 2 | .52,.38 |
| 10164 | 3 | .58,.44 |
| 11433 | 4 | .64,.50 |
| 12680 | 5 | .64,.50 (flutter clip) |
| 13932 | 6 | .70,.56 |
| 15334 | 7 | .76,.62 |

The final response arrived after these observations. Four MOVE receipts plus one
ANIMATE receipt were accepted; NOOP ended normally. The actual renderer functions
were driven from real HTTP state reads using a frame/SVG harness. This proves
endpoint delivery and interpolation, not a human visual/organic assessment.
Windows browser inspection was unavailable, and Paul subsequently waived it.
The course remains compass-stepped and hesitant between remote decisions.

Background mouse drags previously displayed only an endpoint bounding box even
though bounded geometric samples were captured. They now also display those
samples as a polyline; the existing box/reference and governed evidence semantics
are preserved. This is observation of input, not movement-style learning.
