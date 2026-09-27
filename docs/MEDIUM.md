# StickerBook as a medium

> The medium is not decorative packaging around the agent architecture.
> **The medium is the experiment.**

## Why a sticker book

StickerBook begins from a very old and very comprehensible human activity:
somebody has a surface, some pieces, and the freedom to arrange those pieces
into a little world. The child does not need an ontology, an authority
system, coordinates, a model or a planner. They understand *this cow, that
pond, put it there*. Meaning arises through placement, juxtaposition,
repetition, surprise and narration.

That matters because it gives human intention a tactile form **before** any
machine enters the picture. The child makes the first mark. The arrangement
is theirs. An agent arrives at a surface that is already meaningful, and may
respond to it, animate within it, contribute to it, or help extend it.

So the research direction is inverted from the usual one:

```
usual:  start with an autonomous agent  ->  bolt on a human interface
here:   start with a human medium       ->  ask what machine agency can
                                            inhabit it without consuming it
```

A sticker book is unusually well suited to this because **its semantics are
legible**. Moving a butterfly beside a tree is visible. Adding a duck is
visible. Making the butterfly flutter is visible. Removing something is
visible. Agency has its effects on a shared surface rather than disappearing
into hidden state or a long transcript.

## The Chalked connection

A shared surface can carry marks that different observers read differently.

The child sees a painted barn. The page's author may additionally have
marked that barn as a named **place**. An agent receives a bounded semantic
projection saying a barn exists at some location. Those three representations
coexist without ever becoming identical.

> A signpost helps another observer orient itself. It does not turn the
> signified thing into something that observer owns.

This is why the layering matters:

```
picture   !=   place   !=   sticker
```

* the **picture** supplies visual context
* a **place** supplies shared reference
* a **sticker** is an actual participant in the mutable composition

And it generalises past "near the lightpost". The page is a small shared
world whose participants hold different sensory and semantic projections of
it while still meeting on one inspectable surface. A child can point. A page
author can label. A renderer uses coordinates. Jev discriminates among
semantic alternatives. Some future agent may reason linguistically. They can
all meet at the page **without pretending to be the same kind of observer**.

That is much closer to the research goal than making an AI-powered toy.

## The child-centred constraint is an architectural discipline

We are not using children as test subjects for an agent architecture.
Designing a medium that *could eventually be appropriate for a child*
imposes unusually healthy requirements: actions should be visible,
comprehensible, bounded, reversible where possible, and subordinate to the
person's creative activity.

The working test:

> If we need a security console to explain what the butterfly just did, we
> have failed at the medium.

What the child should experience is **"I made a scene, and sometimes the
scene comes alive"** — not "I am supervising an autonomous system."

---

## 1. What a physical sticker book actually is

- **The book is a home for pages.** You move between them.
- **The page is printed and fixed.** It is context, not content. You cannot
  edit the barn.
- **Stickers arrive on a separate sheet**, outside the page until placed.
- **Placement is two decisions:** *which one* (selection) and *where*
  (position). Physical books separate these with a gesture: peel, then press.
- **Reusable books are the right model.** Stickers come off and go back; the
  child rearranges endlessly and nothing is ever committed.
- **The current arrangement is the whole truth.** No history — just what is
  on the page now.
- **Overlap and layering are meaningful.** Putting the cow *behind* the
  fence is a deliberate act.
- **Nothing is validated.** You may put the cow in the sky. This is a
  feature. The art *suggests* where things go; the child decides.
- **The child narrates.** The arrangement is a story they tell. That is the
  product.

What digital adds is not correctness. It is **supply** (never run out),
**reversibility** (undo), and **life** (the page can respond). Of those,
life is the only one worth building a research project around.

What digital must not lose: the tactility of grab-and-place, and permission
to do the "wrong" thing.

### A digital sticker book is not necessarily a linear book

A physical book has page 1, 2, 3 because sheets have to be bound in an
order. Ours do not. Do not inherit that limitation by accident.

```
book = a home / collection for pages          <- this
book = an ordered array of pages              <- not necessarily this
```

A page should stand on its own and later participate in many forms of
organisation: something made yesterday, something made by someone known,
something shared where appropriate, a thematic link, or simply a new blank
page. *"Where do you want to go?"* may end up making more sense than
*"next page"*.

**Do not build social discovery or networking.** This is recorded so the
product is not accidentally designed around permanent previous/next arrows
and later discovered to be a linear reader. Ordering is one optional
relationship among pages, not their defining structure.

## 2. What the child-facing page should feel like

The page is the screen — not a panel in a layout, but the thing itself,
framed like a book spread, art edge to edge.

A **tray along the bottom** holds stickers waiting to be used: a sheet,
visibly separate from the page. Bottom placement is deliberate — it echoes
the physical sticker sheet below the page, keeps the picture visually
dominant, and suits drag-up-to-place.

```
+-------------------------------+
|                               |
|           FARM PAGE           |
|                               |
+-------------------------------+
|   cow   butterfly   duck ...  |   sticker tray
+-------------------------------+
```

