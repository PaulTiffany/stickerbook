"""Load and validate in-app help content.

The same checked-in JSON drives the browser's child/adult documentation.
Only the child branch is projected into OmegaLLM context.

Adult/operator guidance is deliberately never included in the model's scene.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

_HELP_PATH = Path(__file__).resolve().parent / "static" / "help.json"

_CHILD_KEYS = {"title", "intro", "topics"}
_ADULT_KEYS = {"title", "summary", "sections"}


def _load() -> dict:
    raw = json.loads(_HELP_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("unsupported help schema")
    child = raw.get("child")
    adult = raw.get("adult")
    if not isinstance(child, dict) or set(child) != _CHILD_KEYS:
        raise ValueError("invalid child help")
    if not isinstance(adult, dict) or set(adult) != _ADULT_KEYS:
        raise ValueError("invalid adult help")
    if not isinstance(child["topics"], list) or not child["topics"]:
        raise ValueError("child help must contain topics")
    if not isinstance(adult["sections"], list) or not adult["sections"]:
        raise ValueError("adult help must contain sections")
    return raw


def child_help_for_omega() -> dict:
    """Return a defensive copy of child-facing help only."""
    return copy.deepcopy(_load()["child"])


def full_help() -> dict:
    """Return the complete in-app help document for host-side tests/tools."""
    return copy.deepcopy(_load())
