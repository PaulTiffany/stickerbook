"""Non-authoritative conversational/creator agent seam for StickerBook.

The browser can talk to an agent runtime through the bridge, but the runtime
does not receive the authority kernel object. It receives only:
  * the fixed browser principal id,
  * a JSON scene view,
  * validated user text / creator intent.

This seam returns language or draft metadata only. It is not an alternate
write path into the StickerBook authority kernel.

A future Omega-backed runtime can implement the same small interface. Jev and
kernel-governed actions remain separate from conversation.
"""

from __future__ import annotations


class DisabledAgentRuntime:
    """Default runtime: explicit, inspectable, and completely inert."""

    def capabilities(self) -> dict:
        return {
            "creator_agent": False,
            "conversational_agent": False,
        }

    def converse(self, *, text: str, principal: str, scene: dict) -> dict:
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
