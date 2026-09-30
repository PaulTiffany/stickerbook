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


## Phase B: ongoing child invitations, finite steering

The command-line local host enables continuous motion. The test/embedding
`Bridge` and `serve` constructors retain an explicit `continuous_motion` option
so the existing finite pattern/trajectory controller can be tested independently.
Public GitHub Pages never enables the host player and retains mechanical behavior.
No container rebuild, provider/model switch, artwork change, or OpenShell work
was needed.

`MotionPlayer` retains a child invitation per active subject (maximum eight).
Double-tap starts `control / improvise` with human:kid provenance and no OmegaLLM
translator. A valid ordinary OmegaLLM semantic goal installs/replaces an
invitation, preserving existing heading and speed; a pose-only direction also
retains its existing target. Explicit stop/rest/land/still directions revoke
travel and give Jev a bounded legal pose choice. Explicit scale goals and pattern/trajectory intents
keep their existing finite execution contracts, rather than becoming new loops.

The offered body vocabulary contains:

- continue, left/right small (22.5 degrees), left/right large (45 degrees);
- eight starting compass headings on a sixteen-heading lattice;
- three stride speeds (.035, .055, .080 page fractions/second), slow/faster;
- toward an existing semantic target and short left/right arcs around it;
- declared clips, facing, and offered clip-plus-steering combinations;
- STOP/NOOP to cut the current continuation and pause before a new decision.

All are current-state-derived, finite, subject-only choices. Resize, commands for
other objects, model-authored coordinates, clips, or executable strings are absent.
Target-relative steering senses only the already-admitted target; it does not
install a whole circle or canned swoop. Each target-relative tick quantizes a
heading from current kernel geometry and proposes a bounded local move.

The scene supplies last accepted delta, heading, speed, moving/remaining ticks,
bounded recent-turn count, target bearing/distance/proximity and approach trend.
Existing known patterns remain advisory: at most eight descriptions, with two
typed step previews and an explicit omitted count, further limited by the existing
4,000-character Decisions state ceiling. Keys already appear in criteria and are
not duplicated in state. A real run falsified an earlier oversized context;
the final code compacts the context instead of weakening that ceiling. Tests
exercise the actual `jev_core.build_request` validator with target and memory.

A single Jev choice grants **at most six ticks of .25 seconds** (1.5 seconds),
not an unlimited macro. A remote decision is requested during that short travel,
so about one decision/second can coexist with about four host moves/second and
frame-rate rendering. If inference is late the continuation exhausts and waits;
there is no invisible unlimited coasting. STOP/NOOP ends the small continuation,
not the child's ongoing invitation; another explicit Jev choice is needed to
move again. A fresh observation lease renews an existing invitation, never creates
one. Missing observations for four seconds stop play. Closing/hiding/leaving a
page sends an explicit pause; switching pages invalidates old decisions.

Every continued move follows:

    offered steering intent -> validated Jev key
    -> host checks page activation, child revocation and expected subject revision
    -> host reads current kernel geometry and generates one bounded endpoint
    -> ordinary MOVE_STICKER proposal against that snapshot revision
    -> kernel acceptance/refusal -> receipt -> authoritative state -> browser tween

Steering intents are deliberately distinct from old absolute-coordinate action
tables: no destination from an old model snapshot is silently rebased. The model
cannot replace the endpoint. All motor/pose proposals retain requestedBy human:kid
and selectedBy OmegaJev, plus translatedBy OmegaLLM only for spoken/typed goals.
All motion receipts are auditable in a bounded `/api/motion` observation ring.

Grab cancels the tween immediately and sends `/api/hold` to revoke the subject's
player. The hold returns a fresh authoritative revision before the release is
proposed; a missed last motor tick cannot falsely block the child's drag.
The node stays pointer-owned while polls incorporate other world changes. No
late motor decision or prior linguistic turn can restart the held subject. A
finite pose decision also checks the child epoch. Existing stale-revision and
human-superseded tests for finite loops continue to pass. Other-sticker movement
does not revoke this subject. A departed-page mouse release cannot target a new
page, even when an instance id happens to match.

## Live evidence and limits

