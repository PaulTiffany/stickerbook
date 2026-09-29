"""Farm compatibility facade and its original seeded scene."""
from governed_world import (ASSETS, HUMAN_ID, AGENT_ID, HUMAN_TOOLS, AGENT_TOOLS,
                            StickerInstance, Kernel, build_world as empty_world)

# Passive painted scenery. Not governed objects.
BACKDROP_FEATURES = [
    {"id": "barn", "x": 0.17, "y": 0.30},
    {"id": "tree", "x": 0.52, "y": 0.20},
    {"id": "pond", "x": 0.79, "y": 0.60},
    {"id": "fence", "x": 0.22, "y": 0.78},
]


def build_world(profile: str = "local-single-agent") -> Kernel:
    kernel = empty_world(profile=profile)
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
