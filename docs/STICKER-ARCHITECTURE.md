# Sticker architecture

StickerBook separates **visual identity**, **pose**, and **world transforms** so
later Jev experiments have a small, inspectable substrate rather than an
animation system whose pixels secretly redefine world state.

## Three layers

```text
CATALOG
  StickerDefinitions installed in the book
        ↓ child selects
WORKING SHEET / HOTBAR
  a small convenient subset
        ↓ child places
PAGE
  StickerInstances with governed world state
```

The catalog may grow large. Discovery is therefore metadata-driven rather than
assuming every installed definition fits in one tile grid. The browser performs
deterministic local search over name, aliases, category and tags, with category
chips as a second filter. No model is involved in catalog search.

## StickerDefinition: reusable visual package

The installed visual manifest is version 4. A built-in definition may contain:

```json
{
  "name": "Butterfly",
  "category": "animals",
  "tags": ["butterfly", "insect", "flying", "garden"],
  "aliases": ["monarch"],
  "nominal_scale": 1,
  "scale_bounds": {"min": 0.9, "max": 1.1},
  "default_clip": "rest",
  "sprites": {
    "rest": ".../rest.svg",
    "wings-up": ".../wings-up.svg",
    "wings-down": ".../wings-down.svg",
    "land": ".../land.svg"
  },
  "clips": {
    "rest": {"frames": ["rest"], "loop": true},
    "flutter": {"frames": ["wings-up", "wings-down"], "loop": true},
    "land": {"frames": ["wings-down", "land", "rest"], "loop": false}
  }
}
```

Sprites are drawings. Clips are recipes over sprite names. A definition may
have any useful set of poses; only a default/rest clip is a common convention.

The first built-in tranche has nine definitions and four pose sprites per
definition. Four is a useful starting package, not a schema limit.

## StickerInstance: governed placement

A StickerInstance is one placement of a definition. Its authoritative state is:

```text
id
definition / asset
owner
created_by
page
x, y
scale
current clip
revision
```

The core currently keeps the historical field name `animation` for the current
clip so older callers remain wire-compatible. New visual code should reason in
terms of clips.

Position is normalized page-relative world state. Scale is also world state,
not an animation effect. The initial global scale envelope is **0.90–1.10**.
Definitions may tighten that envelope but may not widen it.

The current position invariant governs the sticker center in `[0,1] × [0,1]`.
It does not yet guarantee that every pixel of a scaled sticker remains inside
the page near an edge. Before live Jev locomotion, the host action generator
must account for footprint-safe destinations if that is the desired play rule.

## Rest is alive, not necessarily frozen

A rest clip may contain subtle non-locomotive sprite changes: blinking,
breathing, a bird looking around, a butterfly slowly opening its wings, or a
flower swaying.

Human grabbing immediately displays the **first rest frame** and suppresses
active visual transforms while held. This makes the physical sticker stable
under the pointer. When a human move is accepted, the authoritative current
clip becomes the definition's rest clip.

This is deliberately different from the old `animation = none` convention.

## Pose is not locomotion

A clip changes which sprite frame is depicted. It must not silently redefine
where the object is in the world.

```text
POSE / CLIP     rest → wings-up → wings-down → land
TRANSLATION     (x, y) → (x', y')
SCALE           1.00 → 0.98 → 0.94
```

The v4 built-in clips use frame sprites and do not declare the older CSS
`motion` transforms. Translation and apparent-depth scaling therefore remain
explicit governed state.

A future butterfly can appear to fly away in shallow "3D" by combining a flight
clip with bounded translation and scale changes. Jev does not need arbitrary
pixel or transform authority to obtain that effect.

## Authority and future OmegaJev play

The current local agent authority profiles permit bounded observation/no-op,
movement, clip selection, and resize. **Sticker removal is not in the agent
profile.** Humans retain removal, including removal of agent-created content.

Resize is a typed kernel action. Host-generated agent choices currently expose
only `SCALE:<sticker>:UP` / `DOWN` in 0.02 steps and only while another step
fits inside the definition bounds. The kernel independently validates the final
scale. A model never owns the numeric bound.

Jev is not yet wired into this browser sticker substrate. Do not infer model
capacity from the schema.

When that experiment begins, observation remains a capability:

- an object not explicitly declared in Jev's view does not exist to Jev;
- an action key must not leak an undeclared object merely by naming it;
- the host derives finite legal choices only from the declared view plus
  authority/world constraints;
- Jev selects a typed key; the host maps it to data; the kernel adjudicates it.

The intended play delegation is:

```text
Child
  > OmegaLLM
      > OmegaJev
          > host-generated legal choice table
              > authority kernel
                  > world
```

That ordering describes play control/delegation, not a bypass around the
kernel. Direct child manipulation preempts stale delegated agent intent.

## Experimental discipline

The purpose of this substrate is to make later experiments attributable. Before
asking how many stickers one Jev controller can handle, whether it learns useful
patterns, or how it responds to additional declared objects, keep pose,
translation, scale, observation and authority mechanically distinct.

Then model behavior can be measured rather than explained away as renderer
behavior.
