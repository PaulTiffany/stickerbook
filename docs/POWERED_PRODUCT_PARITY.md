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
