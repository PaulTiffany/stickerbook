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

Live Omega is attached through a loopback-only HTTP adapter. The adapter carries
no provider credential and cannot be pointed at a non-loopback host.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

_MAX_RESPONSE_BYTES = 256 * 1024


class AgentRuntimeError(RuntimeError):
    """Safe host-owned diagnostic; never includes provider response text."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class DisabledAgentRuntime:
    """Default runtime: explicit, inspectable, and completely inert."""

    def capabilities(self) -> dict:
        return {
            "creator_agent": False,
            "conversational_agent": False,
        }

    def inference_options(self) -> list:
        return []

    def converse(
            self, *, text: str, principal: str, scene: dict,
            reference: dict | None = None,
            inference: dict | None = None) -> dict:
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


def _loopback_base(raw: str) -> str:
    """Return a canonical loopback HTTP base URL or raise ValueError."""
    parsed = urlsplit(str(raw).strip())
    if parsed.scheme != "http":
        raise ValueError("OmegaLLM runtime must use loopback HTTP")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("OmegaLLM runtime must be loopback-only")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid OmegaLLM runtime URL")
    if parsed.path not in ("", "/"):
        raise ValueError("OmegaLLM runtime URL must not contain a path")
    if parsed.port is None:
        raise ValueError("OmegaLLM runtime URL must include an explicit port")
    host = "[::1]" if parsed.hostname == "::1" else parsed.hostname
    return "http://%s:%d" % (host, parsed.port)


class LoopbackAgentRuntime:
    """Narrow host adapter for a live OmegaLLM StickerBook channel."""

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
            code = {409: "omegallm-busy", 503: "omegallm-not-ready",
                    504: "omegallm-timeout"}.get(exc.code, "omegallm-http-error")
            raise AgentRuntimeError(code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            code = ("omegallm-timeout" if isinstance(reason, TimeoutError)
                    else "omegallm-unavailable")
            raise AgentRuntimeError(code) from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise AgentRuntimeError("agent-response-too-large")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise AgentRuntimeError("invalid-agent-response") from exc
        if not isinstance(decoded, dict):
            raise AgentRuntimeError("invalid-agent-response")
        return decoded

    def capabilities(self) -> dict:
        try:
            health = self._json("/health")
        except Exception:
            return {"creator_agent": False, "conversational_agent": False}
        ready = bool(health.get("ok")) and health.get("role") == "omegallm"
        return {
            "creator_agent": False,
            "conversational_agent": ready,
        }

    def inference_options(self) -> list:
        try:
            health = self._json("/health")
        except Exception:
            return []
        raw = health.get("inference_options")
        if not isinstance(raw, list):
            return []
        clean = []
        allowed = {
            "id", "label", "description", "default_model",
            "model_locked", "sponsored", "available",
        }
        for item in raw:
            if not isinstance(item, dict) or set(item) != allowed:
                continue
            if not isinstance(item.get("id"), str):
                continue
            clean.append({key: item[key] for key in allowed})
        return clean

    def converse(
            self, *, text: str, principal: str, scene: dict,
            reference: dict | None = None,
            inference: dict | None = None) -> dict:
        payload = {
            "text": text,
            "principal": principal,
            "scene": scene,
        }
        if reference is not None:
            payload["reference"] = reference
        if inference is not None:
            payload["inference"] = inference
        return self._json("/converse", payload)

    def creator_draft(
            self, *,
            kind: str,
            prompt: str,
            animation_intent: str | None,
            asset_schema_version: int | None,
            principal: str,
            scene: dict) -> dict:
        return {"ok": False, "error": "creator-agent-unavailable"}


def agent_runtime_from_env():
    """Opt into live OmegaLLM only when an explicit loopback URL is supplied."""
    raw = os.environ.get("STICKERBOOK_OMEGA_LLM_URL", "").strip()
    if not raw:
        return DisabledAgentRuntime()
    try:
        timeout = float(os.environ.get("STICKERBOOK_OMEGA_TIMEOUT", "40"))
        return LoopbackAgentRuntime(raw, timeout=timeout)
    except (TypeError, ValueError):
        return DisabledAgentRuntime()
