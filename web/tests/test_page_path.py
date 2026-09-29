"""Observed bare-page paths and cross-kind episode chronology."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge  # noqa: E402
import farm  # noqa: E402
import page_path  # noqa: E402
from test_interaction import FakeOmegaLLM, FakeOmegaJev  # noqa: E402
from stickerbook_core import StickerInstance  # noqa: E402


def path(points, duration=900):
    last = len(points) - 1
    return {"duration_ms": duration, "samples": [
        {"t": index / last, "x": x, "y": y}
        for index, (x, y) in enumerate(points)]}


class PagePathCapture(unittest.TestCase):
    def setUp(self):
        self.kernel = farm.build_world()
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge.Bridge(self.kernel, agent_runtime=self.llm,
                                    jev_runtime=self.jev)

    def observe(self, points=None, **extra):
        body = path(points or [(0.2, 0.3), (0.5, 0.1), (0.8, 0.4)])
        body.update(extra)
        return self.bridge.observe_page_path(body)

    def test_background_path_is_observed_only(self):
        before = self.kernel.revision
        receipts = len(self.bridge.receipts(limit=100))
        result = self.observe()
        self.assertTrue(result["ok"])
        trace = self.bridge.page_paths.get("path-1")
        self.assertEqual(trace.kind, "page-path")
        self.assertEqual(trace.principal, farm.HUMAN_ID)
        self.assertEqual(trace.page, "farm")
        self.assertEqual(trace.scene_revision_at_recording, before)
        self.assertEqual((trace.samples[0].x, trace.samples[-1].x),
                         (0.2, 0.8))
        self.assertEqual(self.kernel.revision, before)
        self.assertEqual(len(self.bridge.receipts(limit=100)), receipts)

    def test_multi_bend_and_return_retain_observations(self):
        points = [(0.3, 0.4), (0.5, 0.1), (0.8, 0.4),
                  (0.5, 0.8), (0.3, 0.4)]
        self.observe(points)
        samples = self.bridge.page_paths.get("path-1").samples
        self.assertEqual((samples[0].x, samples[0].y),
                         (samples[-1].x, samples[-1].y))
        self.assertGreater(max(s.x for s in samples), 0.7)
        self.assertLess(min(s.y for s in samples), 0.2)
        self.assertGreater(max(s.y for s in samples), 0.7)

    def test_decimation_keeps_endpoints_and_major_bends(self):
        points = [(0.1 + 0.7 * i / 178, 0.5) for i in range(179)]
        points[90] = (0.45, 0.1)
        points[91] = (0.46, 0.9)
        samples = page_path.decimate([
            page_path.PathSample(index / 178, x, y)
            for index, (x, y) in enumerate(points)])
        self.assertLessEqual(len(samples), page_path.MAX_SAMPLES)
        self.assertEqual(samples[0].x, points[0][0])
        self.assertAlmostEqual(samples[-1].x, points[-1][0])
        self.assertLess(min(s.y for s in samples), 0.2)
        self.assertGreater(max(s.y for s in samples), 0.8)

    def test_malformed_telemetry_is_discarded(self):
        before = self.kernel.revision
        bad = [
            {"samples": [], "duration_ms": 900},
            path([(0.2, 0.3), (0.5, 0.1)], duration=20001),
            path([(0.2, 0.3), (float("nan"), 0.1)]),
            dict(path([(0.2, 0.3), (0.5, 0.1)]), principal="operator"),
            path([(0.2, 0.3)] * (page_path.MAX_INPUT_SAMPLES + 1)),
            {"duration_ms": 900, "samples": [
                {"t": 0.8, "x": 0.2, "y": 0.3},
                {"t": 0.2, "x": 0.5, "y": 0.1}]},
        ]
        for body in bad:
            with self.subTest(body=str(body)[:60]):
                self.assertFalse(self.bridge.observe_page_path(body)["ok"])
        self.assertEqual(len(self.bridge.page_paths), 0)
        self.assertEqual(self.bridge.observed_inputs.after(0), ())
        self.assertEqual(self.kernel.revision, before)

    def test_bad_observation_does_not_block_box_conversation(self):
        bad = {"duration_ms": 900, "samples": [
            {"t": 0, "x": "bad", "y": .2},
            {"t": 1, "x": .5, "y": .3}]}
        self.assertFalse(self.bridge.observe_page_path(bad)["ok"])
        result = self.bridge.converse({"text": "over there", "reference": {
            "kind": "box", "box": {
                "x1": .2, "y1": .2, "x2": .5, "y2": .3}}})
        self.assertTrue(result["ok"])
        self.assertEqual(result["interaction"]["deicticReference"]["kind"],
                         "box")
        self.assertEqual(result["interaction"]["signals"], [])

    def test_transport_ceiling(self):
        body = path([(round(i / 63, 4), round(1 - i / 63, 4))
                     for i in range(64)])
        self.assertLess(len(json.dumps(body).encode()), bridge.MAX_BODY_BYTES)

    def test_box_and_path_are_distinct_evidence(self):
        self.observe()
        reference = {"kind": "box", "box": {
            "x1": 0.2, "y1": 0.1, "x2": 0.8, "y2": 0.4}}
        result = self.bridge.converse({"text": "like this", "reference": reference,
                                       "input_mode": "voice"})
        self.assertTrue(result["ok"])
        episode = result["interaction"]
        self.assertEqual(episode["deicticReference"]["kind"], "box")
        self.assertEqual(episode["signals"], [{
            "kind": "page-path", "ref": "path-1", "subject": None,
            "durationMs": 900, "sourceEvent": "input-event-1"}])
        self.assertEqual(self.llm.scenes[-1]["interaction"], episode)
        self.assertNotIn("samples", json.dumps(self.llm.scenes[-1]))
        self.assertEqual(len(self.bridge.page_paths.get("path-1").samples), 3)
        self.assertEqual(self.bridge.converse({"text": "again"})[
            "interaction"]["signals"], [])

    def test_browser_cannot_splice_or_reorder_history(self):
        self.observe()
        self.bridge.converse({"text": "first"})
        result = self.bridge.converse({
            "text": "second", "paths": ["path-1"], "principal": "operator",
            "signals": [{"kind": "page-path", "ref": "path-999"}]})
        self.assertEqual(result["interaction"]["signals"], [])
        self.assertEqual(self.bridge.interactions.latest().principal,
                         farm.HUMAN_ID)

    def test_cross_kind_host_chronology(self):
        self.kernel.place_sticker(StickerInstance(
            "frog-1", farm.HUMAN_ID, farm.HUMAN_ID, "frog", 1,
            x=0.3, y=0.4, animation="rest"))

        def drag(command, target):
            return self.bridge.propose_move({
                "sticker": "frog-1", "command_id": command,
                "point": {"x": target, "y": 0.4},
                "drag": path([(0.3, 0.4), (target, 0.4)]),
            })

        self.assertTrue(drag("first", 0.4)["receipt"]["accepted"])
        self.observe()
        self.assertTrue(drag("second", 0.5)["receipt"]["accepted"])
        episode = self.bridge.converse({
            "text": "Make Froggy go like this", "input_mode": "voice"})[
                "interaction"]
        self.assertEqual([(s["kind"], s["ref"]) for s in episode["signals"]],
                         [("sticker-drag", "drag-1"),
                          ("page-path", "path-1"),
                          ("sticker-drag", "drag-2")])
        self.assertEqual(episode["inputMode"], "voice")
        self.assertNotIn("samples", json.dumps(self.llm.scenes[-1]))

    def test_bounded_cross_kind_subset(self):
        for index in range(6):
            self.observe()
        signals = self.bridge.converse({"text": "recent"})[
            "interaction"]["signals"]
        self.assertEqual([s["ref"] for s in signals],
                         ["path-3", "path-4", "path-5", "path-6"])

    def test_evicted_observation_marker_remains_deterministic(self):
        self.observe()
        self.bridge.converse({"text": "first"})
        for _ in range(70):
            self.observe()
        self.assertEqual(len(self.bridge.page_paths.traces()), 32)
        self.assertEqual(len(self.bridge.observed_inputs.after(0)), 64)
        signals = self.bridge.converse({"text": "recent"})[
            "interaction"]["signals"]
        self.assertEqual([s["ref"] for s in signals],
                         ["path-68", "path-69", "path-70", "path-71"])

    def test_double_click_still_bypasses_omegallm(self):
        result = self.bridge.animate({"sticker": "cow-1",
                                      "command_id": "double-click"})
        self.assertTrue(result["ok"])
        self.assertEqual(self.llm.scenes, [])


class BrowserBackgroundCapture(unittest.TestCase):
    def test_existing_box_gesture_also_sends_observed_path(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "static",
                               "app.js"), encoding="utf-8") as handle:
            source = handle.read()
        functions = source[source.index("function startDeicticGesture("):
                           source.index("async function tapSticker(")]
        harness = r"""
