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
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402


class ServerCase(unittest.TestCase):
    """A fresh farm and a fresh server per test."""

    def setUp(self):
        self.httpd, self.bridge = bridge_mod.serve("127.0.0.1", 0, quiet=True)
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

    def move(self, sticker, x, y, command_id="c1", based_on=None):
        return self.post("/api/propose-move", {
            "sticker": sticker, "command_id": command_id,
            "point": {"x": x, "y": y}, "based_on_revision": based_on})

    def slot_of(self, sticker_id):
        return self.bridge.kernel.sticker(sticker_id).anchor


class Q1_BrowserCanDisplayKernelState(ServerCase):

    def test_state_is_served_and_kernel_backed(self):
        status, state = self.get("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(state["revision"], self.bridge.kernel.revision)
        ids = sorted(s["id"] for s in state["stickers"])
        self.assertEqual(ids, ["butterfly-1", "cow-1"])

    def test_page_and_assets_are_served(self):
        for path, needle in (("/", b"StickerBook"),
                             ("/static/app.js", b"proposeMove"),
                             ("/static/style.css", b".sticker")):
            with urllib.request.urlopen(self.url(path), timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(needle, r.read())

    def test_each_sticker_carries_a_render_position_from_its_slot(self):
        _, state = self.get("/api/state")
        for s in state["stickers"]:
            self.assertIn(s["slot"], farm.SLOTS)
            self.assertAlmostEqual(s["x"], farm.SLOTS[s["slot"]][0])
            self.assertAlmostEqual(s["y"], farm.SLOTS[s["slot"]][1])


class Q2_HumanCanMoveAStickerThroughTheKernel(ServerCase):

    def test_dragging_the_cow_moves_it(self):
        before = self.slot_of("cow-1")
        x, y = farm.SLOTS["by-the-pond"]
        status, body = self.move("cow-1", x, y)
        self.assertEqual(status, 200)
        self.assertTrue(body["receipt"]["accepted"], body["receipt"])
        self.assertEqual(body["snapped_to"], "by-the-pond")
        self.assertEqual(self.slot_of("cow-1"), "by-the-pond")
        self.assertNotEqual(before, "by-the-pond")


class Q3_EveryMutationPassesTheAuthorityGate(ServerCase):

    def test_the_browser_cannot_choose_its_own_principal(self):
        # Claim to be the agent, the operator, anyone. It is ignored.
        x, y = farm.SLOTS["by-the-pond"]
        for claimed in (farm.AGENT_ID, "operator", "root", None):
            body = {"sticker": "butterfly-1", "command_id": "c-%s" % claimed,
                    "point": {"x": x, "y": y}, "actor": claimed,
                    "principal": claimed, "owner": claimed}
            status, out = self.post("/api/propose-move", body)
            self.assertEqual(out["receipt"]["actor"], farm.HUMAN_ID)
            self.assertFalse(out["receipt"]["accepted"])
            self.assertEqual(out["receipt"]["reason"], "not-owner")

    def test_the_browser_cannot_name_a_slot(self):
        # A slot field is not part of the protocol; the host snaps a point.
        x, y = farm.SLOTS["by-the-barn"]
        status, out = self.post("/api/propose-move", {
            "sticker": "cow-1", "command_id": "c1",
            "point": {"x": x, "y": y},
            "anchor": "somewhere-else", "slot": "somewhere-else"})
        self.assertEqual(out["snapped_to"], "by-the-barn")
        self.assertEqual(self.slot_of("cow-1"), "by-the-barn")

    def test_the_browser_cannot_choose_the_action(self):
        # This endpoint performs exactly one kind of command.
        x, y = farm.SLOTS["by-the-pond"]
        _, out = self.post("/api/propose-move", {
            "sticker": "cow-1", "command_id": "c1", "point": {"x": x, "y": y},
            "action": "remove-own-sticker"})
        self.assertEqual(out["receipt"]["action"], "move-own-sticker")
        self.assertIsNotNone(self.bridge.kernel.sticker("cow-1"))

    def test_unknown_sticker_is_refused_by_the_kernel(self):
        x, y = farm.SLOTS["by-the-pond"]
        _, out = self.move("no-such-sticker", x, y)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "unknown-object")


class Q4_AcceptedOperationsProduceReceipts(ServerCase):

    def test_receipt_carries_full_provenance_and_bumps_revision(self):
        before = self.bridge.kernel.revision
        x, y = farm.SLOTS["in-the-field"]
        _, out = self.move("cow-1", x, y, command_id="cmd-7")
        r = out["receipt"]
        self.assertEqual(r["commandId"], "cmd-7")
        self.assertEqual(r["actor"], farm.HUMAN_ID)
        self.assertEqual(r["action"], "move-own-sticker")
        self.assertEqual(r["object"], "cow-1")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["reason"], "ok")
        self.assertGreater(r["resultRevision"], before)
        self.assertEqual(out["state"]["revision"], r["resultRevision"])

    def test_receipts_endpoint_lists_both_outcomes(self):
        x, y = farm.SLOTS["by-the-pond"]
        self.move("cow-1", x, y, command_id="ok-1")
        self.move("butterfly-1", x, y, command_id="no-1")
        _, body = self.get("/api/receipts")
        outcomes = {r["object"]: r["accepted"] for r in body["receipts"]}
        self.assertTrue(outcomes["cow-1"])
        self.assertFalse(outcomes["butterfly-1"])


