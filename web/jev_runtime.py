"""Narrow runtime seam for the OmegaJev decision loop.

StickerBook does not import Omega or a model provider here. The host composes a
bounded scene plus a finite host-owned action table and asks a runtime adapter to
choose one key.

The live adapter is deliberately loopback-only. It never receives the authority
kernel object and never returns command arguments. It returns only a key already
present in the supplied table; JevController validates that key again before the
kernel sees it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

_MAX_RESPONSE_BYTES = 128 * 1024


class JevRuntimeError(RuntimeError):
    """Fixed host-owned reason, never provider body or exception text."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class DisabledJevRuntime:
    """Default: no Jev loop is connected and no network access is attempted."""

    def available(self) -> bool:
        return False

    def choose(
            self, *, goal: dict, scene: dict, actions: dict,
            turn: int, max_turns: int) -> dict:
        return {"ok": False, "error": "jev-runtime-unavailable"}


def _loopback_base(raw: str) -> str:
    parsed = urlsplit(str(raw).strip())
    if parsed.scheme != "http":
        raise ValueError("OmegaJev runtime must use loopback HTTP")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("OmegaJev runtime must be loopback-only")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid OmegaJev runtime URL")
    if parsed.path not in ("", "/"):
        raise ValueError("OmegaJev runtime URL must not contain a path")
    if parsed.port is None:
        raise ValueError("OmegaJev runtime URL must include an explicit port")
    host = "[::1]" if parsed.hostname == "::1" else parsed.hostname
    return "http://%s:%d" % (host, parsed.port)


class LoopbackJevRuntime:
    """Narrow host adapter for a live OmegaJev StickerBook channel."""

    def __init__(self, base_url: str, timeout: float = 40.0):
        self.base_url = _loopback_base(base_url)
        self.timeout = float(timeout)

    def _json(self, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(
            payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            code = {409:'jev-busy', 503:'jev-not-ready', 504:'jev-timeout',
                    400:'jev-request-refused', 413:'jev-request-too-large'}.get(exc.code,'jev-http-error')
            raise JevRuntimeError(code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc,'reason',exc)
            raise JevRuntimeError('jev-timeout' if isinstance(reason,TimeoutError) else 'jev-unavailable') from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise RuntimeError("OmegaJev response too large")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("OmegaJev returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("OmegaJev returned a non-object")
        return decoded

    def available(self) -> bool:
        try:
            health = self._json("/health")
        except Exception:
            return False
        return bool(health.get("ok")) and health.get("role") == "omegajev"

    def choose(
            self, *, goal: dict, scene: dict, actions: dict,
            turn: int, max_turns: int) -> dict:
        return self._json("/choose", {
            "goal": goal,
            "scene": scene,
            "actions": actions,
            "turn": int(turn),
            "max_turns": int(max_turns),
        })


def jev_runtime_from_env():
    """Opt into live OmegaJev only when an explicit loopback URL is supplied."""
    raw = os.environ.get("STICKERBOOK_OMEGA_JEV_URL", "").strip()
    if not raw:
        return DisabledJevRuntime()
    try:
        timeout = float(os.environ.get("STICKERBOOK_OMEGA_TIMEOUT", "40"))
        return LoopbackJevRuntime(raw, timeout=timeout)
    except (TypeError, ValueError):
        return DisabledJevRuntime()
