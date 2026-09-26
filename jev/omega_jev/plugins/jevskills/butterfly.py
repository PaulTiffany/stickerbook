"""
Toy StickerBook scene state for the Stage 3 demonstration.

This is NOT the StickerBook animation system. It is the smallest possible
stand-in that shows the shape of the eventual architecture:

    the host owns the world; the agent receives a view and a set of legal moves.

The sticker id and the animation names live here, in host source. The two
skills take NO arguments, so there is nothing for Jev to supply: it can only
choose which pre-authorised motion happens next.

State lives in the agent's one writable directory (memory/), so writing it
does not require relaxing the filesystem policy.
"""

import json
import os

STATE_PATH = os.environ.get(
    "JEV_SCENE_PATH", "/PeTTa/repos/Omega/memory/jev_butterfly.json"
)

# Host-owned enumeration. Jev cannot extend it.
VALID_STATES = ("resting", "fluttering")


def _read():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("butterfly") in VALID_STATES:
            return data
    except Exception:
        pass
    return {"butterfly": "resting"}


def _write(state):
    if state not in VALID_STATES:
        # Unreachable from Jev; a guard against our own mistakes.
        return "BUTTERFLY-REJECTED invalid state"
    previous = _read().get("butterfly", "resting")
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump({"butterfly": state}, handle)
    return "BUTTERFLY %s -> %s" % (previous, state)


def flutter():
    """Skill body for butterfly-flutter. Takes no arguments by design."""
    return _write("fluttering")


def rest():
    """Skill body for butterfly-rest. Takes no arguments by design."""
    return _write("resting")


def describe():
    """The 'view' handed to the agent: current scene state, host-composed."""
    return _read().get("butterfly", "resting")
