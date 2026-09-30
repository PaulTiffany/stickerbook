"""Loopback RPC communication channel for StickerBook's Omega roles.

This module runs inside an Omega container as an Omega CommChannel.
The runtime publishes its port to host loopback. The browser never talks
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
from stickerbookrpc_state import state

logger = get_logger(__name__)

_MAX_BODY = 256 * 1024


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
    with state.lock:
        if expected_role is not None and state.role != expected_role:
            return None
        if state.current is None or not state.current.delivered:
            return None
        return copy.deepcopy(state.current.payload)


def recall_memory(role, page, query, asset=None):
    if role != state.role:
        raise ValueError('memory-role-mismatch')
    return state.memory.recall(page, query, asset) if state.memory else []


def remember_conversation(page, text, reply):
    if state.role != 'omegallm':
        raise ValueError('memory-role-mismatch')
    if state.memory:
        import uuid
        return state.memory.remember([{'kind': 'conversation', 'id': 'conversation-' + uuid.uuid4().hex,
                                      'page': page, 'text': text, 'reply': reply}])
    return {'ok': False, 'error': 'omega-memory-disabled'}


def set_provider_ready(role: str, metadata: dict | None = None) -> None:
    clean = _clean_role(role)
    if clean != state.role:
        raise RuntimeError("provider role does not match channel role")
    if metadata is not None and not isinstance(metadata, dict):
        raise RuntimeError("provider metadata must be an object")
    with state.lock:
        state.provider_metadata = copy.deepcopy(metadata or {})
        state.provider_ready = True


def stage_result(result: dict) -> bool:
    """Stage one JSON result for the fixed zero-argument sb-return skill."""
    if not isinstance(result, dict):
        return False
    raw = json.dumps(result, separators=(",", ":"))
    if len(raw.encode("utf-8")) > _MAX_BODY:
        return False
    with state.lock:
        if state.current is None or not state.current.delivered:
            state.staged = None
            return False
        state.staged = (state.current.request_id, copy.deepcopy(result))
        return True


def complete_staged() -> str:
    """Body of sb-return. Completing transport is not world authorization."""
    with state.lock:
        if state.current is None:
            state.staged = None
            return "SB-RPC-NO-REQUEST"
        if state.staged is None or state.staged[0] != state.current.request_id:
            state.staged = None
            return "SB-RPC-NOTHING-STAGED"
        state.current.response = state.staged[1]
        state.staged = None
        state.current.event.set()
        return "SB-RPC-RETURNED"


def _validate_payload(role: str, payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return "body-must-be-object"

    if role == "omegallm":
        allowed = {"text", "principal", "scene", "reference", "inference"}
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
        inference = payload.get("inference")
        if not isinstance(inference, dict) or set(inference) != {"provider", "model"}:
            return "invalid-inference"
        if not isinstance(inference["provider"], str) or not inference["provider"]:
            return "invalid-inference"
        if not isinstance(inference["model"], str) or not inference["model"]:
            return "invalid-inference"
        if len(inference["provider"]) > 40 or len(inference["model"]) > 120:
            return "invalid-inference"
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
    # Existing host pattern and trajectory agent budgets are bounded at 12.
    if not 1 <= payload["turn"] <= payload["max_turns"] <= 12:
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
        if self.path == '/memory' and state.memory is not None:
            return self._send(200, state.memory.describe())
        if self.path != "/health":
            return self._send(404, {"ok": False, "error": "not-found"})
        with state.lock:
            ready = bool(state.provider_ready)
            metadata = copy.deepcopy(state.provider_metadata)
        payload = {"ok": ready, "role": state.role}
        if state.role == "omegallm":
            payload.update(metadata)
            try:
                from sticker_creator import available
                payload['creator_agent'] = available()
            except ImportError:
                payload['creator_agent'] = False
        return self._send(200, payload)

    def do_POST(self):
        expected = "/converse" if state.role == "omegallm" else "/choose"
        memory_request = self.path == '/memory/events'
        creator_request = self.path == '/create' and state.role == 'omegallm'
        if self.path != expected and not memory_request and not creator_request:
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

        if creator_request:
            try:
                from sticker_creator import create
                return self._send(200, create(payload))
            except ImportError:
                return self._send(503, {'ok': False, 'error': 'creator-agent-unavailable'})
        if memory_request:
            if state.memory is None:
                return self._send(503, {'ok': False, 'error': 'omega-memory-unavailable'})
            if not isinstance(payload, dict) or set(payload) != {'events'}:
                return self._send(400, {'ok': False, 'error': 'invalid-memory-fields'})
            try:
                return self._send(200, state.memory.remember(payload['events']))
            except ValueError:
                return self._send(400, {'ok': False, 'error': 'invalid-memory-event'})
            except Exception:
                return self._send(503, {'ok': False, 'error': 'omega-memory-unavailable'})
        error = _validate_payload(state.role, payload)
        if error:
            return self._send(400, {"ok": False, "error": error})

        if not state.provider_ready:
            return self._send(
                503, {"ok": False, "error": "omega-provider-not-ready"})

        if not state.gate.acquire(blocking=False):
            return self._send(409, {"ok": False, "error": "omega-busy"})

        pending = None
        try:
            with state.lock:
                state.serial += 1
                state.staged = None
                state.current = _Pending(state.serial, copy.deepcopy(payload))
                pending = state.current

            timeout = float(config_get_by_key("stickerbookRpcTimeout", 45))
            if not pending.event.wait(timeout=max(1.0, min(timeout, 120.0))):
                return self._send(
                    504, {"ok": False, "error": "omega-response-timeout"})

            with state.lock:
                response = copy.deepcopy(pending.response)
            if not isinstance(response, dict):
                return self._send(
                    502, {"ok": False, "error": "invalid-omega-response"})
            return self._send(200, response)
        finally:
            with state.lock:
                if pending is not None and state.current is not None and state.current is pending:
                    state.current = None
                    state.staged = None
            state.gate.release()


class StickerBookRPCChannel(channels.CommChannel):

    def start(self) -> None:
        state.role = _clean_role(config_get_by_key("stickerbookRpcRole", ""))
        port = int(config_get_by_key(
            "stickerbookRpcPort", 8761 if state.role == "omegallm" else 8762))
        state.provider_ready = False
        state.provider_metadata = {}
        if config_get_by_key('stickerbookMemoryEnabled', False):
            from omega_memory import NativeOmegaMemory
            state.memory = NativeOmegaMemory(state.role)
        else:
            state.memory = None
        # Docker needs the container interface; publication remains host-loopback.
        # The hardened runtime retains the default internal loopback binding.
        bind = str(config_get_by_key("stickerbookRpcBind", "127.0.0.1"))
        if bind not in ("127.0.0.1", "0.0.0.0"):
            raise RuntimeError("invalid StickerBook RPC bind address")
        state.server = ThreadingHTTPServer((bind, port), _Handler)
        state.thread = threading.Thread(
            target=state.server.serve_forever,
            name="stickerbook-omega-rpc",
            daemon=True,
        )
        state.thread.start()
        logger.info(
            "[stickerbookrpc] %s channel listening on sandbox port %s",
            state.role, port)

    def stop(self) -> None:
        state.provider_ready = False
        state.provider_metadata = {}
        if state.server is not None:
            state.server.shutdown()
            state.server.server_close()
        if state.thread is not None:
            state.thread.join(timeout=5)
        state.server = None
        state.thread = None

    def receive(self) -> str:
        with state.lock:
            if state.current is None or state.current.delivered:
                return ""
            state.current.delivered = True
            return "STICKERBOOK-RPC %s %d" % (state.role, state.current.request_id)

    def send(self, message: str) -> None:
        # Omega sends its version at startup and may emit other channel text.
        # RPC completion occurs only through sb-return, never by parsing text.
        logger.info("[stickerbookrpc] Omega channel output: %s", str(message)[:500])


def loadOmegaPlugin():
    channels.registerCommChannel("stickerbookrpc", StickerBookRPCChannel())
