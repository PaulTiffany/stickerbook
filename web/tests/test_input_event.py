"""Host-issued co-origin for a box and its observed bare-page path."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge  # noqa: E402
import farm  # noqa: E402
from test_interaction import FakeOmegaLLM, FakeOmegaJev  # noqa: E402


def path(start=(.2, .3), end=(.8, .4), duration=850):
    return {"duration_ms": duration, "box": {
        "x1": min(start[0], end[0]), "y1": min(start[1], end[1]),
        "x2": max(start[0], end[0]), "y2": max(start[1], end[1])},
        "samples": [
        {"t": 0, "x": start[0], "y": start[1]},
        {"t": .5, "x": .5, "y": .1},
        {"t": 1, "x": end[0], "y": end[1]},
    ]}


def box(start=(.2, .3), end=(.8, .4), source_event=None):
    reference = {"kind": "box", "box": {
        "x1": min(start[0], end[0]), "y1": min(start[1], end[1]),
        "x2": max(start[0], end[0]), "y2": max(start[1], end[1])}}
    if source_event is not None:
        reference["source_event"] = source_event
    return reference


class InputEventProvenance(unittest.TestCase):
    def setUp(self):
        self.kernel = farm.build_world()
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge.Bridge(self.kernel, agent_runtime=self.llm,
                                    jev_runtime=self.jev)

    def test_one_box_and_path_share_host_event(self):
        revision = self.kernel.revision
        receipts = len(self.bridge.receipts(limit=100))
        observed = self.bridge.observe_page_path(path())
        self.assertEqual(observed["sourceEvent"], "input-event-1")
        result = self.bridge.converse({
            "text": "like this", "input_mode": "voice",
            "reference": box(source_event=observed["sourceEvent"])})
        episode = result["interaction"]
        self.assertEqual(episode["deicticReference"]["sourceEvent"],
                         "input-event-1")
        self.assertEqual(set(episode["deicticReference"]),
                         {"kind", "page", "box", "sourceEvent"})
        self.assertEqual(episode["signals"], [{
            "kind": "page-path", "ref": "path-1", "subject": None,
            "durationMs": 850, "sourceEvent": "input-event-1"}])
        self.assertEqual(self.llm.scenes[-1]["interaction"], episode)
        self.assertNotIn("samples", json.dumps(self.llm.scenes[-1]))
        self.assertEqual(self.kernel.revision, revision)
        self.assertEqual(len(self.bridge.receipts(limit=100)), receipts)

    def test_two_gestures_link_pending_box_to_second_path(self):
        first = self.bridge.observe_page_path(path())
        second = self.bridge.observe_page_path(path((.1, .2), (.7, .6)))
        self.assertNotEqual(first["sourceEvent"], second["sourceEvent"])
        episode = self.bridge.converse({
            "text": "Make the bird go like this", "input_mode": "voice",
            "reference": box((.1, .2), (.7, .6),
                             second["sourceEvent"])})["interaction"]
        self.assertEqual([s["sourceEvent"] for s in episode["signals"]],
                         ["input-event-1", "input-event-2"])
        self.assertEqual(episode["deicticReference"]["sourceEvent"],
                         "input-event-2")
        self.assertEqual([s["ref"] for s in episode["signals"]],
                         ["path-1", "path-2"])

    def test_old_forged_and_geometry_mismatched_claims_do_not_link(self):
        first = self.bridge.observe_page_path(path())
        self.bridge.observe_page_path(path((.1, .2), (.7, .6)))
        for claim in (first["sourceEvent"], "input-event-999"):
            with self.subTest(claim=claim):
                reference = self.bridge._deictic_reference(box(
                    (.1, .2), (.7, .6), claim))
                self.assertNotIn("sourceEvent", reference)
        reference = self.bridge._deictic_reference(box(
            (.3, .3), (.7, .6), "input-event-2"))
        self.assertNotIn("sourceEvent", reference)

    def test_auxiliary_capture_rejects_box_path_mismatch(self):
        body = path()
        body["box"]["x1"] = .4
        self.assertFalse(self.bridge.observe_page_path(body)["ok"])
        self.assertEqual(len(self.bridge.page_paths), 0)
        self.assertEqual(self.bridge.observed_inputs.after(0), ())

    def test_consumed_event_cannot_be_spliced_into_next_turn(self):
        observed = self.bridge.observe_page_path(path())
        self.bridge.converse({"text": "first"})
        episode = self.bridge.converse({
            "text": "again",
            "reference": box(source_event=observed["sourceEvent"])})[
                "interaction"]
        self.assertNotIn("sourceEvent", episode["deicticReference"])
        self.assertEqual(episode["signals"], [])

    def test_bad_path_keeps_box_without_fabricated_link(self):
        observed = self.bridge.observe_page_path({
            "duration_ms": 850, "samples": [{"t": 0, "x": "bad", "y": .3}]})
        self.assertFalse(observed["ok"])
        episode = self.bridge.converse({
            "text": "there", "reference": box()})["interaction"]
        self.assertEqual(episode["deicticReference"]["kind"], "box")
        self.assertNotIn("sourceEvent", episode["deicticReference"])
        self.assertEqual(episode["signals"], [])

    def test_point_and_direct_jev_route_are_unchanged(self):
        episode = self.bridge.converse({"text": "there", "reference": {
            "kind": "point", "point": {"x": .2, "y": .3},
            "source_event": "input-event-999"}})["interaction"]
        self.assertNotIn("sourceEvent", episode["deicticReference"])
        before = len(self.llm.scenes)
        self.assertTrue(self.bridge.animate({
            "sticker": "cow-1", "command_id": "double-click"})["ok"])
        self.assertEqual(len(self.llm.scenes), before)


class BrowserCorrelation(unittest.TestCase):
    def test_two_background_drags_only_current_box_gets_current_event(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "static",
                               "app.js"), encoding="utf-8") as handle:
            source = handle.read()
        functions = source[source.index("function startDeicticGesture("):
                           source.index("async function tapSticker(")]
        payload = source[source.index("function deicticPayload("):
                         source.index("function drawDeicticReference(")]
        harness = r"""
