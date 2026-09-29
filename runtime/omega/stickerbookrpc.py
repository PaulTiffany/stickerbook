"""Loopback RPC communication channel for StickerBook's Omega roles.

This module is loaded *inside* an OpenShell sandbox as an Omega CommChannel.
OpenShell forwards the sandbox port to host loopback. The browser never talks
to this service directly; the host bridge does.

One request at a time is intentional. Omega's loop is sequential, and allowing
concurrent callers would create ambiguous conversation/decision ownership.

The channel does not authorize StickerBook actions. It only moves bounded JSON
into and out of an Omega loop. The host kernel remains the authority boundary.
"""

from __future__ import annotations

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import channels
from config import config_get_by_key
from src.logger import get_logger

logger = get_logger(__name__)

_MAX_BODY = 256 * 1024
_lock = threading.RLock()
_gate = threading.Lock()
_current = None
_staged = None
_serial = 0
_provider_ready = False
_role = ""
_server = None
_thread = None


class _Pending:
    def __init__(self, request_id: int, payload: dict):
        self.request_id = request_id
        self.payload = payload
        self.delivered = False
        self.response = None
        self.event = threading.Event()


def _clean_role(value) -> str:
    role = str(value or "").strip().lower()
    if role not in ("omegallm", "omegajev"):
        raise RuntimeError("stickerbookRpcRole must be omegallm or omegajev")
    return role


def current_request(expected_role: str | None = None):
    """Return a defensive copy of the active host request, if any."""
    with _lock:
        if expected_role is not None and _role != expected_role:
            return None
        if _current is None or not _current.delivered:
            return None
        return copy.deepcopy(_current.payload)


def set_provider_ready(role: str) -> None:
    global _provider_ready
    clean = _clean_role(role)
    if clean != _role:
        raise RuntimeError("provider role does not match channel role")
    with _lock:
        _provider_ready = True


def stage_result(result: dict) -> bool:
    """Stage one JSON result for the fixed zero-argument sb-return skill."""
    global _staged
    if not isinstance(result, dict):
        return False
    raw = json.dumps(result, separators=(",", ":"))
    if len(raw.encode("utf-8")) > _MAX_BODY:
        return False
    with _lock:
        if _current is None or not _current.delivered:
            _staged = None
            return False
        _staged = (_current.request_id, copy.deepcopy(result))
        return True


def complete_staged() -> str:
    """Body of sb-return. Completing transport is not world authorization."""
    global _staged
    with _lock:
        if _current is None:
            _staged = None
            return "SB-RPC-NO-REQUEST"
        if _staged is None or _staged[0] != _current.request_id:
            _staged = None
            return "SB-RPC-NOTHING-STAGED"
        _current.response = _staged[1]
        _staged = None
        _current.event.set()
        return "SB-RPC-RETURNED"