The real sponsored ASI lane remained `minimax/minimax-m3`; Jev remained OpenRouter
`typesafe/jev-1.13`. OpenRouter's existing OmegaLLM fallback remained configured.

The final instrumented renderer run asked the real system to swoop toward a box,
then circle near the tree, double-tapped Butterfly, and asked it to land. Its
semantic replies/admission took 17.154, 14.652 and 8.198 seconds respectively;
double-tap was acknowledged in .009 seconds. Existing motion continued while the
next linguistic direction was being interpreted.

For the first nine seconds after swoop admission: seven real Jev decisions
(mean .997 seconds), 31 accepted moves, with flutter concurrent with travel.
Selected positions from its receipt audit:

| elapsed motor seconds | revision | accepted x,y |
|---:|---:|---|
| .000 | 4 | .529723,.389723 |
| .273 | 5 | .539446,.399446 |
| .552 | 6 | .549169,.409169 |
| .824 | 7 | .558892,.418892 |
| 1.096 | 8 | .568615,.428615 |
| 1.364 | 9 | .578338,.438338 |
| 1.639 | 10 | .588061,.448061 |

The initial key was `TOWARD-TARGET+CLIP-flutter`, followed largely by CONTINUE.
It later corrected past the target. This is a smoothly interpolated diagonal
approach and correction, **not a recognizably swooping course**. The tree request
made five decisions (mean 1.127 seconds) and 25 moves, with non-axis headings
changing between roughly -135 and -113 degrees. It approached the tree rather
than making a convincing circle.

The real double-tap made six decisions (mean 1.077 seconds) and 28 moves during
its nine-second sample, with flutter and eastward travel from .50 to .885. Play
continued beyond the old three-turn cap. Across the run, the actual renderer
functions processed 169 authoritative observations and 1,428 position paints,
including 1,278 intermediate positions between endpoints. Animation players
remain attached across positional updates. Interpolation issued zero proposals.
This was an SVG/frame harness connected to real HTTP/providers; it is not a claim
of a human visual inspection. Paul waived that inspection after the UI tool
blocked it. Pixel-level perception and whether this feels organic remain for
child/operator review.

A further real circle request with the final around-target vocabulary took
12.865 seconds to interpret and selected seven decisions / 33 moves. Jev still
preferred toward/continue, producing a northward approach and corrections near
the target, not a circle. This is a retained falsification: an offered expressive
body does not itself guarantee good expressive selection. The host does not
force an around-target key merely to improve the result.

That run's child grab/release was accepted at revision 38 -> 39, put Butterfly
at .42,.42 in its rest clip, and left no activity. After waiting for a potentially
late decision, there was no autonomous restart. State reads averaged .012 seconds.
The earlier continuous run also recorded .013-second average state reads.

The current body is materially more continuous than a final-state teleport, but
calling its behavior organic would overstate the evidence. ASI linguistic latency
still delays a new spoken direction; immediate grabbing remains available.
Serialized decisions and finite continuation limits can produce pauses under
slow inference or many simultaneously active stickers. The existing kernel's
in-memory receipt/idempotency history and process-lifetime world state are
unchanged; production long-session retention is outside this local tranche.

Discrete pattern memory is **not** continuous movement-style learning. Motor
BODY ticks are recorded as accepted geometry in audit/history but deliberately
carry no learnable discrete key, rather than storing a meaningless BODY pattern.
Existing taught patterns remain advisory. Captured child paths now have visible
polylines alongside their reference boxes; naming, persisting and applying a
child-taught continuous motif/style remain future work.


## Verification

Final local checks: 476 web tests, 81 core authority tests, and 40 Jev tests
passed (597 total), plus JavaScript syntax and the existing runtime static
contract. Coverage includes real Decisions context bounds, all existing sticker
catalogs fitting RPC action limits, one-choice tick limits, fresh per-tick
receipts, arbitrary key/coordinate refusal, curved finite steering, clip/motion
coexistence, same/different-subject intervention, pending-pose cancellation,
late-language cancellation, lease expiry, page switching, fresh grab revisions,
pointer-owned stable nodes, departed-page releases, mechanical-only public
behavior, and independent threaded HTTP reads during blocked Jev think-time.
