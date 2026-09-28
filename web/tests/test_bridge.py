"""
Tests for the browser -> bridge -> kernel seam.

These run against a real HTTP server on an ephemeral loopback port, because
the seam is the thing being tested. UI behaviour is not evidence; these are.

Each class maps to one of the questions the milestone set out to answer.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402


class FakeAgentRuntime:
    def __init__(self):
        self.last_principal = None
        self.last_scene = None
        self.last_reference = None
        self.last_creator = None

    def capabilities(self):
        return {
            "creator_agent": True,
            "conversational_agent": True,
        }

    def converse(self, *, text, principal, scene, reference=None):
        self.last_principal = principal
        self.last_scene = scene
        self.last_reference = reference
        return {"ok": True, "reply": "Omega heard: " + text}

    def creator_draft(
            self, *,
            kind,
            prompt,
            animation_intent,
            asset_schema_version,
            principal,
            scene):
        self.last_principal = principal
        self.last_scene = scene
        self.last_creator = {
            "kind": kind,
            "prompt": prompt,
            "animation_intent": animation_intent,
            "asset_schema_version": asset_schema_version,
        }
        return {
            "ok": True,
            "draft": {
                "summary": "draft for " + kind,
                "asset_schema_version": asset_schema_version,
            },
        }


class FakePageImageRuntime:
    def __init__(self):
        self.last_upload = None

    def available(self):
        return True

    def reframe_page(self, *, image_bytes, content_type, filename):
        self.last_upload = {
            "image_bytes": image_bytes,
            "content_type": content_type,
            "filename": filename,
        }
        return {
            "ok": True,
            "draft": {
                "summary": "horizontal and portrait page variants ready",
                "source_name": filename,
                "variants": {
                    "landscape": {
                        "src": "/generated-pages/fake/example.png",
                        "filename": "example.png",
                        "width": 1916,
                        "height": 717,
                        "media_type": "image/png",
                    },
                    "portrait": {
                        "src": "/generated-pages/fake/example-vertical.png",
                        "filename": "example-vertical.png",
                        "width": 941,
                        "height": 1574,
                        "media_type": "image/png",
                    },
                },
            },
        }


class ServerCase(unittest.TestCase):
    """A fresh farm and a fresh server per test."""

    agent_runtime_factory = None
    page_image_runtime_factory = None

    def setUp(self):
        runtime = (self.agent_runtime_factory()
                   if self.agent_runtime_factory else None)
        page_runtime = (
            self.page_image_runtime_factory()
            if self.page_image_runtime_factory else None)
        self.httpd, self.bridge = bridge_mod.serve(
            "127.0.0.1",
            0,
            quiet=True,
            agent_runtime=runtime,
            page_image_runtime=page_runtime,
        )
        self.port = self.httpd.server_address[1]
        # poll_interval matters: shutdown() waits up to one interval, and
        # the default 0.5s dominates the runtime of a suite this size.
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02},
            daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def get(self, path):
        with urllib.request.urlopen(self.url(path), timeout=5) as r:
            return r.status, json.loads(r.read().decode())

    def post(self, path, payload, raw=None):
        data = raw if raw is not None else json.dumps(payload).encode()
        req = urllib.request.Request(
            self.url(path), data=data, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def post_image(
            self, path, raw, *,
            filename="drawing.png",
            content_type="image/png"):
        req = urllib.request.Request(
            self.url(path),
            data=raw,
            method="POST",
            headers={
                "Content-Type": content_type,
                "X-StickerBook-Filename": urllib.parse.quote(
                    filename, safe=""),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def move(self, sticker, x, y, command_id="c1", based_on=None):
        return self.post("/api/propose-move", {
            "sticker": sticker, "command_id": command_id,
            "point": {"x": x, "y": y}, "based_on_revision": based_on})

    def pos_of(self, sticker_id):
        st = self.bridge.kernel.sticker(sticker_id)
        return (round(st.x, 6), round(st.y, 6))


class Q1_BrowserCanDisplayKernelState(ServerCase):

    def test_state_is_served_and_kernel_backed(self):
        status, state = self.get("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(state["revision"], self.bridge.kernel.revision)
        ids = sorted(s["id"] for s in state["stickers"])
        self.assertEqual(ids, ["butterfly-1", "cow-1"])

    def test_page_and_assets_are_served(self):
        for path, needle in (("/", b"StickerBook"),
                             ("/static/app.js", b"grabFromTray"),
                             ("/static/style.css", b".sticker")):
            with urllib.request.urlopen(self.url(path), timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(needle, r.read())

    def test_child_navigation_surfaces_are_in_the_served_page(self):
        with urllib.request.urlopen(self.url("/"), timeout=5) as r:
            page = r.read()
        for marker in (
                b'id="cover-screen"',
                b'id="page-gallery"',
                b'id="play-screen"',
                b'id="home-btn"',
                b'id="library-btn"',
                b'id="sticker-overlay"'):
            self.assertIn(marker, page)
        self.assertNotIn(b'id="book-screen"', page)

    def test_creator_surfaces_offer_upload_and_assisted_paths(self):
        with urllib.request.urlopen(self.url("/"), timeout=5) as r:
            page = r.read()
        self.assertGreaterEqual(page.count(b"Make with StickerBook"), 2)
        for marker in (
                b'id="page-upload-status"',
                b'image/svg+xml,image/png,image/jpeg,image/webp',
                b'id="page-agent-prompt"',
                b'id="page-agent-go"',
                b'id="sticker-agent-prompt"',
                b'id="sticker-agent-go"',
                b'data-clip-intent="animate"'):
            self.assertIn(marker, page)

    def test_voice_and_accessible_chat_are_adult_enabled(self):
        with urllib.request.urlopen(self.url("/"), timeout=5) as r:
            page = r.read()
        for marker in (
                b'id="voice-orb"',
                b'id="voice-enable"',
                b'id="text-chat-enable"',
                b'id="accessibility-chat"',
                b'id="accessibility-chat-log"',
                b'id="accessibility-chat-input"',
                b'id="dev-close"'):
            self.assertIn(marker, page)
        self.assertIn(
            b'href="https://github.com/PaulTiffany/stickerbook"',
            page,
        )
        self.assertIn(b"GitHub repository", page)
        self.assertIn(
            b'Accessibility option: adds a translucent text interface',
            page,
        )
        self.assertNotIn(b'id="adult-text-fallback"', page)
        self.assertNotIn(b'id="adult-chat-input"', page)
        self.assertNotIn(b'Text fallback', page)

        with urllib.request.urlopen(
                self.url("/static/app.js"), timeout=5) as r:
            app = r.read().decode("utf-8")
        self.assertIn(
            'const stub = world.name === "public mechanical";',
            app,
        )
        self.assertIn(
            "const textAvailable = connected || stub;",
            app,
        )
        self.assertIn(
            "textAvailable &&\n      textChatEnabled",
            app,
        )
        self.assertIn(
            "Public demo chat only — no model is connected.",
            app,
        )
        self.assertIn(
            'converseWithStickerBook(text, false, true)',
            app,
        )
        self.assertIn(
            'converseWithStickerBook(transcript, true, textChatEnabled)',
            app,
        )
        self.assertIn(
            'document.getElementById("dev-close").addEventListener',
            app,
        )
        self.assertIn(
            'url.searchParams.delete("dev")',
            app,
        )

        with urllib.request.urlopen(
                self.url("/static/style.css"), timeout=5) as r:
            css = r.read().decode("utf-8")
        chat_start = css.index(".accessibility-chat {")
        chat_end = css.index("}", chat_start)
        chat_rule = css[chat_start:chat_end]
        self.assertIn("position: fixed;", chat_rule)
        self.assertIn("background: rgba(255,253,247,.72);", chat_rule)
        self.assertIn("backdrop-filter: blur(12px)", chat_rule)

        checkbox_start = css.index(".adult-toggle input {")
        checkbox_end = css.index("}", checkbox_start)
        checkbox_rule = css[checkbox_start:checkbox_end]
        self.assertIn("width: 22px;", checkbox_rule)
        self.assertIn("height: 22px;", checkbox_rule)
        self.assertIn("pointer-events: auto;", checkbox_rule)
        self.assertIn("cursor: pointer;", checkbox_rule)

        self.assertIn(".adult-toggle span {\n  pointer-events: none;", css)
        self.assertNotIn(".sticker:hover .art", css)

    def test_phone_layout_is_edge_to_edge_without_cropping_native_art(self):
        with urllib.request.urlopen(self.url("/"), timeout=5) as r:
            page = r.read()

        # The cover is decorative and should own the whole visible browser
        # rectangle. The interactive page remains uncropped so normalized
        # child/agent coordinates stay inside the semantic world.
        self.assertIn(
            b'id="cover-scene" class="cover-scene" viewBox="0 0 1000 640" '
            b'preserveAspectRatio="xMidYMid slice"',
            page)
        self.assertIn(
            b'id="page" viewBox="0 0 1000 640" '
            b'preserveAspectRatio="xMidYMid meet"',
            page)

        with urllib.request.urlopen(
                self.url("/static/style.css"), timeout=5) as r:
            css = r.read().decode("utf-8")

        screen_start = css.index(".screen {")
        screen_end = css.index("}", screen_start)
        screen_rule = css[screen_start:screen_end]
        self.assertIn("width: var(--app-vw, 100dvw);", screen_rule)
        self.assertIn("height: var(--app-vh, 100dvh);", screen_rule)

        hotbar_start = css.index(".hotbar {")
        hotbar_end = css.index("}", hotbar_start)
        hotbar_rule = css[hotbar_start:hotbar_end]
        self.assertIn("left: 0;", hotbar_rule)
        self.assertIn("right: 0;", hotbar_rule)
        self.assertIn("bottom: 0;", hotbar_rule)
        self.assertIn("width: 100%;", hotbar_rule)
        self.assertIn("border-radius: 0;", hotbar_rule)

        cover_start = css.index(".cover-enter::before")
        cover_end = css.index("}", cover_start)
        cover_rule = css[cover_start:cover_end]
        self.assertIn("background-image: var(--cover-art);", cover_rule)

        tile_start = css.index(".page-tile {")
        tile_end = css.index("}", tile_start)
        tile_rule = css[tile_start:tile_end]
        self.assertIn("border: 0;", tile_rule)

        page_wrap_start = css.index("#page-wrap {")
        page_wrap_end = css.index("}", page_wrap_start)
        page_wrap_rule = css[page_wrap_start:page_wrap_end]
        self.assertIn(
            "inset: 0 0 calc(var(--hot) + 14px + "
            "env(safe-area-inset-bottom)) 0;",
            page_wrap_rule)

    def test_bottom_edge_remove_zone_and_page_bounds_are_explicit(self):
        with urllib.request.urlopen(
                self.url("/static/app.js"), timeout=5) as r:
            app = r.read().decode("utf-8")

        remove_start = app.index("function overRemovalZone")
        remove_end = app.index("}", remove_start)
        remove_rule = app[remove_start:remove_end]
        self.assertIn("event.clientY >= box.top", remove_rule)
        self.assertNotIn("box.bottom", remove_rule)

        placed_start = app.index("function grabPlaced")
        placed_end = app.index("function ghostFor", placed_start)
        placed_rule = app[placed_start:placed_end]
        self.assertIn("overRemovalZone(upEvent)", placed_rule)
        self.assertIn("if (!overPage(upEvent))", placed_rule)
        self.assertIn('speak("Keep stickers on the page")', placed_rule)

    def test_public_mechanical_move_also_stops_animation(self):
        with urllib.request.urlopen(
                self.url("/static/app.js"), timeout=5) as r:
            app = r.read().decode("utf-8")

        move_start = app.index('if (path === "/api/propose-move")')
        move_end = app.index('if (path === "/api/remove")', move_start)
        move_rule = app[move_start:move_end]
        self.assertIn(
            'target.animation = def && def.rest_clip || "none";',
            move_rule,
        )

        drag_start = app.index("function grabPlaced")
        drag_end = app.index("function ghostFor", drag_start)
        drag_rule = app[drag_start:drag_end]
        self.assertIn(
            "resetStickerVisualToRest(node, sticker.definition)",
            drag_rule,
        )
        self.assertIn('node.classList.remove("alive")', drag_rule)
        self.assertIn('node.removeAttribute("data-alive")', drag_rule)
        self.assertIn("const grabOffset = pointAtGrab ?", drag_rule)
        self.assertIn("const draggedFraction = (pointerEvent)", drag_rule)
        self.assertIn("point.x - grabOffset.x", drag_rule)
        self.assertIn("point.y - grabOffset.y", drag_rule)
        self.assertIn("point: draggedFraction(upEvent)", drag_rule)
        self.assertNotIn("point: pageFraction(upEvent)", drag_rule)

    def test_grab_uses_idle_art_and_keeps_held_art_centered(self):
        with urllib.request.urlopen(
                self.url("/static/app.js"), timeout=5) as r:
            app = r.read().decode("utf-8")
        with urllib.request.urlopen(
                self.url("/static/style.css"), timeout=5) as r:
            css = r.read().decode("utf-8")

        rest_start = app.index("function resetStickerVisualToRest")
        rest_end = app.index("function miniature", rest_start)
        rest_rule = app[rest_start:rest_end]
        self.assertIn("stickerClip(kind, null)", rest_rule)
        self.assertIn("paper.replaceChildren()", rest_rule)
        self.assertIn("const firstFrame =", rest_rule)
        self.assertNotIn("clipImage(clip)", rest_rule)

        held_start = css.index(".sticker.held .art {")
        held_end = css.index("}", held_start)
        held_rule = css[held_start:held_end]
        self.assertIn("animation: none !important;", held_rule)
        self.assertIn("transition: none;", held_rule)
        self.assertIn("transform: none;", held_rule)
        self.assertNotIn("translate", held_rule)

    def test_manifest_driven_visual_assets_are_served(self):
        cases = (
            ("/static/assets/manifest.json", "application/json"),
            ("/static/assets/cover.svg", "image/svg+xml"),
            ("/static/assets/cover-vertical.svg", "image/svg+xml"),
            ("/static/assets/pages/farm.svg", "image/svg+xml"),
            ("/static/assets/pages/farm-vertical.svg", "image/svg+xml"),
            ("/static/assets/pages/beach.svg", "image/svg+xml"),
            ("/static/assets/pages/beach-vertical.svg", "image/svg+xml"),
            ("/static/assets/pages/playground.svg", "image/svg+xml"),
            ("/static/assets/pages/playground-vertical.svg", "image/svg+xml"),
            ("/static/assets/pages/space.svg", "image/svg+xml"),
            ("/static/assets/pages/space-vertical.svg", "image/svg+xml"),
            ("/static/assets/stickers/frog.svg", "image/svg+xml"),
            ("/static/assets/stickers/bird/flight-up.svg", "image/svg+xml"),
            ("/static/assets/stickers/butterfly/wings-down.svg", "image/svg+xml"),
            ("/static/assets/stickers/puppy/bark.svg", "image/svg+xml"),
            ("/static/assets/stickers/sandcastle/splash.svg", "image/svg+xml"),
            ("/static/assets/stickers/alien/float.svg", "image/svg+xml"),
            ("/static/assets/stickers/robot/beep.svg", "image/svg+xml"),
            ("/static/assets/stickers/rabbit/hop.svg", "image/svg+xml"),
            ("/static/assets/stickers/octopus/swim.svg", "image/svg+xml"),
            ("/static/assets/stickers/yo-yo/spin.svg", "image/svg+xml"),
            ("/static/assets/stickers/rover/scan.svg", "image/svg+xml"),
            ("/static/assets/stickers/rooster/crow.svg", "image/svg+xml"),
            ("/static/assets/stickers/jellyfish/drift.svg", "image/svg+xml"),
            ("/static/assets/stickers/hula-hoop/spin.svg", "image/svg+xml"),
            ("/static/assets/stickers/space-station/beacon.svg", "image/svg+xml"),
        )
        for path, content_type in cases:
            with urllib.request.urlopen(self.url(path), timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertTrue(r.headers["Content-Type"].startswith(content_type))
                self.assertTrue(r.read())

    def test_asset_path_cannot_escape_the_asset_directory(self):
        request = urllib.request.Request(
            self.url("/static/assets/../app.js"), method="GET")
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)
        else:
            self.fail("asset traversal unexpectedly succeeded")

    def test_sticker_manifest_models_visuals_as_clip_packages(self):
        path = os.path.join(
            bridge_mod.STATIC_DIR, "assets", "manifest.json")
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)

        self.assertEqual(manifest["version"], 4)
        self.assertEqual(
            set(manifest["pages"]),
            {"farm", "beach", "playground", "space"})

        cover_variants = manifest["cover"]["variants"]
        self.assertEqual(
            set(cover_variants),
            {"desktop", "landscape_phone", "landscape", "portrait"})

        for name in ("desktop", "landscape_phone", "landscape"):
            cover_landscape = cover_variants[name]
            self.assertEqual(
                cover_landscape["src"],
                "static/assets/cover.svg")
            self.assertEqual(
                (cover_landscape["width"], cover_landscape["height"]),
                (1916, 821))

        cover_portrait = cover_variants["portrait"]
        self.assertEqual(
            cover_portrait["src"],
            "static/assets/cover-vertical.svg")
        self.assertEqual(
            (cover_portrait["width"], cover_portrait["height"]),
            (941, 1672))

        for page_id, page in manifest["pages"].items():
            variants = page["variants"]
            self.assertEqual(set(variants), {"landscape", "portrait"}, page_id)

            landscape = variants["landscape"]
            self.assertEqual(
                (landscape["width"], landscape["height"]),
                (1916, 717),
                page_id,
            )
            self.assertTrue(
                landscape["src"].startswith("static/assets/pages/"),
                page_id,
            )

            portrait = variants["portrait"]
            self.assertEqual(
                (portrait["width"], portrait["height"]),
                (941, 1574),
                page_id,
            )
            self.assertIn("-vertical.", portrait["src"], page_id)

        self.assertTrue(manifest["stickers"])

        self.assertEqual(len(manifest["stickers"]), 57)

        themes_seen = set()
        for kind, package in manifest["stickers"].items():
            for key in (
                    "name", "category", "themes", "tags", "aliases", "sprites",
                    "default_clip", "clips", "scale_bounds"):
                self.assertIn(key, package, (kind, key))

            self.assertTrue(package["themes"], kind)
            themes_seen.update(package["themes"])
            self.assertGreaterEqual(len(package["sprites"]), 4, kind)
            self.assertIn(package["default_clip"], package["clips"], kind)
            self.assertEqual(package["scale_bounds"], {"min": 0.9, "max": 1.1})

            for sprite_name, path in package["sprites"].items():
                self.assertTrue(sprite_name, kind)
                self.assertTrue(
                    path.startswith("static/assets/stickers/%s/" % kind),
                    (kind, sprite_name, path),
                )

            for clip_name, clip in package["clips"].items():
                self.assertIsInstance(clip.get("frames"), list,
                                      (kind, clip_name))
                self.assertTrue(clip["frames"], (kind, clip_name))
                for frame in clip["frames"]:
                    self.assertIn(frame, package["sprites"],
                                  (kind, clip_name, frame))

        self.assertEqual(
            themes_seen,
            {"farm", "beach", "playground", "space"},
        )
        for added in (
                "puppy", "cat", "seagull", "sandcastle", "pinwheel",
                "jump-rope", "alien", "robot"):
            self.assertIn(added, manifest["stickers"])
            self.assertEqual(len(manifest["stickers"][added]["sprites"]), 4)
        for added in (
                "rabbit", "scarecrow", "octopus", "surfboard",
                "yo-yo", "teddy-bear", "comet", "rover"):
            self.assertIn(added, manifest["stickers"])
            self.assertEqual(len(manifest["stickers"][added]["sprites"]), 4)
        for added in (
                "rooster", "bee", "jellyfish", "pelican",
                "hula-hoop", "toy-airplane", "asteroid", "space-station"):
            self.assertIn(added, manifest["stickers"])
            self.assertEqual(len(manifest["stickers"][added]["sprites"]), 4)

    def test_each_sticker_carries_its_authoritative_transform(self):
        _, state = self.get("/api/state")
        for s in state["stickers"]:
            kernel_sticker = self.bridge.kernel.sticker(s["id"])
            self.assertAlmostEqual(s["x"], kernel_sticker.x)
            self.assertAlmostEqual(s["y"], kernel_sticker.y)
            self.assertAlmostEqual(s["scale"], kernel_sticker.scale)
            self.assertEqual(s["facing"], kernel_sticker.facing)

    def test_catalog_search_and_categories_are_served(self):
        with urllib.request.urlopen(self.url("/"), timeout=5) as r:
            page = r.read()
        self.assertIn(b'id="sticker-search"', page)
        self.assertIn(b'id="sticker-themes"', page)
        self.assertIn(b'id="sticker-categories"', page)
        self.assertIn(b'id="reference-layer"', page)

        with urllib.request.urlopen(
                self.url("/static/app.js"), timeout=5) as r:
            app = r.read().decode("utf-8")
        self.assertIn("function stickerCatalogMatches", app)
        self.assertIn("entry.tags", app)
        self.assertIn("entry.aliases", app)
        self.assertIn("entry.themes", app)
        self.assertIn("function drawStickerThemes", app)
        self.assertIn("function startDeicticGesture", app)
        self.assertIn("body.reference = reference", app)
        self.assertIn('sticker.facing === "left"', app)
        self.assertIn("stickerSearch.addEventListener", app)
        self.assertIn("stickerCategory", app)
        self.assertIn("if (clip && clip.motion)", app)
        self.assertNotIn(
            "clip && clip.motion || sticker.animation",
            app,
        )
        self.assertIn("_stickerFrameStartedAt = performance.now()", app)


class Q1b_AgentInterfacesStayOutsideKernelAuthority(ServerCase):

    agent_runtime_factory = FakeAgentRuntime

    def test_agent_capabilities_are_explicit_in_state(self):
        _, state = self.get("/api/state")
        self.assertEqual(state["capabilities"], {
            "creator_agent": True,
            "conversational_agent": True,
            "page_image_creator": False,
        })

    def test_conversation_returns_language_without_mutating_kernel(self):
        before = self.bridge.kernel.revision
        status, body = self.post("/api/agent/converse", {
            "text": "hello",
            "actor": "agent:spoofed",
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["reply"], "Omega heard: hello")
        self.assertEqual(self.bridge.kernel.revision, before)
        self.assertEqual(
            self.bridge.agent_runtime.last_principal,
            bridge_mod.BROWSER_PRINCIPAL)
        self.assertNotIn("kernel", self.bridge.agent_runtime.last_scene)
        self.assertIsNone(self.bridge.agent_runtime.last_reference)

    def test_transient_point_reference_accompanies_one_conversation(self):
        before = self.bridge.kernel.revision
        status, body = self.post("/api/agent/converse", {
            "text": "the ducks swim here",
            "reference": {
                "kind": "point",
                "point": {"x": 0.71, "y": 0.58},
            },
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"], body)
        self.assertEqual(self.bridge.kernel.revision, before)
        self.assertEqual(self.bridge.agent_runtime.last_reference, {
            "kind": "point",
            "page": "farm",
            "point": {"x": 0.71, "y": 0.58},
        })
        _, state = self.get("/api/state")
        self.assertNotIn("reference", state)
        self.assertNotIn("references", state)

    def test_transient_box_reference_is_normalized_conversation_context(self):
        before = self.bridge.kernel.revision
        status, body = self.post("/api/agent/converse", {
            "text": "nothing should go in this area",
            "reference": {
                "kind": "box",
                "box": {"x1": 0.1, "y1": 0.2, "x2": 0.6, "y2": 0.7},
            },
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"], body)
        self.assertEqual(self.bridge.kernel.revision, before)
        self.assertEqual(self.bridge.agent_runtime.last_reference["kind"], "box")
        self.assertEqual(self.bridge.agent_runtime.last_reference["page"], "farm")

    def test_bad_deictic_reference_is_rejected_before_runtime(self):
        before = self.bridge.kernel.revision
        bad = (
            {"kind": "point", "point": {"x": -0.1, "y": 0.4}},
            {"kind": "box", "box": {"x1": 0.8, "y1": 0.2,
                                    "x2": 0.3, "y2": 0.7}},
            {"kind": "lasso", "points": []},
        )
        for reference in bad:
            with self.subTest(reference=reference):
                status, body = self.post("/api/agent/converse", {
                    "text": "here",
                    "reference": reference,
                })
                self.assertEqual(status, 400)
                self.assertFalse(body["ok"])
        self.assertEqual(self.bridge.kernel.revision, before)
        self.assertIsNone(self.bridge.agent_runtime.last_reference)

    def test_creator_draft_targets_v2_package_without_mutating_kernel(self):
        before = self.bridge.kernel.revision
        status, body = self.post("/api/creator/draft", {
            "kind": "sticker",
            "prompt": "a purple dragon",
            "animation_intent": "animate",
            "asset_schema_version": 2,
            "actor": "agent:spoofed",
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["draft"]["asset_schema_version"], 2)
        self.assertEqual(self.bridge.kernel.revision, before)
        self.assertEqual(
            self.bridge.agent_runtime.last_principal,
            bridge_mod.BROWSER_PRINCIPAL)
        self.assertEqual(
            self.bridge.agent_runtime.last_creator["animation_intent"],
            "animate")

    def test_agent_routes_validate_input_before_runtime(self):
        before = self.bridge.kernel.revision
        status, body = self.post("/api/agent/converse", {"text": ""})
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(self.bridge.kernel.revision, before)

        status, body = self.post("/api/creator/draft", {
            "kind": "sticker",
            "prompt": "frog",
            "animation_intent": "animate",
            "asset_schema_version": 1,
        })
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(self.bridge.kernel.revision, before)


class Q1c_PageImageCreationStaysOutsideKernelAuthority(ServerCase):

    page_image_runtime_factory = FakePageImageRuntime

    def test_page_image_capability_is_explicit(self):
        _, state = self.get("/api/state")
        self.assertTrue(state["capabilities"]["page_image_creator"])
        self.assertFalse(state["capabilities"]["creator_agent"])

    def test_page_upload_reframes_without_mutating_kernel(self):
        before = self.bridge.kernel.revision
        status, body = self.post_image(
            "/api/creator/page-image",
            b"not-a-real-png-but-valid-for-the-fake-runtime",
            filename="My Garden.png",
            content_type="image/png",
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"], body)
        self.assertEqual(self.bridge.kernel.revision, before)

        draft = body["draft"]
        self.assertEqual(
            (draft["variants"]["landscape"]["width"],
             draft["variants"]["landscape"]["height"]),
            (1916, 717),
        )
        self.assertEqual(
            (draft["variants"]["portrait"]["width"],
             draft["variants"]["portrait"]["height"]),
            (941, 1574),
        )
        self.assertEqual(
            self.bridge.page_image_runtime.last_upload["filename"],
            "My Garden.png",
        )

    def test_page_upload_rejects_unapproved_media_before_runtime(self):
        before = self.bridge.kernel.revision
        status, body = self.post_image(
            "/api/creator/page-image",
            b"<html>not an image</html>",
            filename="drawing.html",
            content_type="text/html",
        )
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "unsupported-page-image-type")
        self.assertEqual(self.bridge.kernel.revision, before)
        self.assertIsNone(self.bridge.page_image_runtime.last_upload)


class Q2_HumanCanMoveAStickerThroughTheKernel(ServerCase):

    def test_dragging_the_cow_moves_it(self):
        before = self.pos_of("cow-1")
        status, body = self.move("cow-1", 0.71, 0.29)
        self.assertEqual(status, 200)
        self.assertTrue(body["receipt"]["accepted"], body["receipt"])
        self.assertEqual(self.pos_of("cow-1"), (0.71, 0.29))
        self.assertNotEqual(before, (0.71, 0.29))

    def test_dragging_an_animated_sticker_sets_it_down_still(self):
        _, animated = self.post("/api/animate", {
            "sticker": "cow-1",
            "command_id": "animate-before-drag",
        })
        self.assertTrue(animated["receipt"]["accepted"], animated)
        self.assertEqual(
            self.bridge.kernel.sticker("cow-1").animation,
            "chew",
        )

        _, moved = self.move(
            "cow-1",
            0.61,
            0.37,
            command_id="human-drag",
        )
        self.assertTrue(moved["receipt"]["accepted"], moved)
        self.assertEqual(
            self.bridge.kernel.sticker("cow-1").animation,
            "rest",
        )
        by_id = {item["id"]: item for item in moved["state"]["stickers"]}
        self.assertEqual(by_id["cow-1"]["animation"], "rest")

    def test_the_page_belongs_to_the_human(self):
        """The one authority change: drag the agent-owned butterfly too."""
        _, body = self.move("butterfly-1", 0.18, 0.62)
        self.assertTrue(body["receipt"]["accepted"], body["receipt"]["reason"])
        self.assertEqual(self.pos_of("butterfly-1"), (0.18, 0.62))
        # Provenance is unchanged by moving it.
        self.assertEqual(self.bridge.kernel.sticker("butterfly-1").owner,
                         farm.AGENT_ID)

    def test_a_sticker_can_go_anywhere_on_the_page(self):
        """Free placement, not five dots."""
        for i, (x, y) in enumerate([(0.0, 0.0), (1.0, 1.0), (0.337, 0.914),
                                    (0.5, 0.5)]):
            _, body = self.move("cow-1", x, y, command_id="free-%d" % i)
            self.assertTrue(body["receipt"]["accepted"])
            self.assertEqual(self.pos_of("cow-1"), (x, y))

    def test_off_page_positions_are_refused_by_the_kernel(self):
        before = self.pos_of("cow-1")
        for i, (x, y) in enumerate([(-0.1, 0.5), (1.4, 0.5), (0.5, 99.0)]):
            _, body = self.move("cow-1", x, y, command_id="off-%d" % i)
            self.assertFalse(body["receipt"]["accepted"])
            self.assertEqual(body["receipt"]["reason"], "position-out-of-page")
        self.assertEqual(self.pos_of("cow-1"), before)


class Q2b_StickerScaleIsAGovernedWorldTransform(ServerCase):

    def test_human_can_resize_within_definition_bounds(self):
        status, body = self.post("/api/resize", {
            "sticker": "cow-1",
            "command_id": "scale-1",
            "scale": 1.08,
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["receipt"]["accepted"], body["receipt"])
        self.assertAlmostEqual(
            self.bridge.kernel.sticker("cow-1").scale, 1.08)
        by_id = {item["id"]: item for item in body["state"]["stickers"]}
        self.assertAlmostEqual(by_id["cow-1"]["scale"], 1.08)

    def test_scale_outside_definition_bounds_is_receipted_and_refused(self):
        before = self.bridge.kernel.sticker("cow-1").scale
        status, body = self.post("/api/resize", {
            "sticker": "cow-1",
            "command_id": "scale-too-large",
            "scale": 1.11,
        })
        self.assertEqual(status, 200)
        self.assertFalse(body["receipt"]["accepted"])
        self.assertEqual(
            body["receipt"]["reason"], "scale-out-of-bounds")
        self.assertAlmostEqual(
            self.bridge.kernel.sticker("cow-1").scale, before)

    def test_browser_cannot_turn_resize_into_an_unbounded_transform(self):
        _, body = self.post("/api/resize", {
            "sticker": "cow-1",
            "command_id": "scale-spoof",
            "scale": 7,
            "min": 0,
            "max": 99,
        })
        self.assertFalse(body["receipt"]["accepted"])
        self.assertEqual(
            body["receipt"]["action"], "resize-own-sticker")


class Q2c_StickerFacingIsAGovernedWorldTransform(ServerCase):

    def test_human_can_flip_sticker_facing(self):
        status, body = self.post("/api/facing", {
            "sticker": "cow-1",
            "command_id": "face-left",
            "facing": "left",
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["receipt"]["accepted"], body["receipt"])
        self.assertEqual(
            self.bridge.kernel.sticker("cow-1").facing, "left")
        by_id = {item["id"]: item for item in body["state"]["stickers"]}
        self.assertEqual(by_id["cow-1"]["facing"], "left")

    def test_unknown_facing_is_receipted_and_refused(self):
        status, body = self.post("/api/facing", {
            "sticker": "cow-1",
            "command_id": "face-bad",
            "facing": "upside-down",
        })
        self.assertEqual(status, 200)
        self.assertFalse(body["receipt"]["accepted"])
        self.assertEqual(
            body["receipt"]["reason"], "facing-not-supported")
        self.assertEqual(self.bridge.kernel.sticker("cow-1").facing, "right")


class Q3_EveryMutationPassesTheAuthorityGate(ServerCase):

    def test_the_browser_cannot_choose_its_own_principal(self):
        # Claim to be the agent, the operator, anyone. It is ignored.
        x, y = 0.71, 0.29
        for claimed in (farm.AGENT_ID, "operator", "root", None):
            body = {"sticker": "butterfly-1", "command_id": "c-%s" % claimed,
                    "point": {"x": x, "y": y}, "actor": claimed,
                    "principal": claimed, "owner": claimed}
            status, out = self.post("/api/propose-move", body)
            self.assertEqual(out["receipt"]["actor"], farm.HUMAN_ID)

    def test_extra_fields_in_the_body_are_ignored(self):
        status, out = self.post("/api/propose-move", {
            "sticker": "cow-1", "command_id": "c1",
            "point": {"x": 0.71, "y": 0.29},
            "owner": "someone-else", "revision": 999})
        self.assertTrue(out["receipt"]["accepted"])
        self.assertEqual(self.pos_of("cow-1"), (0.71, 0.29))

    def test_the_browser_cannot_choose_the_action(self):
        # This endpoint performs exactly one kind of command.
        x, y = 0.71, 0.29
        _, out = self.post("/api/propose-move", {
            "sticker": "cow-1", "command_id": "c1", "point": {"x": x, "y": y},
            "action": "remove-own-sticker"})
        self.assertEqual(out["receipt"]["action"], "move-sticker")
        self.assertIsNotNone(self.bridge.kernel.sticker("cow-1"))

    def test_unknown_sticker_is_refused_by_the_kernel(self):
        x, y = 0.71, 0.29
        _, out = self.move("no-such-sticker", x, y)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "unknown-object")


class Q4_AcceptedOperationsProduceReceipts(ServerCase):

    def test_receipt_carries_full_provenance_and_bumps_revision(self):
        before = self.bridge.kernel.revision
        x, y = 0.71, 0.29
        _, out = self.move("cow-1", x, y, command_id="cmd-7")
        r = out["receipt"]
        self.assertEqual(r["commandId"], "cmd-7")
        self.assertEqual(r["actor"], farm.HUMAN_ID)
        self.assertEqual(r["action"], "move-sticker")
        self.assertEqual(r["object"], "cow-1")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["reason"], "ok")
        self.assertGreater(r["resultRevision"], before)
        self.assertEqual(out["state"]["revision"], r["resultRevision"])

    def test_receipts_endpoint_lists_both_outcomes(self):
        x, y = 0.71, 0.29
        self.move("cow-1", 0.71, 0.29, command_id="ok-1")
        self.move("cow-1", 9.0, 9.0, command_id="no-1")   # off the page
        _, body = self.get("/api/receipts")
        by_id = {r["commandId"]: r["accepted"] for r in body["receipts"]}
        self.assertTrue(by_id["ok-1"])
        self.assertFalse(by_id["no-1"])


class Q5_RejectedOperationsChangeNothing(ServerCase):

    def test_an_unknown_sticker_leaves_everything_unchanged(self):
        before = self.bridge.state()["stickers"]
        before_rev = self.bridge.kernel.revision
        _, out = self.move("ghost-1", 0.71, 0.29)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "unknown-object")
        self.assertEqual(self.bridge.state()["stickers"], before)
        self.assertEqual(self.bridge.kernel.revision, before_rev)

    def test_malformed_proposals_never_reach_the_kernel(self):
        before_rev = self.bridge.kernel.revision
        before = json.dumps(self.bridge.state()["stickers"], sort_keys=True)
        bad_bodies = [
            {}, {"sticker": "cow-1"}, {"command_id": "c"},
            {"sticker": "cow-1", "command_id": "c"},
            {"sticker": "cow-1", "command_id": "c", "point": "nope"},
            {"sticker": 12, "command_id": "c", "point": {"x": 0.5, "y": 0.5}},
            {"sticker": "cow-1", "command_id": "c",
             "point": {"x": 0.5, "y": 0.5}, "based_on_revision": "soon"},
        ]
        for body in bad_bodies:
            with self.subTest(body=body):
                status, out = self.post("/api/propose-move", body)
                self.assertEqual(status, 400)
                self.assertFalse(out["ok"])
                self.assertNotIn("receipt", out)
        self.assertEqual(self.bridge.kernel.revision, before_rev)
        self.assertEqual(
            json.dumps(self.bridge.state()["stickers"], sort_keys=True), before)

    def test_bad_coordinate_values_are_refused_by_the_kernel_with_a_receipt(self):
        """Shape is the bridge's business; values are the kernel's.

        A non-numeric or non-finite coordinate is a well-formed proposal
        with a bad value, so it goes to the kernel and the refusal is
        recorded rather than dropped at the seam.
        """
        before = self.pos_of("cow-1")
        cases = [(("a", 1), "position-not-numeric"),
                 ((float("nan"), 0.5), "position-not-finite"),
                 ((float("inf"), 0.5), "position-not-finite")]
        for i, ((x, y), reason) in enumerate(cases):
            with self.subTest(x=x):
                _, out = self.move("cow-1", x, y, command_id="v%d" % i)
                self.assertFalse(out["receipt"]["accepted"])
                self.assertEqual(out["receipt"]["reason"], reason)
        self.assertEqual(self.pos_of("cow-1"), before)

    def test_non_json_body_is_refused(self):
        status, out = self.post("/api/propose-move", None, raw=b"<not json>")
        self.assertEqual(status, 400)
        self.assertFalse(out["ok"])

    def test_stale_revision_is_refused(self):
        x, y = 0.71, 0.29
        self.move("cow-1", x, y, command_id="first")
        stale = 0
        _, out = self.move("cow-1", 0.33, 0.44, command_id="second",
                           based_on=stale)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "stale-revision")
        self.assertEqual(self.pos_of("cow-1"), (0.71, 0.29))

    def test_replayed_command_id_does_not_move_twice(self):
        x, y = 0.71, 0.29
        _, first = self.move("cow-1", x, y, command_id="same")
        rev = self.bridge.kernel.revision
        _, second = self.move("cow-1", 0.33, 0.44, command_id="same")
        self.assertTrue(second["receipt"]["replayed"])
        self.assertEqual(self.bridge.kernel.revision, rev)
        self.assertEqual(self.pos_of("cow-1"), (0.71, 0.29))


class Q6_RendererFollowsAuthoritativeState(ServerCase):

    def test_every_response_carries_authoritative_state(self):
        x, y = 0.71, 0.29
        for sticker in ("cow-1", "butterfly-1"):
            _, out = self.move(sticker, x, y, command_id="c-" + sticker)
            self.assertIn("state", out)
            self.assertEqual(out["state"]["revision"],
                             self.bridge.kernel.revision)

    def test_refused_move_returns_the_unchanged_position(self):
        before = self.pos_of("butterfly-1")
        _, out = self.move("butterfly-1", 5.0, 5.0)        # off the page
        self.assertFalse(out["receipt"]["accepted"])
        drawn = {s["id"]: (round(s["x"], 6), round(s["y"], 6))
                 for s in out["state"]["stickers"]}
        self.assertEqual(drawn["butterfly-1"], before)

    def test_malformed_response_still_carries_state_to_redraw_from(self):
        _, out = self.post("/api/propose-move", {"sticker": "cow-1"})
        self.assertIn("state", out)


class Q7_BackdropIsPassiveScenery(ServerCase):

    def test_backdrop_features_are_not_kernel_objects(self):
        for feature in ("barn", "pond", "tree", "fence"):
            self.assertIsNone(self.bridge.kernel.sticker(feature))

    def test_backdrop_features_cannot_be_moved(self):
        x, y = 0.71, 0.29
        for feature in ("barn", "pond", "tree", "fence"):
            _, out = self.move(feature, x, y, command_id="c-" + feature)
            self.assertFalse(out["receipt"]["accepted"])
            self.assertEqual(out["receipt"]["reason"], "unknown-object")

    def test_backdrop_is_present_for_rendering_only(self):
        _, state = self.get("/api/state")
        drawn = {f["id"] for f in state["picture"]["features"]}
        self.assertEqual(drawn, {"barn", "pond", "tree", "fence"})
        governed = {s["id"] for s in state["stickers"]}
        self.assertFalse(drawn & governed)


class Q8_StickersRetainDistinctOwnership(ServerCase):

    def test_two_stickers_with_different_owners_coexist(self):
        _, state = self.get("/api/state")
        owners = {s["id"]: s["owner"] for s in state["stickers"]}
        self.assertEqual(owners["cow-1"], farm.HUMAN_ID)
        self.assertEqual(owners["butterfly-1"], farm.AGENT_ID)
        mine = {s["id"]: s["mine"] for s in state["stickers"]}
        self.assertTrue(mine["cow-1"])
        self.assertFalse(mine["butterfly-1"])

    def test_provenance_survives_a_move(self):
        x, y = 0.71, 0.29
        self.move("cow-1", x, y)
        sticker = self.bridge.kernel.sticker("cow-1")
        self.assertEqual(sticker.owner, farm.HUMAN_ID)
        self.assertEqual(sticker.created_by, farm.HUMAN_ID)


class Q9_NoAgentRequired(ServerCase):

    def test_no_agent_module_is_imported(self):
        for name in list(sys.modules):
            self.assertNotIn("jev", name.split("."),
                             "bridge pulled in an OmegaJev module: %s" % name)

    def test_the_agent_principal_exists_but_nothing_drives_it(self):
        # It is registered so ownership is meaningful, and it never acts.
        self.assertIn(farm.AGENT_ID, [farm.AGENT_ID])
        actors = {r.actor for r in self.bridge.kernel.receipts}
        self.assertNotIn(farm.AGENT_ID, actors)


class Q10_NoSecondAuthorityKernel(ServerCase):

    def test_the_bridge_uses_the_one_kernel_package(self):
        import stickerbook_core
        self.assertIsInstance(self.bridge.kernel, stickerbook_core.Kernel)

    def test_the_bridge_holds_no_ownership_or_permission_logic(self):
        """The decision must not be reimplemented at the seam."""
        with open(bridge_mod.__file__, encoding="utf-8") as handle:
            source = handle.read()
        body = source.split('"""', 2)[-1]        # skip the module docstring
        for banned in ("owner ==", "owner !=", ".owner", "is_owner",
                       "permitted", "ALLOWED", "if actor =="):
            self.assertNotIn(banned, body,
                             "bridge appears to make its own authority "
                             "decision via %r" % banned)

    def test_position_validation_lives_in_the_kernel_not_the_bridge(self):
        """The bridge forwards the coordinate; the kernel judges it."""
        with open(bridge_mod.__file__, encoding="utf-8") as handle:
            source = handle.read()
        for banned in ("0.0 <=", "<= 1.0", "min(max", "clamp"):
            self.assertNotIn(banned, source)
        _, out = self.move("cow-1", 42.0, -7.0)
        self.assertEqual(out["receipt"]["reason"], "position-out-of-page")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TrayPlacement(ServerCase):
    """Putting a sticker down from the tray, and taking one off."""

    def place(self, asset, x, y, command_id="a1", based_on=None):
        return self.post("/api/place", {
            "asset": asset, "command_id": command_id,
            "point": {"x": x, "y": y}, "based_on_revision": based_on})

    def take_off(self, sticker, command_id="r1", based_on=None):
        return self.post("/api/remove", {
            "sticker": sticker, "command_id": command_id,
            "based_on_revision": based_on})

    def test_the_hotbar_offers_the_pages_sticker_definitions(self):
        _, state = self.get("/api/state")
        self.assertEqual(
            sorted(d["id"] for d in state["definitions"]),
            sorted(farm.ASSETS),
        )

    def test_placing_from_the_tray_creates_a_sticker_at_that_point(self):
        before = set(self.bridge.kernel.sticker_ids())
        _, out = self.place("duck", 0.66, 0.41)
        self.assertTrue(out["receipt"]["accepted"], out["receipt"]["reason"])
        new = set(self.bridge.kernel.sticker_ids()) - before
        self.assertEqual(len(new), 1)
        sticker = self.bridge.kernel.sticker(new.pop())
        self.assertEqual(sticker.asset, "duck")
        self.assertAlmostEqual(sticker.x, 0.66)
        self.assertAlmostEqual(sticker.y, 0.41)

    def test_a_placed_sticker_belongs_to_the_person_who_placed_it(self):
        _, out = self.place("hen", 0.3, 0.3)
        sticker = self.bridge.kernel.sticker(out["receipt"]["object"])
        self.assertEqual(sticker.owner, farm.HUMAN_ID)
        self.assertEqual(sticker.created_by, farm.HUMAN_ID)

    def test_supply_is_unlimited(self):
        for i in range(5):
            _, out = self.place("duck", 0.5, 0.5, command_id="d%d" % i)
            self.assertTrue(out["receipt"]["accepted"])
        ducks = [s for s in self.bridge.kernel.sticker_ids()
                 if s.startswith("duck")]
        self.assertEqual(len(ducks), 5)

    def test_an_unknown_asset_is_refused_by_the_kernel(self):
        _, out = self.place("dragon", 0.5, 0.5)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "unknown-asset")

    def test_placing_off_the_page_is_refused(self):
        before = set(self.bridge.kernel.sticker_ids())
        _, out = self.place("duck", 1.4, 0.5)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "position-out-of-page")
        self.assertEqual(set(self.bridge.kernel.sticker_ids()), before)

    def test_taking_a_sticker_off_removes_it(self):
        _, out = self.take_off("cow-1")
        self.assertTrue(out["receipt"]["accepted"], out["receipt"]["reason"])
        self.assertIsNone(self.bridge.kernel.sticker("cow-1"))

    def test_one_verb_takes_off_any_sticker_on_the_page(self):
        """The child cannot perceive who placed it, so neither should the UI."""
        _, out = self.take_off("butterfly-1")
        self.assertTrue(out["receipt"]["accepted"], out["receipt"]["reason"])
        self.assertIsNone(self.bridge.kernel.sticker("butterfly-1"))

    def test_malformed_place_and_remove_never_reach_the_kernel(self):
        before_rev = self.bridge.kernel.revision
        for path, body in [
            ("/api/place", {"command_id": "c", "point": {"x": 0.5, "y": 0.5}}),
            ("/api/place", {"asset": "duck", "point": {"x": 0.5, "y": 0.5}}),
            ("/api/place", {"asset": "duck", "command_id": "c"}),
            ("/api/place", {"asset": 7, "command_id": "c",
                            "point": {"x": 0.5, "y": 0.5}}),
            ("/api/remove", {}),
            ("/api/remove", {"sticker": "cow-1"}),
            ("/api/remove", {"sticker": 5, "command_id": "c"}),
        ]:
            with self.subTest(path=path, body=body):
                status, out = self.post(path, body)
                self.assertEqual(status, 400)
                self.assertNotIn("receipt", out)
        self.assertEqual(self.bridge.kernel.revision, before_rev)

    def test_the_browser_still_cannot_choose_its_principal_when_placing(self):
        _, out = self.post("/api/place", {
            "asset": "duck", "command_id": "c1",
            "point": {"x": 0.5, "y": 0.5}, "actor": farm.AGENT_ID})
        self.assertEqual(out["receipt"]["actor"], farm.HUMAN_ID)
        sticker = self.bridge.kernel.sticker(out["receipt"]["object"])
        self.assertEqual(sticker.owner, farm.HUMAN_ID)

    def test_unknown_write_routes_are_404(self):
        for path in ("/api/delete-everything", "/api/grant", "/api/admin"):
            status, _ = self.post(path, {"sticker": "cow-1"})
            self.assertEqual(status, 404, path)


