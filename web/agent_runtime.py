"""Non-authoritative conversational/creator agent seam for StickerBook.

The browser can talk to an agent runtime through the bridge, but the runtime
does not receive the authority kernel object. It receives only:
  * the fixed browser principal id,
  * a JSON scene view,
  * validated user text / creator intent,
  * an optional transient child deictic reference for the current turn.

The conversational seam is the OmegaLLM role. It returns language and may
optionally attach one bounded semantic goal under a `goal` field. A goal is
not a command and carries no authority: the host validates it, OmegaJev chooses
from a finite host-owned action surface, and the kernel decides every mutation.

A future Omega-backed runtime can implement the same small interface. OmegaLLM
and OmegaJev remain separate agent loops even when they cooperate on one child
request.
"""

from __future__ import annotations


class DisabledAgentRuntime:
    """Default runtime: explicit, inspectable, and completely inert."""

    def capabilities(self) -> dict:
        return {
            "creator_agent": False,
            "conversational_agent": False,
        }

    def converse(
            self, *, text: str, principal: str, scene: dict,
            reference: dict | None = None) -> dict:
        return {
            "ok": False,
            "error": "conversational-agent-unavailable",
        }

    def creator_draft(
            self, *,
            kind: str,
            prompt: str,
            animation_intent: str | None,
            asset_schema_version: int | None,
            principal: str,
            scene: dict) -> dict:
        return {
            "ok": False,
            "error": "creator-agent-unavailable",
        }
