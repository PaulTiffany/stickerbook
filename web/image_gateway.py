"""Loopback-only OpenRouter image gateway for StickerBook page uploads.

This process is intentionally separate from the browser bridge and authority
kernel. It may hold OPENROUTER_API_KEY, but it has no StickerBook principal,
kernel object, command path, or agent authority.

Run it separately from the bridge:

    set OPENROUTER_API_KEY=...
    set STICKERBOOK_OPENROUTER_IMAGE_MODEL=<editing-capable image model>
    python image_gateway.py

Then start the browser bridge with:

    set STICKERBOOK_IMAGE_GATEWAY_URL=http://127.0.0.1:8757
    python bridge.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from page_assets import (
    SUPPORTED_IMAGE_TYPES,
    generation_plan,
    supported_upload,
    variant_filename,
)

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATED_PAGE_DIR = os.path.join(HERE, "generated_pages")
OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PROVIDER_RESPONSE_BYTES = 64 * 1024 * 1024

_OUTPUT_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}


def _media_type_from_bytes(raw: bytes, declared: str | None) -> str | None:
    if declared in _OUTPUT_EXTENSIONS:
        return declared
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.lstrip().startswith(b"<svg"):
        return "image/svg+xml"
    return None


def _jpeg_dimensions(raw: bytes) -> tuple[int, int] | None:
    if not raw.startswith(b"\xff\xd8"):
        return None
    index = 2
    sof = {
        0xC0, 0xC1, 0xC2, 0xC3,
        0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB,
        0xCD, 0xCE, 0xCF,
    }
    while index + 4 <= len(raw):
        if raw[index] != 0xFF:
            index += 1
            continue
        while index < len(raw) and raw[index] == 0xFF:
            index += 1
        if index >= len(raw):
            break
        marker = raw[index]
        index += 1
        if marker in (0xD8, 0xD9):
            continue
        if index + 2 > len(raw):
            break
        length = int.from_bytes(raw[index:index + 2], "big")
        if length < 2 or index + length > len(raw):
            break
        if marker in sof and length >= 7:
            height = int.from_bytes(raw[index + 3:index + 5], "big")
            width = int.from_bytes(raw[index + 5:index + 7], "big")
            return width, height
        index += length
    return None


def _svg_dimensions(raw: bytes) -> tuple[int, int] | None:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None

    def number(value):
        if not isinstance(value, str):
            return None
        match = re.fullmatch(
            r"\s*([0-9]+(?:\.[0-9]+)?)\s*(?:px)?\s*", value)
        return float(match.group(1)) if match else None

    width = number(root.attrib.get("width"))
    height = number(root.attrib.get("height"))
    if width is not None and height is not None:
        if width.is_integer() and height.is_integer():
            return int(width), int(height)
        return None

    view_box = root.attrib.get("viewBox")
    if isinstance(view_box, str):
        parts = re.split(r"[\s,]+", view_box.strip())
        if len(parts) == 4:
            try:
                width = float(parts[2])
                height = float(parts[3])
            except ValueError:
                return None
            if width.is_integer() and height.is_integer():
                return int(width), int(height)
    return None


def image_dimensions(
        raw: bytes, media_type: str) -> tuple[int, int] | None:
    """Read output dimensions without an image-processing dependency."""
    if media_type == "image/png":
        if (
                len(raw) >= 24
                and raw.startswith(b"\x89PNG\r\n\x1a\n")
                and raw[12:16] == b"IHDR"):
            return struct.unpack(">II", raw[16:24])
        return None

    if media_type in ("image/jpeg", "image/jpg"):
        return _jpeg_dimensions(raw)

    if media_type == "image/svg+xml":
        return _svg_dimensions(raw)

    if media_type == "image/webp":
        if len(raw) < 30 or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            return None
        chunk = raw[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(raw[24:27], "little")
            height = 1 + int.from_bytes(raw[27:30], "little")
            return width, height
        if chunk == b"VP8L" and len(raw) >= 25 and raw[20] == 0x2F:
            b1, b2, b3, b4 = raw[21:25]
            width = 1 + b1 + ((b2 & 0x3F) << 8)
            height = 1 + ((b2 & 0xC0) >> 6) + (b3 << 2) + (
                (b4 & 0x0F) << 10)
            return width, height
        if (
                chunk == b"VP8 "
                and len(raw) >= 30
                and raw[23:26] == b"\x9d\x01\x2a"):
            width = int.from_bytes(raw[26:28], "little") & 0x3FFF
            height = int.from_bytes(raw[28:30], "little") & 0x3FFF
            return width, height
        return None

    return None


def build_openrouter_payload(
        *,
        model: str,
        image_bytes: bytes,
        content_type: str,
        prompt: str,
        width: int,
        height: int) -> dict:
    """Build one exact image-to-image request for OpenRouter's Image API."""
    source = (
        "data:" + content_type + ";base64,"
        + base64.b64encode(image_bytes).decode("ascii")
    )
    # OpenRouter's unified Image API currently standardizes reference-image
    # editing, but exact pixel-size controls are model-dependent. The exact
    # target remains in the fixed prompt, and we mechanically reject any
    # returned image whose intrinsic dimensions are not the requested canvas.
    return {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "input_references": [
            {
                "type": "image_url",
                "image_url": {"url": source},
            }
        ],
    }


