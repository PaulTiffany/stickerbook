"""Canonical StickerBook page-art sizes, names, formats, and edit prompts.

These values define the presentation surface used by the browser and by the
non-authoritative page-image creation path. They do not grant authority over
StickerBook world state.
"""

from __future__ import annotations

import os
import re

LANDSCAPE_WIDTH = 1916
LANDSCAPE_HEIGHT = 717
PORTRAIT_WIDTH = 941
PORTRAIT_HEIGHT = 1574

SUPPORTED_IMAGE_TYPES = frozenset({
    "image/svg+xml",
    "image/png",
    "image/jpeg",
    "image/webp",
})

SUPPORTED_IMAGE_EXTENSIONS = frozenset({
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
})

LANDSCAPE_PROMPT = """**Edit the uploaded image.**
Use the uploaded image as the direct reference and preserve the artwork, style, colors, subject matter, and overall composition as closely as possible.
**Do not create a new scene. Do not reinterpret the content.**
Only **reframe / extend / outpaint** the image so the final canvas is exactly 1916 × 717.
Keep the result **very similar to the original artwork**, with any newly added areas matching the same visual style and content naturally.
If needed, **expand the background and surrounding scene**, rather than stretching or distorting the image.
Avoid adding unrelated new objects, text, or design elements."""

PORTRAIT_PROMPT = """**Edit the uploaded image.**
Use the uploaded image as the direct reference and preserve the artwork, style, colors, subject matter, and overall composition as closely as possible.
**Do not create a new scene. Do not reinterpret the content.**
Only **reframe / extend / outpaint** the image so the final canvas is exactly 941 × 1574.
Keep the result **very similar to the original artwork**, with any newly added areas matching the same visual style and content naturally.
If needed, **expand the background and surrounding scene**, rather than stretching or distorting the image.
Avoid adding unrelated new objects, text, or design elements."""

_TARGETS = {
    "landscape": {
        "width": LANDSCAPE_WIDTH,
        "height": LANDSCAPE_HEIGHT,
        "suffix": "",
        "prompt": LANDSCAPE_PROMPT,
    },
    "portrait": {
        "width": PORTRAIT_WIDTH,
        "height": PORTRAIT_HEIGHT,
        "suffix": "-vertical",
        "prompt": PORTRAIT_PROMPT,
    },
}

_SAFE_STEM = re.compile(r"[^A-Za-z0-9._-]+")


def supported_upload(filename: str, content_type: str) -> bool:
    """Return whether a child page upload is an allowed image type."""
    ext = os.path.splitext(filename or "")[1].lower()
    return (
        content_type in SUPPORTED_IMAGE_TYPES
        and ext in SUPPORTED_IMAGE_EXTENSIONS
    )


def safe_page_stem(filename: str) -> str:
    """Produce a filesystem-safe, deterministic stem for generated variants."""
    stem = os.path.splitext(os.path.basename(filename or "page"))[0].strip()
    stem = _SAFE_STEM.sub("-", stem).strip("._-")
    return stem[:80] or "page"


def variant_filename(filename: str, orientation: str, extension: str) -> str:
    """Return <stem>.<ext> or <stem>-vertical.<ext>."""
    target = _TARGETS[orientation]
    ext = extension.lower().lstrip(".")
    return f"{safe_page_stem(filename)}{target['suffix']}.{ext}"


def generation_plan(filename: str) -> dict:
    """Return the two exact edit jobs for one uploaded page image."""
    stem = safe_page_stem(filename)
    return {
        name: {
            "name": name,
            "stem": stem + target["suffix"],
            "width": target["width"],
            "height": target["height"],
            "prompt": target["prompt"],
        }
        for name, target in _TARGETS.items()
    }
