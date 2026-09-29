"""Narrow runtime seam for the OmegaJev decision loop.

StickerBook does not import Omega or a model provider here.  The host composes a
bounded scene plus a finite host-owned action table and asks a runtime adapter to
choose one key.  A future OmegaJev/OpenShell adapter implements this interface.

The runtime never receives the authority kernel object and never returns command
arguments.  It returns only a key already present in the supplied table.
"""

from __future__ import annotations


class DisabledJevRuntime:
    """Default: no Jev loop is connected and no network access is attempted."""

    def available(self) -> bool:
        return False

    def choose(
            self, *, goal: dict, scene: dict, actions: dict,
            turn: int, max_turns: int) -> dict:
        return {"ok": False, "error": "jev-runtime-unavailable"}
