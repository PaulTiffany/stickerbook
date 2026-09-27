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

import farm  # noqa: E402
from stickerbook_core import Command, MOVE_STICKER  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# The only principal this bridge will ever act as. Not client-selectable.
BROWSER_PRINCIPAL = farm.HUMAN_ID

CONTENT_TYPES = {".html": "text/html; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8"}

MAX_BODY_BYTES = 8192


class Bridge:
    """Kernel-facing logic, kept free of HTTP so it can be tested directly."""

    def __init__(self, kernel=None):
        self.kernel = kernel or farm.build_world()

    # -- reads -------------------------------------------------------------

    def state(self) -> dict:
        """Authoritative state, as the browser's principal may observe it."""
        view = self.kernel.view(BROWSER_PRINCIPAL)
        chrome = farm.page_chrome()
        stickers = []
        for s in view["stickers"]:
            stickers.append({
                "id": s["id"],
                "is": s["asset"],
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
            "backdrop": chrome["backdrop"],
            "stickers": stickers,
        }

    def receipts(self, limit: int = 12) -> list:
        return [r.to_dict() for r in self.kernel.receipts[-limit:]]

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
            if path == "/api/receipts":
                return self._send(200, {"receipts": bridge.receipts()})
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path.split("?")[0] != "/api/propose-move":
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
            result = bridge.propose_move(body)
            return self._send(200 if result.get("ok") else 400, result)

        def _static(self, name):
            # Serve only the files we ship, by exact name.
            safe = os.path.basename(name)
            path = os.path.join(STATIC_DIR, safe)
            if safe != name or not os.path.isfile(path):
                return self._send(404, {"error": "not found"})
            ext = os.path.splitext(safe)[1]
            if ext not in CONTENT_TYPES:
                return self._send(404, {"error": "not found"})
            with open(path, "rb") as handle:
                self._send(200, handle.read(), CONTENT_TYPES[ext])

        def log_message(self, fmt, *args):
            sys.stderr.write("[bridge] %s\n" % (fmt % args))

    return Handler


def serve(host="127.0.0.1", port=8756, kernel=None, quiet=False):
    bridge = Bridge(kernel)
    httpd = ThreadingHTTPServer((host, port), make_handler(bridge, quiet))
    return httpd, bridge


if __name__ == "__main__":
    # Loopback only. This is a local development surface, not a service.
    PORT = int(os.environ.get("STICKERBOOK_PORT", "8756"))
    httpd, _ = serve("127.0.0.1", PORT)
    print("StickerBook farm on http://127.0.0.1:%d/  (Ctrl-C to stop)" % PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        httpd.server_close()