class OpenRouterPageGateway:
    def __init__(
            self, *,
            api_key: str,
            model: str,
            endpoint: str = OPENROUTER_IMAGES_URL,
            output_dir: str = GENERATED_PAGE_DIR,
            timeout: float = 300.0):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.output_dir = output_dir
        self.timeout = timeout

    def _edit(
            self, *,
            image_bytes: bytes,
            content_type: str,
            prompt: str,
            width: int,
            height: int) -> tuple[bytes, str, float | None]:
        payload = build_openrouter_payload(
            model=self.model,
            image_bytes=image_bytes,
            content_type=content_type,
            prompt=prompt,
            width=width,
            height=height,
        )
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                    request, timeout=self.timeout) as response:
                raw = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            sys.stderr.write(
                "[page-image-gateway] OpenRouter HTTP %s\n" % exc.code)
            raise RuntimeError("openrouter-image-error") from exc
        except OSError as exc:
            raise RuntimeError("openrouter-unavailable") from exc

        if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
            raise RuntimeError("openrouter-response-too-large")

        try:
            result = json.loads(raw.decode("utf-8"))
            item = (result.get("data") or [])[0]
            encoded = item.get("b64_json")
            if not isinstance(encoded, str) or not encoded:
                raise ValueError("missing image bytes")
            image = base64.b64decode(encoded, validate=True)
            media_type = _media_type_from_bytes(
                image, item.get("media_type"))
            if media_type not in _OUTPUT_EXTENSIONS:
                raise ValueError("unsupported output image type")
            dimensions = image_dimensions(image, media_type)
            if dimensions != (width, height):
                raise ValueError(
                    "provider output dimensions %r, expected %dx%d"
                    % (dimensions, width, height))
            cost = result.get("usage", {}).get("cost")
            if not isinstance(cost, (int, float)):
                cost = None
            return image, media_type, cost
        except (IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("invalid-openrouter-image-response") from exc

    def reframe_page(
            self, *,
            image_bytes: bytes,
            content_type: str,
            filename: str) -> dict:
        if not supported_upload(filename, content_type):
            return {"ok": False, "error": "unsupported-page-image-type"}
        if not image_bytes:
            return {"ok": False, "error": "empty-page-image"}
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            return {"ok": False, "error": "page-image-too-large"}

        jobs = generation_plan(filename)
        generated = {}
        total_cost = 0.0
        cost_seen = False

        try:
            for orientation in ("landscape", "portrait"):
                job = jobs[orientation]
                image, media_type, cost = self._edit(
                    image_bytes=image_bytes,
                    content_type=content_type,
                    prompt=job["prompt"],
                    width=job["width"],
                    height=job["height"],
                )
                generated[orientation] = {
                    "bytes": image,
                    "media_type": media_type,
                    "width": job["width"],
                    "height": job["height"],
                }
                if cost is not None:
                    total_cost += float(cost)
                    cost_seen = True
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc)}

        token = uuid.uuid4().hex
        target_dir = os.path.join(self.output_dir, token)
        os.makedirs(target_dir, exist_ok=False)

        variants = {}
        for orientation in ("landscape", "portrait"):
            item = generated[orientation]
            extension = _OUTPUT_EXTENSIONS[item["media_type"]]
            name = variant_filename(filename, orientation, extension)
            path = os.path.join(target_dir, name)
            with open(path, "wb") as handle:
                handle.write(item["bytes"])
            variants[orientation] = {
                "src": "/generated-pages/" + token + "/" + name,
                "filename": name,
                "width": item["width"],
                "height": item["height"],
                "media_type": item["media_type"],
            }

        draft = {
            "summary": "horizontal and portrait page variants ready",
            "source_name": os.path.basename(filename),
            "model": self.model,
            "variants": variants,
        }
        if cost_seen:
            draft["cost"] = round(total_cost, 8)

        return {"ok": True, "draft": draft}