Stickers should invite grabbing: a lift and shadow under the pointer,
settling when released. A child's read of "can I touch this?" should come
from how it looks, not from a label.

Nothing numeric. No revision, no principal, no owner tag, no receipt, no
word "kernel". If a move is refused, the sticker simply does not go — the
same feedback a real sticker gives when it will not stick.

When the agent eventually does something, it shows up as the butterfly
starting to flutter. Not as a notification.

## 3. Product UI versus instrumentation

| Element | Verdict |
|---|---|
| The page, picture, stickers | **Product** — the art must dominate |
| Sticker id labels (`cow-1`) | Instrumentation |
| Owner tags (`owned by agent:…`) | Instrumentation |
| Revision counter | Instrumentation |
| "acting as human:kid" | Instrumentation |
| Verdict line | Instrumentation; the child-facing version is the sticker not moving |
| Receipt stream | Instrumentation — and our best evidence, so keep it |
| Sticker tray | **Product, and was missing** |

The proof harness stays, behind a developer view (`?dev=1`). We lose the
ability to demonstrate the boundary if the receipts disappear.

## 4. Keeping the three layers distinct

| Layer | What it is | Mutable at play time? | Governed by the kernel? |
|---|---|---|---|
| **Picture** | The illustration: barn, pond, tree, sky | No | No |
| **Places** | Named signs *about* the picture: "the barn is here" | No | No |
| **Stickers** | Identity, position, provenance, state | Yes | Yes — the only governed objects |

The rule that keeps this clean:

> **A place is a coordinate vocabulary, not an object.** It answers *"where
> is the barn?"*. It never answers *"who may move the barn?"* — because
> nothing may.

Promoting a sign into a governed object is what made "near the lightpost"
undecidable in the earlier forest experiment. Places live in page data,
above the kernel; the host resolves them to coordinates; **the kernel only
ever sees coordinates and sticker ids.** No new security machinery is needed
for any of this.

Sticker books do not enforce plausibility, so places must not silently
become placement rules ("ducks only in the pond"). If that is ever wanted it
is a page-authored rule and deserves its own review.

## 5. A future "Create New Page" workflow

Sketched, not designed:

```
choose or upload a picture
        |
click a spot  -> name it      "barn"
click a spot  -> name it      "pond"
mark an area  -> name it      "sky"
        |
save: picture + named places + which stickers this page offers
```

Start with **named points** — enough for every "near X" question, which is
most of them. Add **regions** only when "in the sky" matters, because that
needs containment rather than proximity.

Resist a taxonomy. No "this place is a water feature". A name and a
location. The page author's words are the vocabulary; that is the point of a
shared surface.

Later a model could propose annotations from an uploaded picture and a human
accept or correct them. Keep provenance on each place — authored, or
suggested-and-accepted. The human stays the authority on whether a sign is
right; the machine only drafts.

## 6. How places let an agent say "near the lightpost"

Both directions run through the host, and the kernel learns nothing about
barns:

```
DESCRIBING   cow at (0.31, 0.78)  ->  host tests against places
                                  ->  "the cow is near the barn"

INTENDING    agent chooses: put the butterfly NEAR the lightpost
             host resolves: lightpost -> (0.62, 0.31); "near" -> an offset
             host proposes: move  butterfly-1  x=0.64 y=0.34
             kernel decides
```

The agent's surface stays **finite and enumerable** — sticker x relation x
place — while the coordinate space stays **continuous** for the human
pointing at the page. Neither party needs the other's vocabulary.

"Near" is fuzzy and the host owns the fuzziness. Radius belongs in page
data: a sprawling meadow and a cramped kitchen want different answers.

## 7. Vocabulary

| Child / UI | Implementation | Note |
|---|---|---|
| book | *(none yet)* | a home for pages, not an ordered array |
| page | Page | |
| picture | *(page art asset)* | never "backdrop" to a child |
| place | Place | named point or region in the picture |
| sticker | StickerInstance | shared word: the concept genuinely matches |
| sticker tray | *(tray / sheet)* | where unplaced stickers live |
| put / move / take off | add / move / remove commands | |
| — | Principal, Receipt, revision, AuthorityProfile, Command, Kernel | **never surfaced** |

Two notes. **"Sticker" stays shared** — inventing a separate internal word
for something the child already names correctly is pure friction. And
`human:kid` is a poor identifier: the person testing the page is a *player*,
neither a kid nor the operator. When renaming eventually happens,
`player` / `operator` / `agent` internally and nothing at all in the UI.

Let the user-facing vocabulary stabilise before any broad internal rename.

## 8. Known inconsistency

Removal is split across two action names — `remove-own-sticker`
(owner-scoped) and `remove-agent-sticker` — while `move` has been unified
into "the human may move anything on their page". Taking a sticker off the
page should not need a different verb depending on who put it there, since
no child could perceive the difference. This is a vocabulary inconsistency,
not a hole in the security model, and is noted here to be resolved
deliberately rather than during unrelated work.