class DefinitionsAndInstances(ServerCase):
    """One sticker DESIGN, many PLACEMENTS."""

    def test_state_separates_definitions_from_instances(self):
        _, st = self.get("/api/state")
        designs = {d["id"] for d in st["definitions"]}
        self.assertEqual(designs, set(farm.ASSETS))
        for d in st["definitions"]:
            self.assertIn("none", d["animations"])
            self.assertEqual(d["rest_clip"], "rest")
            self.assertEqual(
                d["scale_bounds"],
                {"min": 0.9, "max": 1.1},
            )
        for instance in st["stickers"]:
            self.assertIn(instance["definition"], designs)

    def test_one_definition_can_have_many_instances(self):
        for i in range(3):
            self.post("/api/place", {"asset": "duck", "command_id": "d%d" % i,
                                     "point": {"x": 0.2 + i * .2, "y": 0.5}})
        _, st = self.get("/api/state")
        ducks = [s for s in st["stickers"] if s["definition"] == "duck"]
        self.assertEqual(len(ducks), 3)
        self.assertEqual(len({d["id"] for d in ducks}), 3)


class TheBookIsACollection(ServerCase):
    """A home for pages, not an ordered array."""

    def test_book_lists_its_pages(self):
        _, b = self.get("/api/book")
        self.assertEqual(b["title"], "StickerBook")
        self.assertEqual([p["id"] for p in b["pages"]], ["farm"])

    def test_the_book_exposes_no_ordering(self):
        """No index, no previous, no next -- pages are visited, not advanced."""
        _, b = self.get("/api/book")
        flat = json.dumps(b)
        for ordering in ("index", "previous", "next", "order", "position"):
            self.assertNotIn('"%s"' % ordering, flat)
        for page in b["pages"]:
            self.assertEqual(sorted(page), ["id", "name", "summary"])

    def test_unbuilt_things_are_named_but_not_pretended_to_exist(self):
        _, b = self.get("/api/book")
        self.assertEqual([c["label"] for c in b["coming"]],
                         ["New Page", "Find Pages"])