def make_handler(gateway: OpenRouterPageGateway, quiet: bool = False):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] == "/health":
                return self._send(200, {
                    "ok": True,
                    "service": "stickerbook-page-image-gateway",
                    "model": gateway.model,
                })
            return self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if self.path.split("?")[0] != "/v1/page/reframe":
                return self._send(404, {"ok": False, "error": "not found"})

            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, {"ok": False, "error": "bad length"})
            if length <= 0:
                return self._send(400, {"ok": False, "error": "empty-page-image"})
            if length > MAX_UPLOAD_BYTES:
                return self._send(413, {"ok": False, "error": "page-image-too-large"})

            content_type = (self.headers.get("Content-Type") or "").split(";")[0]
            raw_name = self.headers.get("X-StickerBook-Filename") or "page.png"
            filename = urllib.parse.unquote(raw_name)
            image_bytes = self.rfile.read(length)

            if content_type not in SUPPORTED_IMAGE_TYPES:
                return self._send(
                    415, {"ok": False, "error": "unsupported-page-image-type"})

            result = gateway.reframe_page(
                image_bytes=image_bytes,
                content_type=content_type,
                filename=filename,
            )
            return self._send(200 if result.get("ok") else 400, result)

        def _send(self, status: int, payload: dict):
            raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def address_string(self):
            return self.client_address[0]

        def log_message(self, fmt, *args):
            if not quiet:
                sys.stderr.write("[page-image-gateway] %s\n" % (fmt % args))

    return Handler


def serve(
        host: str,
        port: int,
        *,
        api_key: str,
        model: str,
        quiet: bool = False):
    gateway = OpenRouterPageGateway(api_key=api_key, model=model)
    httpd = ThreadingHTTPServer((host, port), make_handler(gateway, quiet))
    return httpd, gateway


if __name__ == "__main__":
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get(
        "STICKERBOOK_OPENROUTER_IMAGE_MODEL", "").strip()
    port = int(os.environ.get("STICKERBOOK_IMAGE_GATEWAY_PORT", "8757"))

    if not api_key:
        sys.stderr.write(
            "StickerBook page image gateway: OPENROUTER_API_KEY is required.\n")
        raise SystemExit(2)
    if not model:
        sys.stderr.write(
            "StickerBook page image gateway: "
            "STICKERBOOK_OPENROUTER_IMAGE_MODEL is required.\n")
        raise SystemExit(2)

    try:
        httpd, gateway = serve(
            "127.0.0.1", port, api_key=api_key, model=model)
    except OSError as exc:
        sys.stderr.write(
            "StickerBook page image gateway: cannot listen on "
            "127.0.0.1:%d -- %s\n" % (port, exc))
        raise SystemExit(2)

    print(
        "StickerBook page image gateway on http://127.0.0.1:%d/ "
        "(model %s)" % (port, gateway.model))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        httpd.server_close()
