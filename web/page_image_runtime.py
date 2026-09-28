"""Local client for StickerBook's separate page-image gateway.

The browser bridge never receives an OpenRouter credential. When the operator
explicitly configures a gateway URL, the bridge may hand validated image bytes
to that loopback-only service and receive non-authoritative page draft metadata.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class DisabledPageImageRuntime:
    """Default: page uploads remain local previews and no provider is called."""

    def available(self) -> bool:
        return False

    def reframe_page(
            self, *,
            image_bytes: bytes,
            content_type: str,
            filename: str) -> dict:
        return {"ok": False, "error": "page-image-creator-unavailable"}


class GatewayPageImageRuntime:
    """Client for a separately started, loopback-only image gateway."""

    def __init__(self, base_url: str, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        return True

    def reframe_page(
            self, *,
            image_bytes: bytes,
            content_type: str,
            filename: str) -> dict:
        request = urllib.request.Request(
            self.base_url + "/v1/page/reframe",
            data=image_bytes,
            method="POST",
            headers={
                "Content-Type": content_type,
                "X-StickerBook-Filename": urllib.parse.quote(
                    filename, safe=""),
            },
        )

        try:
            with urllib.request.urlopen(
                    request, timeout=self.timeout) as response:
                raw = response.read(131073)
                if len(raw) > 131072:
                    return {"ok": False, "error": "image-gateway-response-too-large"}
                payload = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read(131073).decode("utf-8"))
            except Exception:
                payload = {"ok": False, "error": "image-gateway-error"}
        except (OSError, ValueError, json.JSONDecodeError):
            return {"ok": False, "error": "image-gateway-unavailable"}

        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid-image-gateway-response"}
        return payload


def page_image_runtime_from_env():
    """Enable the gateway only when the operator explicitly configures it."""
    base_url = os.environ.get("STICKERBOOK_IMAGE_GATEWAY_URL", "").strip()
    if not base_url:
        return DisabledPageImageRuntime()
    return GatewayPageImageRuntime(base_url)