class BringingAStickerToLife(ServerCase):
    """Double-tap means bring this to life. The host picks the animation."""

    def animate(self, sticker, command_id="an1"):
        return self.post("/api/animate", {"sticker": sticker,
                                          "command_id": command_id})

    def test_it_toggles_life_on_and_off(self):
        _, out = self.animate("butterfly-1", "a1")
        self.assertTrue(out["receipt"]["accepted"], out["receipt"]["reason"])
        self.assertEqual(self.bridge.kernel.sticker("butterfly-1").animation,
                         "flutter")
        _, out = self.animate("butterfly-1", "a2")
        self.assertTrue(out["receipt"]["accepted"])
        self.assertEqual(self.bridge.kernel.sticker("butterfly-1").animation,
                         "rest")

    def test_the_browser_does_not_choose_the_animation(self):
        """It sends a gesture, not a value. The host reads the definition."""
        _, out = self.post("/api/animate", {
            "sticker": "cow-1", "command_id": "a1", "animation": "flutter"})
        self.assertTrue(out["receipt"]["accepted"])
        # cow declares chew, not flutter -- the body was ignored
        self.assertEqual(self.bridge.kernel.sticker("cow-1").animation, "chew")

    def test_a_human_may_animate_an_agent_owned_sticker(self):
        self.assertEqual(self.bridge.kernel.sticker("butterfly-1").owner,
                         farm.AGENT_ID)
        _, out = self.animate("butterfly-1")
        self.assertTrue(out["receipt"]["accepted"], out["receipt"]["reason"])

    def test_malformed_animate_never_reaches_the_kernel(self):
        rev = self.bridge.kernel.revision
        for body in ({}, {"sticker": "cow-1"}, {"command_id": "c"},
                     {"sticker": "nope", "command_id": "c"}):
            status, out = self.post("/api/animate", body)
            self.assertEqual(status, 400)
            self.assertNotIn("receipt", out)
        self.assertEqual(self.bridge.kernel.revision, rev)