def _validate_payload(role: str, payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return "body-must-be-object"

    if role == "omegallm":
        allowed = {"text", "principal", "scene", "reference"}
        if set(payload) - allowed:
            return "unknown-field"
        if not isinstance(payload.get("text"), str):
            return "invalid-text"
        if not payload["text"].strip() or len(payload["text"]) > 2000:
            return "invalid-text"
        if not isinstance(payload.get("principal"), str):
            return "invalid-principal"
        if not isinstance(payload.get("scene"), dict):
            return "invalid-scene"
        if "reference" in payload and not isinstance(payload["reference"], dict):
            return "invalid-reference"
        return None

    allowed = {"goal", "scene", "actions", "turn", "max_turns"}
    if set(payload) != allowed:
        return "invalid-fields"
    if not isinstance(payload["goal"], dict) or not isinstance(payload["scene"], dict):
        return "invalid-view"
    actions = payload["actions"]
    if not isinstance(actions, dict) or not actions or len(actions) > 128:
        return "invalid-actions"
    for key, description in actions.items():
        if not isinstance(key, str) or not key or len(key) > 200:
            return "invalid-actions"
        if not isinstance(description, str) or len(description) > 1000:
            return "invalid-actions"
    if not isinstance(payload["turn"], int) or isinstance(payload["turn"], bool):
        return "invalid-turn"
    if not isinstance(payload["max_turns"], int) or isinstance(
            payload["max_turns"], bool):
        return "invalid-turn"
    if not 1 <= payload["turn"] <= payload["max_turns"] <= 6:
        return "invalid-turn"
    return None


class _Handler(BaseHTTPRequestHandler):
    server_version = "StickerBookOmegaRPC/0.1"

    def log_message(self, fmt, *args):
        logger.info("[stickerbookrpc] " + fmt, *args)

    def _send(self, code: int, payload: dict):
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path != "/health":
            return self._send(404, {"ok": False, "error": "not-found"})
        with _lock:
            ready = bool(_provider_ready)
        return self._send(200, {"ok": ready, "role": _role})

    def do_POST(self):
        expected = "/converse" if _role == "omegallm" else "/choose"
        if self.path != expected:
            return self._send(404, {"ok": False, "error": "not-found"})

        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            return self._send(400, {"ok": False, "error": "bad-length"})
        if length <= 0 or length > _MAX_BODY:
            return self._send(413, {"ok": False, "error": "bad-size"})
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self._send(400, {"ok": False, "error": "bad-json"})

        error = _validate_payload(_role, payload)
        if error:
            return self._send(400, {"ok": False, "error": error})

        if not _provider_ready:
            return self._send(
                503, {"ok": False, "error": "omega-provider-not-ready"})

        if not _gate.acquire(blocking=False):
            return self._send(409, {"ok": False, "error": "omega-busy"})

        global _current, _serial, _staged
        pending = None
        try:
            with _lock:
                _serial += 1
                _staged = None
                _current = _Pending(_serial, copy.deepcopy(payload))
                pending = _current

            timeout = float(config_get_by_key("stickerbookRpcTimeout", 45))
            if not pending.event.wait(timeout=max(1.0, min(timeout, 120.0))):
                return self._send(
                    504, {"ok": False, "error": "omega-response-timeout"})

            with _lock:
                response = copy.deepcopy(pending.response)
            if not isinstance(response, dict):
                return self._send(
                    502, {"ok": False, "error": "invalid-omega-response"})
            return self._send(200, response)
        finally:
            with _lock:
                if pending is not None and _current is not None and _current is pending:
                    _current = None
                    _staged = None
            _gate.release()


class StickerBookRPCChannel(channels.CommChannel):

    def start(self) -> None:
        global _role, _server, _thread, _provider_ready
        _role = _clean_role(config_get_by_key("stickerbookRpcRole", ""))
        port = int(config_get_by_key(
            "stickerbookRpcPort", 8761 if _role == "omegallm" else 8762))
        _provider_ready = False
        _server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        _thread = threading.Thread(
            target=_server.serve_forever,
            name="stickerbook-omega-rpc",
            daemon=True,
        )
        _thread.start()
        logger.info(
            "[stickerbookrpc] %s channel listening on sandbox port %s",
            _role, port)

    def stop(self) -> None:
        global _server, _thread, _provider_ready
        _provider_ready = False
        if _server is not None:
            _server.shutdown()
            _server.server_close()
        if _thread is not None:
            _thread.join(timeout=5)
        _server = None
        _thread = None

    def receive(self) -> str:
        with _lock:
            if _current is None or _current.delivered:
                return ""
            _current.delivered = True
            return "STICKERBOOK-RPC %s %d" % (_role, _current.request_id)

    def send(self, message: str) -> None:
        # Omega sends its version at startup and may emit other channel text.
        # RPC completion occurs only through sb-return, never by parsing text.
        logger.info("[stickerbookrpc] Omega channel output: %s", str(message)[:500])


def loadOmegaPlugin():
    channels.registerCommChannel("stickerbookrpc", StickerBookRPCChannel())
