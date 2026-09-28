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
    ADD_OWN_STICKER, AGENT, ANIMATE_OWN_STICKER, StickerDefinition, HUMAN,
    Kernel, MOVE_STICKER, NOOP, OBSERVE, PROFILES, Principal,
    REMOVE_AGENT_STICKER, REMOVE_OWN_STICKER, RESIZE_OWN_STICKER,
    SET_STICKER_FACING, StickerInstance,
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


# What this page's tray offers. Supply is unlimited: a screen has no reason
# to run out, and a child expects it not to.
def _definition(name, *clips):
    return StickerDefinition(
        name, ("none", "rest") + tuple(clips), rest_animation="rest")


ASSETS = {
    # Shared / original set.
    "bird": _definition("bird", "flight", "land"),
    "butterfly": _definition("butterfly", "flutter", "land"),
    "frog": _definition("frog", "hop", "land"),
    "fish": _definition("fish", "swim", "dive"),
    "flower": _definition("flower", "sway", "bloom"),
    "cloud": _definition("cloud", "drift", "stretch"),
    "cow": _definition("cow", "chew", "look", "step"),
    "duck": _definition("duck", "paddle", "dive"),
    "hen": _definition("hen", "peck", "look", "flap"),

    # Farm pack.
    "horse": _definition("horse", "walk", "look"),
    "pig": _definition("pig", "sniff", "step"),
    "sheep": _definition("sheep", "walk", "look"),
    "goat": _definition("goat", "walk", "hop"),
    "tractor": _definition("tractor", "roll", "bounce"),
    "hay-bale": _definition("hay-bale", "wobble", "tumble"),

    # Beach pack.
    "crab": _definition("crab", "scuttle", "wave"),
    "starfish": _definition("starfish", "wiggle", "stretch"),
    "turtle": _definition("turtle", "swim", "tuck"),
    "dolphin": _definition("dolphin", "swim", "leap"),
    "umbrella": _definition("umbrella", "sway", "blow"),
    "shell": _definition("shell", "wiggle", "open"),

    # Playground pack.
    "ball": _definition("ball", "roll", "bounce"),
    "kite": _definition("kite", "sway", "dive"),
    "scooter": _definition("scooter", "roll", "lean"),
    "skateboard": _definition("skateboard", "roll", "tilt"),
    "balloon": _definition("balloon", "sway", "rise"),
    "frisbee": _definition("frisbee", "spin", "tilt"),

    # Space pack.
    "rocket": _definition("rocket", "thrust", "launch"),
    "astronaut": _definition("astronaut", "wave", "float"),
    "planet": _definition("planet", "spin", "glow"),
    "moon": _definition("moon", "wink", "glow"),
    "ufo": _definition("ufo", "hover", "beam"),
    "satellite": _definition("satellite", "orbit", "signal"),

    # Round-two packs.
    "puppy": _definition("puppy", "wag", "trot", "bark"),
    "cat": _definition("cat", "stretch", "walk", "pounce"),
    "seagull": _definition("seagull", "flap", "glide"),
    "sandcastle": _definition("sandcastle", "flag", "sparkle", "splash"),
    "pinwheel": _definition("pinwheel", "turn", "spin", "wind"),
    "jump-rope": _definition("jump-rope", "swing", "spin"),
    "alien": _definition("alien", "wave", "float", "hop"),
    "robot": _definition("robot", "wave", "roll", "beep"),

    # Round-three packs.
    "rabbit": _definition("rabbit", "sniff", "hop"),
    "scarecrow": _definition("scarecrow", "sway", "wave"),
    "octopus": _definition("octopus", "wave", "swim", "squish"),
    "surfboard": _definition("surfboard", "sway", "ride"),
    "yo-yo": _definition("yo-yo", "drop", "spin", "return"),
    "teddy-bear": _definition("teddy-bear", "wave", "hug", "bounce"),
    "comet": _definition("comet", "glow", "swoop", "spark"),
    "rover": _definition("rover", "roll", "scan"),
}

HUMAN_TOOLS = frozenset({
    OBSERVE, NOOP, ADD_OWN_STICKER, MOVE_STICKER, ANIMATE_OWN_STICKER,
    RESIZE_OWN_STICKER, SET_STICKER_FACING,
    REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER,
})
# Registered, but nothing drives this principal in this milestone.
AGENT_TOOLS = frozenset({
    OBSERVE, NOOP, MOVE_STICKER, ANIMATE_OWN_STICKER, RESIZE_OWN_STICKER,
    SET_STICKER_FACING,
})


def build_world(profile: str = "local-single-agent") -> Kernel:
    """Construct the farm. The kernel learns the slot vocabulary and the two
    stickers; it is never told about the backdrop."""
    kernel = Kernel(PROFILES[profile], assets=ASSETS)
    kernel.register_principal(Principal(HUMAN_ID, HUMAN, tools=HUMAN_TOOLS,
                                        delegable=frozenset()))
    kernel.register_principal(Principal(AGENT_ID, AGENT, tools=AGENT_TOOLS,
                                        delegable=frozenset()))
    kernel.place_sticker(StickerInstance(
        "cow-1", HUMAN_ID, HUMAN_ID, "cow", 1,
        x=0.24, y=0.86, animation="rest"))
    # Agent-owned provenance, kept so ownership stays visible. The human
    # can still drag it: the page belongs to the human.
    kernel.place_sticker(StickerInstance(
        "butterfly-1", AGENT_ID, AGENT_ID, "butterfly", 1,
        x=0.52, y=0.38, animation="rest"))
    return kernel


def page_chrome() -> dict:
    """Everything the renderer needs that is not authoritative state."""
    return {
        "picture": {
            "description": "a small farm at midday",
            "features": BACKDROP_FEATURES,
        },
        "tray": sorted(ASSETS),

    }
