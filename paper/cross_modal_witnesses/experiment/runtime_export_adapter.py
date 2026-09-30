"""Adapter template for exporting real StickerBook events into schema v0.1.

This file does not connect to a running StickerBook instance by itself. It is a
small integration seam intended to be copied/wired into the runtime or bridge.
It binds the public Receipt.to_dict() field names to the experiment schema.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class RuntimeTraceBuilder:
    trace_id: str
    invariant: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def add_receipt_event(
        self,
        *,
        t: float,
        event: str,
        page: str | None,
        principal: str,
        revision_before: int | None,
        route: str,
        legal_keys: list[str],
        selected_key: str | None,
        receipt: dict[str, Any] | None,
        state_delta: list[dict[str, Any]],
        selected_key_source: str | None = "host-table",
        authority_expired: bool = False,
        notes: str = "",
    ) -> None:
        self.events.append({
            "t": float(t), "event": event, "page": page, "principal": principal,
            "revision_before": revision_before, "route": route,
            "legal_keys": list(legal_keys), "selected_key": selected_key,
            "selected_key_source": selected_key_source,
            "authority_expired": bool(authority_expired),
            "receipt": receipt, "state_delta": list(state_delta), "notes": notes,
        })

    def build_unlabeled(self) -> dict[str, Any]:
        """Return a runtime trace before experiment ground-truth labeling.

        A separate fixture/labeling step should attach the target invariant's
        ground truth; do not infer that label from media renderers.
        """
        return {
            "schema_version": "0.1",
            "trace_id": self.trace_id,
            "fixture_kind": "runtime-export",
            "invariant": self.invariant,
            "condition": None,
            "ground_truth": None,
            "events": self.events,
        }

# StickerBook Receipt.to_dict() currently exposes:
# commandId, actor, requestedBy, translatedBy, selectedBy, action, object,
# basedOnRevision, accepted, reason, resultRevision, replayed.
