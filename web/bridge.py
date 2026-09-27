"""
Localhost bridge between the browser and the StickerBook authority kernel.

    pointer action
        -> browser POSTs a PROPOSAL (sticker id + where the pointer was)
        -> bridge validates the shape and fixes the acting principal
        -> bridge builds the Command; the kernel validates and decides
        -> kernel returns a Receipt
        -> bridge returns receipt + authoritative state
        -> browser re-renders from that state

The browser is a proposer and a renderer. It is not the authority boundary.

What the browser is NOT trusted with, enforced here:

  * its own identity -- the acting principal is fixed by the bridge; an
    `actor` field in the request body is ignored entirely;
  * the position it claims -- the kernel checks the coordinate is on the
    page before anything moves;
  * choosing an action -- this endpoint performs exactly one kind of
    command, a move of an existing sticker;
  * being believed about success -- every response carries authoritative
    state, and the renderer draws that rather than its own proposal.

There is one kernel. This process holds it; nothing is reimplemented here.
No credential, no model, no outbound network: the server binds loopback only.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import book  # noqa: E402
import farm  # noqa: E402
from agent_runtime import DisabledAgentRuntime  # noqa: E402
from stickerbook_core import (  # noqa: E402
    ADD_OWN_STICKER, ANIMATE_OWN_STICKER, Command, MOVE_STICKER,
    REMOVE_OWN_STICKER,
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# The only principal this bridge will ever act as. Not client-selectable.
BROWSER_PRINCIPAL = farm.HUMAN_ID

CONTENT_TYPES = {".html": "text/html; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8",
                 ".json": "application/json; charset=utf-8",
                 ".svg": "image/svg+xml",
                 ".png": "image/png",
                 ".jpg": "image/jpeg",
                 ".jpeg": "image/jpeg",
                 ".webp": "image/webp"}

MAX_BODY_BYTES = 8192


class Bridge:
    """Kernel-facing logic, kept free of HTTP so it can be tested directly."""

    def __init__(self, kernel=None, agent_runtime=None):
        self.kernel = kernel or farm.build_world()
        self.agent_runtime = agent_runtime or DisabledAgentRuntime()

    # -- reads -------------------------------------------------------------

    def state(self) -> dict:
        """Authoritative state, as the browser's principal may observe it."""
        view = self.kernel.view(BROWSER_PRINCIPAL)
        chrome = farm.page_chrome()
        stickers = []
        for s in view["stickers"]:
            stickers.append({
                "id": s["id"],
                "definition": s["asset"],
                "x": s["x"],
                "y": s["y"],
                "owner": s["owner"],
                "mine": s["mine"],
                "animation": s["animation"],
                "revision": s["revision"],
            })
        return {
            "revision": view["revision"],
            "principal": BROWSER_PRINCIPAL,
            "page": {"id": book.DEFAULT_PAGE,
                     "name": book.PAGES[book.DEFAULT_PAGE]["name"]},
            "picture": chrome["picture"],
            # StickerDefinitions: reusable designs the tray offers. One
            # design, many instances.
            "definitions": [
                {"id": name, "animations": list(d.animations)}
                for name, d in sorted(farm.ASSETS.items())
            ],
            "capabilities": self._agent_capabilities(),
            "stickers": stickers,
        }

    def receipts(self, limit: int = 12) -> list:
        return [r.to_dict() for r in self.kernel.receipts[-limit:]]

    def _agent_capabilities(self) -> dict:
        """Expose only small boolean feature flags to the browser."""
        try:
            raw = self.agent_runtime.capabilities()
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        return {
            "creator_agent": bool(raw.get("creator_agent", False)),
            "conversational_agent": bool(
                raw.get("conversational_agent", False)),
        }

    def converse(self, body: dict) -> dict:
        """Return language only. This is not a kernel command path."""
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")

        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._bad_request("missing conversation text")
        text = text.strip()
        if len(text) > 2000:
            return self._bad_request("conversation text too long")

        if not self._agent_capabilities()["conversational_agent"]:
            return {"ok": False,
                    "error": "conversational-agent-unavailable",
                    "state": self.state()}

        try:
            result = self.agent_runtime.converse(
                text=text,
                principal=BROWSER_PRINCIPAL,
                scene=self.state())
        except Exception:
            return {"ok": False, "error": "agent-runtime-error",
                    "state": self.state()}

        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}

        if not result.get("ok"):
            error = result.get("error")
            return {"ok": False,
                    "error": error if isinstance(error, str)
                    else "agent-runtime-error",
                    "state": self.state()}

        reply = result.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}

        return {"ok": True, "reply": reply.strip(), "state": self.state()}

    def creator_draft(self, body: dict) -> dict:
        """Return a non-authoritative page/sticker draft description."""
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")

        kind = body.get("kind")
        prompt = body.get("prompt")
        animation_intent = body.get("animation_intent")
        schema = body.get("asset_schema_version")

        if kind not in ("page", "sticker"):
            return self._bad_request("unknown creator kind")
        if not isinstance(prompt, str) or not prompt.strip():
            return self._bad_request("missing creator prompt")
        prompt = prompt.strip()
        if len(prompt) > 500:
            return self._bad_request("creator prompt too long")

        if kind == "sticker":
            if animation_intent not in ("still", "move", "animate"):
                return self._bad_request("invalid animation intent")
            if schema != 2:
                return self._bad_request("unsupported asset schema")
        else:
            animation_intent = None
            schema = None

        if not self._agent_capabilities()["creator_agent"]:
            return {"ok": False, "error": "creator-agent-unavailable",
                    "state": self.state()}

        try:
            result = self.agent_runtime.creator_draft(
                kind=kind,
                prompt=prompt,
                animation_intent=animation_intent,
                asset_schema_version=schema,
                principal=BROWSER_PRINCIPAL,
                scene=self.state())
        except Exception:
            return {"ok": False, "error": "agent-runtime-error",
                    "state": self.state()}

        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}

        try:
            encoded = json.dumps(result)
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}
        if len(encoded.encode("utf-8")) > 65536:
            return {"ok": False, "error": "agent-response-too-large",
                    "state": self.state()}

        if not result.get("ok") or not isinstance(result.get("draft"), dict):
            error = result.get("error")
            return {"ok": False,
                    "error": error if isinstance(error, str)
                    else "invalid-agent-response",
                    "state": self.state()}

        return {"ok": True, "draft": result["draft"], "state": self.state()}

    # -- the one write path ------------------------------------------------

    def propose_move(self, body: dict) -> dict:
        """Validate the request shape, then let the kernel decide.

        Shape failures are refused here without reaching the kernel; they are
        malformed HTTP, not proposals. Everything that *is* a well-formed
        proposal goes to the kernel, including ones certain to be refused, so
        the refusal is recorded as a receipt.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")

        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        point = body.get("point")
        based_on = body.get("based_on_revision")

        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if not isinstance(point, dict):
            return self._bad_request("missing pointer position")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")

        # NOTE: actor is NOT taken from the request. Whatever the browser
        # claims about who it is has no effect.
        receipt = self.kernel.propose(Command(
            action=MOVE_STICKER,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            object_id=sticker_id,
            params=(("x", point.get("x")), ("y", point.get("y"))),
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(),
                "state": self.state()}

    def place(self, body: dict) -> dict:
        """Put a new sticker on the page, from the tray."""
        fields = self._common(body, ("asset",))
        if isinstance(fields, dict):
            return fields
        command_id, point, based_on, (asset,) = fields
        receipt = self.kernel.propose(Command(
            action=ADD_OWN_STICKER,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            params=(("asset", asset), ("x", point.get("x")),
                    ("y", point.get("y"))),
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def remove(self, body: dict) -> dict:
        """Take a sticker off the page, back to the tray."""
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        based_on = body.get("based_on_revision")
        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")
        receipt = self.kernel.propose(Command(
            action=REMOVE_OWN_STICKER,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            object_id=sticker_id,
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def animate(self, body: dict) -> dict:
        """Bring a sticker to life, or let it settle.

        The child gesture is a double-tap; which animation that means is
        decided here from what the definition declares, never sent by the
        browser. Later an agent may choose instead, without the gesture
        changing.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        based_on = body.get("based_on_revision")
        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")

        sticker = self.kernel.sticker(sticker_id)
        if sticker is None:
            return self._bad_request("no such sticker")
        definition = self.kernel.assets.get(sticker.asset)
        alive = [a for a in (definition.animations if definition else ())
                 if a != "none"]
        # A toggle: bring it to life, or let it settle.
        wanted = "none" if sticker.animation != "none" else (
            alive[0] if alive else "none")

        receipt = self.kernel.propose(Command(
            action=ANIMATE_OWN_STICKER,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            object_id=sticker_id,
            params=(("animation", wanted),),
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def _common(self, body, extra=()):
        """Shape validation shared by the pointer-driven write paths.

        Shape is the bridge's business; VALUES are the kernel's. A coordinate
        that is off the page or not a number is a well-formed proposal with a
        bad value, so it goes to the kernel and the refusal is receipted.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        command_id = body.get("command_id")
        point = body.get("point")
        based_on = body.get("based_on_revision")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if not isinstance(point, dict):
            return self._bad_request("missing pointer position")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")
        values = []
        for name in extra:
            value = body.get(name)
            if not isinstance(value, str) or not value:
                return self._bad_request("missing " + name)
            values.append(value)
        return command_id, point, based_on, tuple(values)

    def _bad_request(self, reason: str) -> dict:
        """Malformed input never reaches the kernel and never mutates."""
        return {"ok": False, "error": reason, "state": self.state()}


def make_handler(bridge: Bridge, quiet: bool = False):

    class Handler(BaseHTTPRequestHandler):
        server_version = "StickerBookBridge/0.1"

        def address_string(self):
            # Skip the reverse DNS lookup BaseHTTPRequestHandler does by
            # default; on loopback it is pure latency.
            return self.client_address[0]

        def _send(self, code, payload, content_type="application/json"):
            data = payload if isinstance(payload, bytes) else \
                json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            # The page needs no third-party anything; forbid it outright.
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path == "/api/state":
                return self._send(200, bridge.state())
            if path == "/api/book":
                return self._send(200, book.listing())
            if path == "/api/receipts":
                return self._send(200, {"receipts": bridge.receipts()})
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            return self._send(404, {"error": "not found"})

        ROUTES = {"/api/propose-move": "propose_move",
                  "/api/place": "place",
                  "/api/remove": "remove",
                  "/api/animate": "animate",
                  "/api/agent/converse": "converse",
                  "/api/creator/draft": "creator_draft"}

        def do_POST(self):
            route = self.ROUTES.get(self.path.split("?")[0])
            if route is None:
                return self._send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, {"ok": False, "error": "bad length"})
            if length > MAX_BODY_BYTES:
                return self._send(413, {"ok": False, "error": "body too large"})
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else None
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"ok": False, "error": "body is not JSON",
                                        "state": bridge.state()})
            result = getattr(bridge, route)(body)
            return self._send(200 if result.get("ok") else 400, result)

        def _static(self, name):
            # Root browser code remains exact-name only. Visual assets may live
            # below static/assets/, but path resolution is contained there.
            if name in ("index.html", "app.js", "style.css"):
                path = os.path.join(STATIC_DIR, name)
            elif name.startswith("assets/"):
                asset_root = os.path.realpath(os.path.join(STATIC_DIR, "assets"))
                relative = name[len("assets/"):]
                path = os.path.realpath(os.path.join(asset_root, relative))
                try:
                    contained = os.path.commonpath((asset_root, path)) == asset_root
                except ValueError:
                    contained = False
                if not relative or not contained:
                    return self._send(404, {"error": "not found"})
            else:
                return self._send(404, {"error": "not found"})

            if not os.path.isfile(path):
                return self._send(404, {"error": "not found"})

            ext = os.path.splitext(path)[1].lower()
            if ext not in CONTENT_TYPES:
                return self._send(404, {"error": "not found"})

            with open(path, "rb") as handle:
                self._send(200, handle.read(), CONTENT_TYPES[ext])

        def address_string(self):
            # Skip the reverse DNS lookup BaseHTTPRequestHandler does
            # by default; on loopback it is pure latency.
            return self.client_address[0]

        def log_message(self, fmt, *args):
            if not quiet:
                sys.stderr.write("[bridge] %s\n" % (fmt % args))

    return Handler


def serve(host="127.0.0.1", port=8756, kernel=None, quiet=False,
          agent_runtime=None):
    bridge = Bridge(kernel, agent_runtime=agent_runtime)
    httpd = ThreadingHTTPServer((host, port), make_handler(bridge, quiet))
    return httpd, bridge


if __name__ == "__main__":
    # Loopback only. This is a local development surface, not a service.
    PORT = int(os.environ.get("STICKERBOOK_PORT", "8756"))
    try:
        httpd, _ = serve("127.0.0.1", PORT)
    except OSError as exc:
        # Fail LOUDLY. A silent bind failure leaves an OLDER process
        # serving: it hands out the current static files but the Python
        # it imported at startup is stale, so the page looks updated
        # while the kernel behind it is not. That has cost real
        # debugging time twice in one sitting.
        sys.stderr.write(
            "\nStickerBook: cannot listen on 127.0.0.1:%d -- %s\n"
            "Something already serves that port, probably an older bridge.\n"
            "Stop it first; do NOT assume this one is running.\n\n"
            % (PORT, exc))
        raise SystemExit(2)
    print("StickerBook farm on http://127.0.0.1:%d/  (Ctrl-C to stop)" % PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        httpd.server_close()
