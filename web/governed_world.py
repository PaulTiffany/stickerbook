"""Shared governed sticker vocabulary and page-world construction."""

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

# Shared sticker vocabulary offered by every governed page. Supply is unlimited: a screen has no reason
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

    # Round-four packs.
    "rooster": _definition("rooster", "crow", "step", "flap"),
    "bee": _definition("bee", "fly", "buzz"),
    "jellyfish": _definition("jellyfish", "pulse", "drift", "squish"),
    "pelican": _definition("pelican", "call", "flap", "glide"),
    "hula-hoop": _definition("hula-hoop", "sway", "spin"),
    "toy-airplane": _definition("toy-airplane", "bank", "zoom"),
    "asteroid": _definition("asteroid", "spin", "spark"),
    "space-station": _definition("space-station", "orbit", "beacon"),

    # H+ people pack.
    "ben-goertzel": _definition("ben-goertzel", "gesture", "think", "celebrate"),
    "aubrey-de-grey": _definition("aubrey-de-grey", "wave", "explain", "think"),
    "ray-kurzweil": _definition("ray-kurzweil", "present", "point", "think"),
    "david-eagleman": _definition("david-eagleman", "explain", "present", "think"),
    "nick-bostrom": _definition("nick-bostrom", "explain", "think", "present"),
    "max-more": _definition("max-more", "wave", "present", "think"),
    "natasha-vita-more": _definition("natasha-vita-more", "wave", "present", "think"),
    "eliezer-yudkowsky": _definition("eliezer-yudkowsky", "explain", "think", "present"),

    # Classic H+ people pack, round two.
    "fm-2030": _definition("fm-2030", "wave", "present", "think"),
    "robert-ettinger": _definition("robert-ettinger", "present", "think", "point"),
    "hans-moravec": _definition("hans-moravec", "explain", "think", "present"),
    "vernor-vinge": _definition("vernor-vinge", "wave", "think", "present"),
    "k-eric-drexler": _definition("k-eric-drexler", "explain", "point", "think"),
    "anders-sandberg": _definition("anders-sandberg", "wave", "present", "think"),
    "david-pearce": _definition("david-pearce", "gesture", "think", "present"),
    "martine-rothblatt": _definition("martine-rothblatt", "wave", "present", "celebrate"),

    # Cosmic engineers pack.
    "giulio-prisco": _definition("giulio-prisco", "cosmic", "book", "think"),
    "david-orban": _definition("david-orban", "explain", "point", "wave"),
    "paul-tiffany": _definition("paul-tiffany", "explain", "chalkboard", "poster"),
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


def build_world(page: int = 1, profile: str = "local-single-agent") -> Kernel:
    """Construct an empty governed world with shared definitions and principals."""
    kernel = Kernel(PROFILES[profile], assets=ASSETS, page=page)
    kernel.register_principal(Principal(HUMAN_ID, HUMAN, tools=HUMAN_TOOLS,
                                        delegable=frozenset()))
    kernel.register_principal(Principal(AGENT_ID, AGENT, tools=AGENT_TOOLS,
                                        delegable=frozenset()))
    return kernel