class Q5_RejectedOperationsChangeNothing(ServerCase):

    def test_moving_an_agent_owned_sticker_is_refused(self):
        before_slot = self.slot_of("butterfly-1")
        before_rev = self.bridge.kernel.revision
        x, y = farm.SLOTS["by-the-pond"]
        _, out = self.move("butterfly-1", x, y)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "not-owner")
        self.assertEqual(self.slot_of("butterfly-1"), before_slot)
        self.assertEqual(self.bridge.kernel.revision, before_rev)

    def test_malformed_proposals_never_reach_the_kernel(self):
        before_rev = self.bridge.kernel.revision
        before = json.dumps(self.bridge.state()["stickers"], sort_keys=True)
        bad_bodies = [
            {}, {"sticker": "cow-1"}, {"command_id": "c"},
            {"sticker": "cow-1", "command_id": "c"},
            {"sticker": "cow-1", "command_id": "c", "point": "nope"},
            {"sticker": "cow-1", "command_id": "c", "point": {"x": "a", "y": 1}},
            {"sticker": "cow-1", "command_id": "c",
             "point": {"x": float("nan"), "y": 0.5}},
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

    def test_non_json_body_is_refused(self):
        status, out = self.post("/api/propose-move", None, raw=b"<not json>")
        self.assertEqual(status, 400)
        self.assertFalse(out["ok"])

    def test_stale_revision_is_refused(self):
        x, y = farm.SLOTS["by-the-pond"]
        self.move("cow-1", x, y, command_id="first")
        stale = 0
        bx, by = farm.SLOTS["by-the-barn"]
        _, out = self.move("cow-1", bx, by, command_id="second", based_on=stale)
        self.assertFalse(out["receipt"]["accepted"])
        self.assertEqual(out["receipt"]["reason"], "stale-revision")
        self.assertEqual(self.slot_of("cow-1"), "by-the-pond")

    def test_replayed_command_id_does_not_move_twice(self):
        x, y = farm.SLOTS["by-the-pond"]
        _, first = self.move("cow-1", x, y, command_id="same")
        rev = self.bridge.kernel.revision
        bx, by = farm.SLOTS["by-the-barn"]
        _, second = self.move("cow-1", bx, by, command_id="same")
        self.assertTrue(second["receipt"]["replayed"])
        self.assertEqual(self.bridge.kernel.revision, rev)
        self.assertEqual(self.slot_of("cow-1"), "by-the-pond")


class Q6_RendererFollowsAuthoritativeState(ServerCase):

    def test_every_response_carries_authoritative_state(self):
        x, y = farm.SLOTS["by-the-pond"]
        for sticker in ("cow-1", "butterfly-1"):
            _, out = self.move(sticker, x, y, command_id="c-" + sticker)
            self.assertIn("state", out)
            self.assertEqual(out["state"]["revision"],
                             self.bridge.kernel.revision)

    def test_refused_move_returns_the_unchanged_position(self):
        x, y = farm.SLOTS["by-the-pond"]
        _, out = self.move("butterfly-1", x, y)
        drawn = {s["id"]: s["slot"] for s in out["state"]["stickers"]}
        self.assertEqual(drawn["butterfly-1"], "under-the-tree")

    def test_malformed_response_still_carries_state_to_redraw_from(self):
        _, out = self.post("/api/propose-move", {"sticker": "cow-1"})
        self.assertIn("state", out)


class Q7_BackdropIsPassiveScenery(ServerCase):

    def test_backdrop_features_are_not_kernel_objects(self):
        for feature in ("barn", "pond", "tree", "fence"):
            self.assertIsNone(self.bridge.kernel.sticker(feature))

    def test_backdrop_features_cannot_be_moved(self):
        x, y = farm.SLOTS["by-the-pond"]
        for feature in ("barn", "pond", "tree", "fence"):
            _, out = self.move(feature, x, y, command_id="c-" + feature)
            self.assertFalse(out["receipt"]["accepted"])
            self.assertEqual(out["receipt"]["reason"], "unknown-object")

    def test_backdrop_is_present_for_rendering_only(self):
        _, state = self.get("/api/state")
        drawn = {f["id"] for f in state["backdrop"]["features"]}
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
        x, y = farm.SLOTS["by-the-pond"]
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

    def test_slot_snapping_is_total_and_closed(self):
        for point in [(-99, -99), (99, 99), (0.5, 0.5), (0, 1), (1, 0)]:
            self.assertIn(farm.snap_to_slot(*point), farm.SLOTS)
        for bad in [("a", 0.5), (None, 0.5), (float("nan"), 0.5)]:
            with self.assertRaises(ValueError):
                farm.snap_to_slot(*bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
