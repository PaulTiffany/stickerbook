"""
The farm page: host-owned scene definition.

A page is a passive backdrop plus stickers.

  * BACKDROP_FEATURES are painted scenery -- barn, pond, tree, fence. They
    are NOT kernel objects. Nothing can act on them, so the authority kernel
    has no reason to know they exist. They are here purely so the renderer
    can draw them and so slot names can refer to them.

  * SLOTS are host-owned named positions, and are the only legal destinations
    for a sticker. The kernel is told this vocabulary when the world is built
    and rejects anything outside it.

Pixel coordinates live here and in the browser. They are presentation and
input detail, never authority: `snap_to_slot` converts a pointer position
into one of the named slots on the host side, so the browser never chooses a
slot and cannot invent one.

Coordinates are fractions of the page (0.0-1.0) so the renderer can scale.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))

from stickerbook_core import (  # noqa: E402
    AGENT, ANIMATE_OWN_STICKER, AssetDef, HUMAN, Kernel, MOVE_OWN_STICKER,
    NOOP, OBSERVE, PROFILES, Principal, REMOVE_AGENT_STICKER,
    REMOVE_OWN_STICKER, StickerInstance,
)

HUMAN_ID = "human:kid"
AGENT_ID = "agent:jev-visual-1"

# Passive painted scenery. Not governed objects.
BACKDROP_FEATURES = [
    {"id": "barn", "x": 0.17, "y": 0.30},
    {"id": "tree", "x": 0.52, "y": 0.20},
    {"id": "pond", "x": 0.79, "y": 0.60},
    {"id": "fence", "x": 0.22, "y": 0.78},
]

# Host-owned named positions: the complete set of legal destinations.
SLOTS = {
    "by-the-barn": (0.30, 0.44),
    "under-the-tree": (0.52, 0.38),
    "by-the-pond": (0.76, 0.75),
    "by-the-fence": (0.24, 0.88),
    "in-the-field": (0.56, 0.70),
}

ASSETS = {
    "cow": AssetDef("cow", ("none", "chew")),
    "butterfly": AssetDef("butterfly", ("none", "flutter")),
}

HUMAN_TOOLS = frozenset({
    OBSERVE, NOOP, MOVE_OWN_STICKER, ANIMATE_OWN_STICKER,
    REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER,
})
# Registered, but nothing drives this principal in this milestone.
AGENT_TOOLS = frozenset({OBSERVE, NOOP, MOVE_OWN_STICKER, ANIMATE_OWN_STICKER})


def build_world(profile: str = "local-single-agent") -> Kernel:
    """Construct the farm. The kernel learns the slot vocabulary and the two
    stickers; it is never told about the backdrop."""
    kernel = Kernel(PROFILES[profile], assets=ASSETS, anchors=tuple(SLOTS))
    kernel.register_principal(Principal(HUMAN_ID, HUMAN, tools=HUMAN_TOOLS,
                                        delegable=frozenset()))
    kernel.register_principal(Principal(AGENT_ID, AGENT, tools=AGENT_TOOLS,
                                        delegable=frozenset()))
    kernel.place_sticker(StickerInstance(
        "cow-1", HUMAN_ID, HUMAN_ID, "cow", 1, anchor="by-the-fence"))
    # Agent-owned, so the ownership boundary is visible even with no agent
    # running: a human drag of this sticker is refused by the kernel.
    kernel.place_sticker(StickerInstance(
        "butterfly-1", AGENT_ID, AGENT_ID, "butterfly", 1,
        anchor="under-the-tree"))
    return kernel


def snap_to_slot(x, y) -> str:
    """Nearest slot to a pointer position. Host-side, total, and closed.

    Any input -- including nonsense from a modified browser -- resolves to
    exactly one legal slot or raises. The browser therefore cannot name a
    slot, invent one, or place a sticker between them.
    """
    try:
        px, py = float(x), float(y)
    except (TypeError, ValueError):
        raise ValueError("pointer position is not numeric")
    if not (px == px and py == py):          # NaN
        raise ValueError("pointer position is not a number")
    px = min(max(px, 0.0), 1.0)
    py = min(max(py, 0.0), 1.0)
    return min(SLOTS, key=lambda s: (SLOTS[s][0] - px) ** 2
               + (SLOTS[s][1] - py) ** 2)


def page_chrome() -> dict:
    """Everything the renderer needs that is not authoritative state."""
    return {
        "backdrop": {
            "description": "a small farm at midday",
            "features": BACKDROP_FEATURES,
        },
        "slots": [{"id": name, "x": xy[0], "y": xy[1]}
                  for name, xy in SLOTS.items()],
    }
