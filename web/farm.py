"""
The farm page: host-owned scene definition.

A page is a passive backdrop plus stickers.

  * BACKDROP_FEATURES are painted scenery -- barn, pond, tree, fence. They
    are NOT kernel objects. Nothing can act on them, so the authority kernel
    has no reason to know they exist. They are here purely so the renderer
    can draw them and so slot names can refer to them.

A sticker's position is a coordinate, a fraction of the page (0.0-1.0), so
the renderer can scale it. A human drags anywhere; the kernel checks the
coordinate is on the page and that this principal may move this sticker.

There are no named slots. A sticker book whose stickers snap to five dots is
not a sticker book.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))

from stickerbook_core import (  # noqa: E402
    AGENT, ANIMATE_OWN_STICKER, AssetDef, HUMAN, Kernel, MOVE_STICKER,
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


ASSETS = {
    "cow": AssetDef("cow", ("none", "chew")),
    "butterfly": AssetDef("butterfly", ("none", "flutter")),
}

HUMAN_TOOLS = frozenset({
    OBSERVE, NOOP, MOVE_STICKER, ANIMATE_OWN_STICKER,
    REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER,
})
# Registered, but nothing drives this principal in this milestone.
AGENT_TOOLS = frozenset({OBSERVE, NOOP, MOVE_STICKER, ANIMATE_OWN_STICKER})


def build_world(profile: str = "local-single-agent") -> Kernel:
    """Construct the farm. The kernel learns the slot vocabulary and the two
    stickers; it is never told about the backdrop."""
    kernel = Kernel(PROFILES[profile], assets=ASSETS)
    kernel.register_principal(Principal(HUMAN_ID, HUMAN, tools=HUMAN_TOOLS,
                                        delegable=frozenset()))
    kernel.register_principal(Principal(AGENT_ID, AGENT, tools=AGENT_TOOLS,
                                        delegable=frozenset()))
    kernel.place_sticker(StickerInstance(
        "cow-1", HUMAN_ID, HUMAN_ID, "cow", 1, x=0.24, y=0.86))
    # Agent-owned provenance, kept so ownership stays visible. The human
    # can still drag it: the page belongs to the human.
    kernel.place_sticker(StickerInstance(
        "butterfly-1", AGENT_ID, AGENT_ID, "butterfly", 1, x=0.52, y=0.38))
    return kernel


def page_chrome() -> dict:
    """Everything the renderer needs that is not authoritative state."""
    return {
        "backdrop": {
            "description": "a small farm at midday",
            "features": BACKDROP_FEATURES,
        },

    }