let pendingDefinition = null;
let stickerOverlay = {hidden: true};
let screens = {play: {hidden: false}};
let deicticGesture = null;
let deicticReferenceSerial = 0;
let pendingDeicticReference = null;
let pendingPathObservation = Promise.resolve();
let sent = [];
let reference = null;
let tick = 0;
let performance = {now: () => ++tick * 100};
let svg = {setPointerCapture() {}, releasePointerCapture() {}};
let kernelWorld = {observePagePath: async (body) => {
  sent.push(body); return {ok: true, sourceEvent: "input-event-1"};
}};
let world = kernelWorld;
let copy = (value) => JSON.parse(JSON.stringify(value));
let overPage = () => true;
let pageFraction = (event) => event.point;
let drawDeicticReference = () => {};
let setDeicticReference = (value) => {
  reference = value; pendingDeicticReference = value;
  deicticReferenceSerial += 1;
};
"""
        tail = r"""
const event = (x, y, cx, cy) => ({pointerId: 1, button: 0,
  point: {x, y}, clientX: cx, clientY: cy, preventDefault() {}});
startDeicticGesture(event(.2, .3, 20, 30));
updateDeicticGesture(event(.4, .1, 40, 10));
updateDeicticGesture(event(.6, .6, 60, 60));
finishDeicticGesture(event(.8, .4, 80, 40));
pendingPathObservation.then(() => console.log(JSON.stringify({reference, sent})));
"""
        output = subprocess.run(["node", "-e", harness + functions + tail],
                                capture_output=True, text=True, check=True)
        result = json.loads(output.stdout)
        self.assertEqual(result["reference"], {"kind": "box", "box": {
            "x1": .2, "y1": .3, "x2": .8, "y2": .4},
            "sourceEvent": "input-event-1"})
        self.assertEqual(len(result["sent"]), 1)
        samples = result["sent"][0]["samples"]
        self.assertEqual((samples[0]["x"], samples[-1]["x"]), (.2, .8))
        self.assertIn(.6, [s["y"] for s in samples])


if __name__ == "__main__":
    unittest.main()
