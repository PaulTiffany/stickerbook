# Powered local product parity

The existing six scenes (`farm`, `beach`, `playground`, `space`, `school`,
`theater`) are governed local worlds. `web/book.py` reads page names, summaries,
and artwork metadata from the existing manifest. It creates worlds using the
shared definitions, principals, and tools in `web/governed_world.py`; `farm.py`
retains its compatibility facade and original Cow/Butterfly seeds. Other pages
start empty. No artwork or static/public provider access changes.

`POST /api/select-page {"page":"beach"}` selects a registered world. Unknown
or malformed ids are refused. `BookBridge` retains one page-local `Bridge`,
kernel, JevController, receipt history, path/input/interaction logs, replay log,
and trajectory execution log per page. Re-entering a page restores its world.
Every controller stays bound to its own kernel. Browser requests carry their
page identity; a delayed request cannot target a matching id on another page.

Switching pages clears transient demonstration/reference carry and advances an
activation token. Model answers from a previous activation are canceled before
submission, including when a child switches away and immediately back. Direct
gestures are atomic with selection; model think-time holds no world lock.

Learned patterns are deliberately book-wide, scoped by asset definition. They
are bounded advisory descriptions; they contain no world authority. Accepted
action history and geometry remain page-local, so remembering cannot silently
capture actions from another world. Provider/model selection carries across
page switches and does not influence page semantics.

The historical first Docker qualification is recorded in
`DOCKER_POWERED_LOCAL.md`. Its Farm-only limitation is superseded by this work.

## Double-tap improvisation

The old powered gesture offered only animation clips and NOOP for one turn.
The new gesture sends the existing `control` goal with `behavior: improvise`,
and offers the subject's current MOVE, ANIMATE, FACE and NOOP choices for at
most three decisions. Resize and other stickers are excluded. Every table,
scene and revision is rebuilt after an accepted step; provider think-time
holds no world lock. NOOP ends normally, an unknown key fails closed, and a
refused/stale step stops without retry. Same-subject human movement during
inference is reported as `human-superseded`; other-sticker movement does not
supersede it. Provenance remains human request, no translator, Jev selection,
ordinary kernel receipt.

Bounded `known_patterns` descriptions remain available to the chooser. A
terminal NOOP after accepted steps of that same gesture episode is treated as
the stop marker when remembering; it cannot erase the demonstration. A
first-turn NOOP cannot reach backwards into an older demonstration. No raw
historical action keys, transcript, model coordinates or command strings are
introduced. Static/public double-tap keeps its existing mechanical behavior.

Live qualification on the updated host bridge (`127.0.0.1:8758`) opened all
six pages. Sponsored ASI translated "Make the frog hop" on Beach; Jev's hop
receipt was accepted by Beach's kernel in 8.928 seconds total. A real direct
double-tap then selected three offered `MOVE:frog-1:STEP-E` keys against
revisions 2, 3 and 4. All three were accepted, moving x from .50 to .56 to .62
to .68 in 3.873 seconds, ending at the three-turn cap. All receipts had
`translatedBy: null`. Farm remained at its original Cow/Butterfly state;
re-entering Beach restored the frog at .68.

The exact reported conversational phrase, "yeah, the architecture should be
set up for you to direct Jev", succeeded under sponsored ASI in 12.209 seconds.
It produced a valid conversational reply and no semantic goal. There was
therefore no goal admission or Jev selection to fail; world state stayed
unchanged. The prior failure is not reproducible from that utterance alone,
and is not evidence of an animation-library defect.