let pendingDefinition = null;
let stickerOverlay = {hidden: true};
let screens = {play: {hidden: false}};
let deicticGesture = null;
let deicticReferenceSerial = 0;
let pendingDeicticReference = null;
let pendingPathObservation = Promise.resolve();
let tick = 0;
let issued = 0;
let captures = [];
let performance = {now: () => ++tick * 100};
let svg = {setPointerCapture() {}, releasePointerCapture() {}};
let kernelWorld = {observePagePath: async (body) => {
  captures.push(body);
  return {ok: true, sourceEvent: "input-event-" + (++issued)};
}};
let world = kernelWorld;
let overPage = () => true;
let pageFraction = (event) => event.point;
let drawDeicticReference = () => {};
let copy = (value) => JSON.parse(JSON.stringify(value));
let setDeicticReference = (value) => {
  pendingDeicticReference = value;
  deicticReferenceSerial += 1;
};
"""
        tail = r"""
const event = (x, y, cx, cy) => ({pointerId: 1, button: 0,
  point: {x, y}, clientX: cx, clientY: cy, preventDefault() {}});
function drag(x1, y1, x2, y2) {
  startDeicticGesture(event(x1, y1, 20, 30));
  finishDeicticGesture(event(x2, y2, 80, 70));
}
drag(.2, .3, .8, .4);
drag(.1, .2, .7, .6);
pendingPathObservation.then(async () => {
  const reference = deicticPayload(pendingDeicticReference);
  kernelWorld.observePagePath = async () => ({ok: false});
  drag(.3, .2, .8, .7);
  await pendingPathObservation;
  console.log(JSON.stringify({
    issued, captures, reference,
    failed: deicticPayload(pendingDeicticReference)}));
});
"""
        output = subprocess.run(
            ["node", "-e", harness + payload + functions + tail],
            capture_output=True, text=True, check=True)
        result = json.loads(output.stdout)
        self.assertEqual(result["issued"], 2)
        self.assertEqual(result["captures"][0]["box"], {
            "x1": .2, "y1": .3, "x2": .8, "y2": .4})
        self.assertEqual(result["captures"][1]["box"], {
            "x1": .1, "y1": .2, "x2": .7, "y2": .6})
        self.assertEqual(result["reference"]["source_event"],
                         "input-event-2")
        self.assertEqual(result["reference"]["box"], {
            "x1": .1, "y1": .2, "x2": .7, "y2": .6})
        self.assertNotIn("source_event", result["failed"])
        self.assertEqual(result["failed"]["box"], {
            "x1": .3, "y1": .2, "x2": .8, "y2": .7})


if __name__ == "__main__":
    unittest.main()
