"""
stickerbook_core -- the StickerBook authority kernel.

Headless and renderer-free by design: the security model is testable without
pixels. Standard library only.

See ../../SECURITY.md for the requirements this implements, and
../tests/test_authority.py for the mechanical proofs.
"""

from .kernel import Kernel
from .model import (
    ADD_OWN_STICKER, AGENT, ALL_ACTIONS, ANIMATE_OWN_STICKER,
    StickerDefinition, CREATE_AGENT, Command, HUMAN, LOCAL_MULTI_AGENT,
    LOCAL_SINGLE_AGENT, MOVE_STICKER, MUTATING_ACTIONS, NOOP, OBSERVE,
    OPERATOR, PAGES_DEMO, POSITION_MAX, POSITION_MIN, PROFILES, Principal,
    Receipt, REMOVE_AGENT_STICKER, REMOVE_OWN_STICKER, RESIZE_OWN_STICKER,
    SCALE_MAX, SCALE_MIN, SET_STICKER_FACING, StickerInstance,
)

__all__ = [
    "Kernel", "Principal", "StickerInstance", "StickerDefinition", "Command",
    "Receipt", "PROFILES", "PAGES_DEMO", "LOCAL_SINGLE_AGENT",
    "LOCAL_MULTI_AGENT", "HUMAN", "AGENT", "OPERATOR", "ALL_ACTIONS",
    "MUTATING_ACTIONS", "POSITION_MIN", "POSITION_MAX", "SCALE_MIN",
    "SCALE_MAX", "NOOP", "OBSERVE", "ADD_OWN_STICKER", "MOVE_STICKER",
    "ANIMATE_OWN_STICKER", "RESIZE_OWN_STICKER", "SET_STICKER_FACING",
    "REMOVE_OWN_STICKER",
    "REMOVE_AGENT_STICKER", "CREATE_AGENT",
]
