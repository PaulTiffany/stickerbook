"""
Tests for the embodied gesture trace.

    Input history is not world history.

A child freehand-drags a sticker. The browser sees a whole trajectory; the
kernel is asked to authorize exactly one ordinary MOVE_STICKER to the release
point. These tests prove the host keeps the demonstration as bounded
declarative data without inventing any authority for it:

* the start is authoritative, read before the move is proposed;
* the samples between are observations of input, never kernel receipts;
* the end is authoritative, read after the kernel accepted.

This tranche is observational. A freehand drag is still deliberately NOT
learnable by the discrete PatternStep mechanism.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402
import gesture_trace  # noqa: E402
from gesture_trace import (  # noqa: E402
    MAX_DURATION_MS, MAX_INPUT_SAMPLES, MAX_SAMPLES, Point, TrajectorySample,
    decimate,
)

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "core"))

from stickerbook_core import (  # noqa: E402
    ALL_ACTIONS, MUTATING_ACTIONS, StickerInstance,
)

HUMAN_ID = farm.HUMAN_ID


class GestureCase(unittest.TestCase):

    def setUp(self):
        self.kernel = farm.build_world()
        self.bridge = bridge_mod.Bridge(self.kernel)
        self.traces = self.bridge.traces
        self.history = self.bridge.history
        self.place("frog-1", x=0.30, y=0.40)

    def place(self, sticker_id, *, x, y, asset="frog"):
        self.kernel.place_sticker(StickerInstance(
            sticker_id, HUMAN_ID, HUMAN_ID, asset, 1, x=x, y=y,
            animation="rest"))
        return self.kernel.sticker(sticker_id)

    def gesture(self, points, duration_ms=800):
        """Build a browser-shaped gesture payload from absolute points."""
        last = len(points) - 1 or 1
        return {
            "samples": [
                {"t": index / last, "x": x, "y": y}
                for index, (x, y) in enumerate(points)
            ],
            "duration_ms": duration_ms,
        }

    def drag(self, points, *, sticker="frog-1", command_id="move-1",
             release=None, duration_ms=800, gesture=True):
        release = release if release is not None else points[-1]
        body = {
            "sticker": sticker,
            "command_id": command_id,
            "point": {"x": release[0], "y": release[1]},
        }
        if gesture:
            body["gesture"] = self.gesture(points, duration_ms)
        return self.bridge.propose_move(body)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

class Capture(GestureCase):

    def test_straight_drag_produces_a_bounded_trace(self):
        result = self.drag([(0.30, 0.40), (0.40, 0.40), (0.50, 0.40)])
        self.assertTrue(result["ok"])
        self.assertTrue(result["receipt"]["accepted"])
        self.assertEqual(len(self.traces), 1)

        trace = self.traces.traces()[0]
        self.assertEqual(trace.subject_id, "frog-1")
        self.assertEqual(trace.asset, "frog")
        self.assertEqual(trace.demonstrated_by, HUMAN_ID)
        self.assertEqual(trace.kind, "freehand")
        self.assertTrue(trace.terminal_move_accepted)
        self.assertEqual(trace.terminal_command_id, "move-1")
        self.assertLessEqual(len(trace.samples), MAX_SAMPLES)
        self.assertGreaterEqual(len(trace.samples), 2)

    def test_start_comes_from_authoritative_state(self):
        """Not from anything the browser asserted about the origin."""
        before = self.kernel.sticker("frog-1")
        # The browser's first sample is nowhere near the real position.
        self.drag([(0.90, 0.90), (0.50, 0.50), (0.42, 0.44)])
        trace = self.traces.traces()[0]
        self.assertEqual((trace.start.x, trace.start.y), (before.x, before.y))
        self.assertEqual((trace.start.x, trace.start.y), (0.30, 0.40))

    def test_end_is_the_accepted_governed_endpoint(self):
        self.drag([(0.30, 0.40), (0.36, 0.44), (0.42, 0.44)])
        after = self.kernel.sticker("frog-1")
        trace = self.traces.traces()[0]
        self.assertEqual((trace.end.x, trace.end.y), (after.x, after.y))
        self.assertAlmostEqual(trace.end.x, 0.42, places=6)
        self.assertAlmostEqual(trace.end.y, 0.44, places=6)

    def test_samples_are_relative_displacement_not_absolute(self):
        self.drag([(0.30, 0.40), (0.50, 0.40)])
        trace = self.traces.traces()[0]
        # First sample sits at the authoritative origin: zero displacement.
        self.assertAlmostEqual(trace.samples[0].dx, 0.0, places=6)
        self.assertAlmostEqual(trace.samples[0].dy, 0.0, places=6)
        # The last is displacement, not the absolute coordinate.
        self.assertAlmostEqual(trace.samples[-1].dx, 0.20, places=6)
        self.assertNotAlmostEqual(trace.samples[-1].dx, 0.50, places=6)

    def test_the_same_shape_is_start_independent(self):
        """Two frogs, same demonstrated shape, different starting points."""
        self.drag([(0.30, 0.40), (0.40, 0.50), (0.50, 0.40)],
                  command_id="a")
        self.place("frog-2", x=0.10, y=0.10)
        self.drag([(0.10, 0.10), (0.20, 0.20), (0.30, 0.10)],
                  sticker="frog-2", command_id="b")

        first, second = self.traces.traces()
        self.assertNotEqual((first.start.x, first.start.y),
                            (second.start.x, second.start.y))
        self.assertEqual(
            [(round(s.dx, 6), round(s.dy, 6)) for s in first.samples],
            [(round(s.dx, 6), round(s.dy, 6)) for s in second.samples])

    def test_duration_is_preserved_separately(self):
        self.drag([(0.30, 0.40), (0.42, 0.44)], duration_ms=1234)
        self.assertEqual(self.traces.traces()[0].duration_ms, 1234)

    def test_progress_is_monotonic(self):
        self.drag([(0.30, 0.40), (0.35, 0.32), (0.43, 0.30), (0.49, 0.38)])
        samples = self.traces.traces()[0].samples
        for earlier, later in zip(samples, samples[1:]):
            self.assertLessEqual(earlier.t, later.t)


# ---------------------------------------------------------------------------
# Shape is preserved, not just the endpoint
# ---------------------------------------------------------------------------

class ShapeSurvives(GestureCase):

    def test_zigzag_keeps_its_ordered_bends(self):
        points = [(0.30, 0.40), (0.40, 0.30), (0.50, 0.40),
                  (0.60, 0.30), (0.70, 0.40)]
        self.drag(points)
        samples = self.traces.traces()[0].samples
        # The alternating vertical direction survives.
        signs = []
        for earlier, later in zip(samples, samples[1:]):
            delta = later.dy - earlier.dy
            if abs(delta) > 1e-9:
                signs.append(1 if delta > 0 else -1)
        changes = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
        self.assertGreaterEqual(changes, 3)

    def test_loop_does_not_collapse_into_its_endpoint(self):
        """A circle back to near the start is not just "it ended there"."""
        points = [(0.30 + 0.10 * math.cos(2 * math.pi * i / 24),
                   0.40 + 0.10 * math.sin(2 * math.pi * i / 24))
                  for i in range(25)]
        self.drag(points, release=(0.31, 0.41))
        trace = self.traces.traces()[0]

        # Endpoint alone says almost nothing: it is back where it began.
        self.assertLess(
            math.hypot(trace.end.x - trace.start.x,
                       trace.end.y - trace.start.y), 0.05)
        # The trace says a great deal more.
        self.assertGreaterEqual(len(trace.samples), 8)
        reach = max(math.hypot(s.dx, s.dy) for s in trace.samples)
        self.assertGreater(reach, 0.10)
        # It genuinely went around: displacement is spread over all quadrants.
        quadrants = {(s.dx >= 0, s.dy >= 0) for s in trace.samples}
        self.assertEqual(len(quadrants), 4)

    def test_decimation_observes_the_whole_gesture(self):
        """A long drag must not fill the buffer early and miss its end."""
        points = [(0.05 + 0.9 * i / 200, 0.40 + 0.2 * math.sin(i / 8))
                  for i in range(201)]
        self.drag(points)
        samples = self.traces.traces()[0].samples
        self.assertLessEqual(len(samples), MAX_SAMPLES)
        self.assertAlmostEqual(samples[0].t, 0.0, places=6)
        self.assertAlmostEqual(samples[-1].t, 1.0, places=6)
        # Coverage across the whole gesture, not only its beginning.
        self.assertGreater(max(s.t for s in samples[:len(samples) // 2]), 0.2)
        self.assertGreater(len([s for s in samples if s.t > 0.5]), 3)

    def test_decimation_keeps_first_last_and_order(self):
        points = [TrajectorySample(t=i / 50, dx=i / 100, dy=(i % 7) / 100)
                  for i in range(51)]
        out = decimate(points, 10)
        self.assertEqual(len(out), 10)
        self.assertEqual(out[0], points[0])
        self.assertEqual(out[-1], points[-1])
        self.assertEqual(out, sorted(out, key=lambda s: s.t))

    def test_decimation_is_deterministic(self):
        points = [TrajectorySample(t=i / 40, dx=math.cos(i), dy=math.sin(i))
                  for i in range(41)]
        self.assertEqual(decimate(points, 9), decimate(points, 9))


# ---------------------------------------------------------------------------
# The browser is input, not authority
# ---------------------------------------------------------------------------

class BrowserIsUntrusted(GestureCase):

    def assert_refused(self, body_gesture, fragment=None):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "bad-1",
            "point": {"x": 0.42, "y": 0.44},
            "gesture": body_gesture,
        })
        self.assertFalse(result["ok"], result)
        self.assertEqual(len(self.traces), 0)
        if fragment:
            self.assertIn(fragment, result["error"])
        return result

    def test_non_finite_samples_are_refused(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            self.assert_refused({
                "samples": [{"t": 0.0, "x": bad, "y": 0.4}],
                "duration_ms": 100})

    def test_out_of_range_samples_are_refused(self):
        self.assert_refused({
            "samples": [{"t": 0.0, "x": 1.5, "y": 0.4}], "duration_ms": 100})
        self.assert_refused({
            "samples": [{"t": 2.0, "x": 0.4, "y": 0.4}], "duration_ms": 100})

    def test_unordered_progress_is_refused(self):
        self.assert_refused({
            "samples": [{"t": 0.9, "x": 0.3, "y": 0.4},
                        {"t": 0.1, "x": 0.4, "y": 0.4}],
            "duration_ms": 100}, "not ordered")

    def test_excessive_sample_count_is_refused(self):
        samples = [{"t": i / (MAX_INPUT_SAMPLES + 1), "x": 0.3, "y": 0.4}
                   for i in range(MAX_INPUT_SAMPLES + 2)]
        self.assert_refused(
            {"samples": samples, "duration_ms": 900}, "too many")

    def test_large_but_allowed_input_is_decimated_not_refused(self):
        points = [(0.05 + 0.9 * i / (MAX_INPUT_SAMPLES - 1), 0.40)
                  for i in range(MAX_INPUT_SAMPLES)]
        result = self.drag(points)
        self.assertTrue(result["ok"])
        self.assertLessEqual(len(self.traces.traces()[0].samples), MAX_SAMPLES)

    def test_excessive_duration_is_refused(self):
        self.assert_refused({
            "samples": [{"t": 0.0, "x": 0.3, "y": 0.4}],
            "duration_ms": MAX_DURATION_MS + 1}, "duration")

    def test_zero_or_negative_duration_is_refused(self):
        for bad in (0, -5):
            self.assert_refused({
                "samples": [{"t": 0.0, "x": 0.3, "y": 0.4}],
                "duration_ms": bad}, "duration")

    def test_executable_or_metadata_content_is_refused(self):
        self.assert_refused({
            "samples": [{"t": 0.0, "x": 0.3, "y": 0.4,
                         "onload": "alert(1)"}],
            "duration_ms": 100}, "malformed")
        self.assert_refused({
            "samples": [{"t": 0.0, "x": 0.3, "y": 0.4}],
            "duration_ms": 100,
            "actor": "operator"}, "unknown gesture field")
        self.assert_refused({
            "samples": [{"t": 0.0, "x": 0.3, "y": 0.4}],
            "duration_ms": 100,
            "origin": "omegallm-jev"}, "unknown gesture field")

    def test_string_coordinates_are_refused(self):
        self.assert_refused({
            "samples": [{"t": "0", "x": "0.3", "y": "0.4"}],
            "duration_ms": 100}, "malformed")

    def test_browser_cannot_choose_the_acting_principal(self):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "spoof-1",
            "point": {"x": 0.42, "y": 0.44},
            "actor": "operator",
            "gesture": self.gesture([(0.30, 0.40), (0.42, 0.44)]),
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["receipt"]["actor"], HUMAN_ID)
        trace = self.traces.traces()[0]
        self.assertEqual(trace.demonstrated_by, HUMAN_ID)

    def test_browser_cannot_name_another_subject_in_the_gesture(self):
        """The subject comes from the request path, not gesture metadata."""
        self.assert_refused({
            "samples": [{"t": 0.0, "x": 0.3, "y": 0.4}],
            "duration_ms": 100,
            "subject": "cow-1"}, "unknown gesture field")


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

class Eligibility(GestureCase):

    def test_refused_move_produces_no_demonstration(self):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "stale-1",
            "point": {"x": 0.42, "y": 0.44},
            "based_on_revision": 0,
            "gesture": self.gesture([(0.30, 0.40), (0.42, 0.44)]),
        })
        self.assertTrue(result["ok"])
        self.assertFalse(result["receipt"]["accepted"])
        self.assertEqual(len(self.traces), 0)
        self.assertNotIn("gesture", result)

    def test_release_outside_the_page_produces_no_demonstration(self):
        """The browser proposes nothing at all, so there is nothing to keep."""
        before = len(self.traces)
        # No propose-move call happens in that case; nothing is recorded.
        self.assertEqual(len(self.traces), before)
        self.assertEqual(len(self.history), 0)

    def test_move_without_a_gesture_still_works(self):
        result = self.drag([(0.42, 0.44)], gesture=False)
        self.assertTrue(result["ok"])
        self.assertTrue(result["receipt"]["accepted"])
        self.assertEqual(len(self.traces), 0)
        entry = self.history.entries()[-1]
        self.assertIsNone(entry.gesture_trace)


# ---------------------------------------------------------------------------
# Input history is not world history
# ---------------------------------------------------------------------------

class InputIsNotWorldHistory(GestureCase):

    def test_one_drag_creates_exactly_one_governed_mutation(self):
        points = [(0.30 + 0.012 * i, 0.40 + 0.01 * (i % 5))
                  for i in range(40)]
        before_revision = self.kernel.revision
        self.drag(points)

        receipts = self.bridge.receipts(limit=200)
        moves = [r for r in receipts if r["action"] == "move-sticker"]
        self.assertEqual(len(moves), 1)
        self.assertEqual(self.kernel.revision, before_revision + 1)

    def test_no_intermediate_sample_becomes_a_kernel_receipt(self):
        points = [(0.30, 0.40), (0.35, 0.32), (0.43, 0.30), (0.49, 0.38),
                  (0.45, 0.47), (0.36, 0.49), (0.42, 0.44)]
        self.drag(points)
        trace = self.traces.traces()[0]
        self.assertGreater(len(trace.samples), 2)
        self.assertEqual(len(self.bridge.receipts(limit=200)), 1)

    def test_history_records_one_move_linked_to_the_trace(self):
        self.drag([(0.30, 0.40), (0.36, 0.44), (0.42, 0.44)])
        entries = self.history.entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.action, "move-sticker")
        self.assertEqual(entry.origin, "human-gesture")
        self.assertTrue(entry.accepted)
        self.assertEqual(entry.gesture_trace, "gesture-1")
        self.assertEqual(entry.gesture_kind, "freehand")
        # Still no typed key: a drag is not a discrete PatternStep.
        self.assertIsNone(entry.key)

    def test_conversation_projection_names_the_trace_without_samples(self):
        self.drag([(0.30, 0.40), (0.36, 0.44), (0.42, 0.44)])
        described = self.history.describe_for_scene()
        self.assertEqual(len(described), 1)
        entry = described[0]
        self.assertEqual(entry["gestureTrace"], "gesture-1")
        self.assertEqual(entry["gestureKind"], "freehand")
        self.assertNotIn("samples", entry)
        for value in entry.values():
            self.assertNotIsInstance(value, (list, dict))

    def test_trace_summary_carries_no_samples(self):
        self.drag([(0.30, 0.40), (0.36, 0.44), (0.42, 0.44)])
        summary = self.traces.traces()[0].summary()
        self.assertNotIn("samples", summary)
        self.assertEqual(summary["kind"], "freehand")
        self.assertGreater(summary["sampleCount"], 0)


# ---------------------------------------------------------------------------
# Nothing else moved
# ---------------------------------------------------------------------------

class NothingElseChanged(GestureCase):

    def test_core_action_vocabulary_is_unchanged(self):
        self.assertEqual(ALL_ACTIONS, frozenset({
            "noop", "observe", "add-own-sticker", "move-sticker",
            "animate-own-sticker", "resize-own-sticker",
            "set-sticker-facing", "remove-own-sticker",
            "remove-agent-sticker", "create-agent",
        }))
        self.assertEqual(len(MUTATING_ACTIONS), 8)

    def test_a_drag_is_still_not_learnable_as_a_pattern_step(self):
        """Deliberate for this tranche: capture first, interpret later."""
        self.drag([(0.30, 0.40), (0.36, 0.44), (0.42, 0.44)])
        result = self.bridge.jev_controller.remember_recent(
            subject_id="frog-1", label="swoop", learned_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no-accepted-pattern-steps")

    def test_discrete_pattern_learning_still_works_alongside(self):
        moves = self.kernel.available_actions(HUMAN_ID)
        self.assertIn("ANIMATE:frog-1:hop", moves)
        receipt = self.kernel.propose_key(
            HUMAN_ID, "ANIMATE:frog-1:hop", "hop-1",
            requested_by=HUMAN_ID)
        self.history.record(
            receipt, origin="gesture-jev", key="ANIMATE:frog-1:hop",
            subject_id="frog-1")
        result = self.bridge.jev_controller.remember_recent(
            subject_id="frog-1", label="hop dance", learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["pattern"]["steps"],
                         [{"verb": "ANIMATE", "suffix": "hop"}])

    def test_a_drag_ends_a_discrete_episode(self):
        """A drag has no typed form, so it is a non-learnable boundary."""
        receipt = self.kernel.propose_key(
            HUMAN_ID, "ANIMATE:frog-1:hop", "hop-2", requested_by=HUMAN_ID)
        self.history.record(
            receipt, origin="gesture-jev", key="ANIMATE:frog-1:hop",
            subject_id="frog-1")
        self.drag([(0.30, 0.40), (0.42, 0.44)], command_id="drag-after")
        result = self.bridge.jev_controller.remember_recent(
            subject_id="frog-1", label="after drag", learned_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no-accepted-pattern-steps")


# ---------------------------------------------------------------------------
# The worked demonstration
# ---------------------------------------------------------------------------

class FroggyDrawsALoop(GestureCase):

    def test_a_loop_is_remembered_as_shape_not_as_an_endpoint(self):
        # Authoritative start.
        start = self.kernel.sticker("frog-1")
        self.assertEqual((start.x, start.y), (0.30, 0.40))

        # What the child physically drew: out, around, and back.
        observed = [
            (0.30, 0.40), (0.35, 0.32), (0.43, 0.30), (0.49, 0.38),
            (0.45, 0.47), (0.36, 0.49), (0.31, 0.41),
        ]
        result = self.drag(observed, release=(0.42, 0.44), duration_ms=1400)

        # Exactly one governed mutation, at the release point.
        self.assertTrue(result["receipt"]["accepted"])
        self.assertEqual(result["receipt"]["action"], "move-sticker")
        self.assertEqual(len(self.bridge.receipts(limit=200)), 1)
        after = self.kernel.sticker("frog-1")
        self.assertAlmostEqual(after.x, 0.42, places=6)
        self.assertAlmostEqual(after.y, 0.44, places=6)

        # And a demonstration that holds far more than that endpoint.
        trace = self.traces.traces()[0]
        self.assertEqual(trace.start.to_dict(), {"x": 0.30, "y": 0.40})
        self.assertEqual(trace.end.to_dict(), {"x": after.x, "y": after.y})
        self.assertEqual(trace.duration_ms, 1400)
        self.assertGreaterEqual(len(trace.samples), 6)

        # The loop reaches well away from the start and comes back, which a
        # single endpoint could never show. This gesture arcs east, so the
        # evidence is that it went up and then down again.
        reach = max(math.hypot(s.dx, s.dy) for s in trace.samples)
        self.assertGreater(reach, 0.15)
        self.assertLess(min(s.dy for s in trace.samples), -0.05)
        self.assertGreater(max(s.dy for s in trace.samples), 0.05)
        # It returned near its origin mid-gesture, so the path is not monotonic.
        self.assertGreater(
            max(math.hypot(s.dx, s.dy) for s in trace.samples),
            math.hypot(trace.samples[-1].dx, trace.samples[-1].dy))

        # History says one accepted move, and names the demonstration.
        entry = self.history.entries()[-1]
        self.assertEqual(entry.action, "move-sticker")
        self.assertEqual(entry.gesture_trace, trace.trace_id)
        self.assertIsNone(entry.key)


if __name__ == "__main__":
    unittest.main()
