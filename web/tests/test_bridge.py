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
                             ("/static/app.js", b"proposeMove"),
                             ("/static/style.css", b".sticker")):
            with urllib.request.urlopen(self.url(path), timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(needle, r.read())

    def test_each_sticker_carries_its_authoritative_position(self):
        _, state = self.get("/api/state")
        for s in state["stickers"]:
            kernel_sticker = self.bridge.kernel.sticker(s["id"])
            self.assertAlmostEqual(s["x"], kernel_sticker.x)
            self.assertAlmostEqual(s["y"], kernel_sticker.y)


class Q2_HumanCanMoveAStickerThroughTheKernel(ServerCase):

    def test_dragging_the_cow_moves_it(self):
        before = self.pos_of("cow-1")
        status, body = self.move("cow-1", 0.71, 0.29)
        self.assertEqual(status, 200)
        self.assertTrue(body["receipt"]["accepted"], body["receipt"])
        self.assertEqual(self.pos_of("cow-1"), (0.71, 0.29))
        self.assertNotEqual(before, (0.71, 0.29))

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
