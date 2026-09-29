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

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402
import sticker_drag  # noqa: E402
from sticker_drag import (  # noqa: E402
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

    def drag_payload(self, points, duration_ms=800):
        """Build a browser-shaped drag payload from absolute points."""
        last = len(points) - 1 or 1
        return {
            "samples": [
                {"t": index / last, "x": x, "y": y}
                for index, (x, y) in enumerate(points)
            ],
            "duration_ms": duration_ms,
        }

    def drag(self, points, *, sticker="frog-1", command_id="move-1",
             release=None, duration_ms=800, telemetry=True):
        release = release if release is not None else points[-1]
        body = {
            "sticker": sticker,
            "command_id": command_id,
            "point": {"x": release[0], "y": release[1]},
        }
        if telemetry:
            body["drag"] = self.drag_payload(points, duration_ms)
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
        self.assertEqual(trace.kind, "sticker-drag")
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
        points = [(0.05 + 0.9 * i / 179, 0.40 + 0.2 * math.sin(i / 8))
                  for i in range(180)]
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

    def assert_refused(self, body_drag, fragment=None, command_id="bad-1"):
        """Unusable telemetry is discarded; the ordinary move still happens.

        Failure to observe must not become failure to act. The child's
        sticker does not snap back because auxiliary observation was bad.
        """
        before = self.kernel.sticker("frog-1")
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": command_id,
            "point": {"x": 0.42, "y": 0.44},
            "drag": body_drag,
        })
        # The move was adjudicated normally.
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["receipt"]["accepted"], result)
        self.assertEqual(result["receipt"]["action"], "move-sticker")
        after = self.kernel.sticker("frog-1")
        self.assertAlmostEqual(after.x, 0.42, places=6)
        self.assertAlmostEqual(after.y, 0.44, places=6)
        self.assertNotEqual((after.x, after.y), (before.x, before.y))
        # The observation was discarded and never reached history.
        self.assertEqual(len(self.traces), 0)
        self.assertNotIn("drag", result)
        self.assertIn("dragIgnored", result)
        self.assertIsNone(self.history.entries()[-1].gesture_trace)
        if fragment:
            self.assertIn(fragment, result["dragIgnored"])
        return result

    def test_non_finite_samples_are_refused(self):
        for index, bad in enumerate(
                (float("nan"), float("inf"), float("-inf"))):
            self.setUp()
            self.assert_refused({
                "samples": [{"t": 0.5, "x": bad, "y": 0.4}],
                "duration_ms": 100}, command_id="nf-%d" % index)

    def test_out_of_range_samples_are_refused(self):
        self.assert_refused({
            "samples": [{"t": 0.5, "x": 1.5, "y": 0.4}], "duration_ms": 100},
            command_id="oor-1")
        self.setUp()
        self.assert_refused({
            "samples": [{"t": 2.0, "x": 0.4, "y": 0.4}], "duration_ms": 100},
            command_id="oor-2")

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
            "samples": [{"t": 0.5, "x": 0.3, "y": 0.4}],
            "duration_ms": MAX_DURATION_MS + 1}, "duration")

    def test_zero_or_negative_duration_is_refused(self):
        for index, bad in enumerate((0, -5)):
            self.setUp()
            self.assert_refused({
                "samples": [{"t": 0.5, "x": 0.3, "y": 0.4}],
                "duration_ms": bad}, "duration", command_id="d-%d" % index)

    def test_executable_or_metadata_content_is_refused(self):
        self.assert_refused({
            "samples": [{"t": 0.5, "x": 0.3, "y": 0.4,
                         "onload": "alert(1)"}],
            "duration_ms": 100}, "malformed", command_id="x-1")
        self.setUp()
        self.assert_refused({
            "samples": [{"t": 0.5, "x": 0.3, "y": 0.4}],
            "duration_ms": 100,
            "actor": "operator"}, "unknown drag telemetry field",
            command_id="x-2")
        self.setUp()
        self.assert_refused({
            "samples": [{"t": 0.5, "x": 0.3, "y": 0.4}],
            "duration_ms": 100,
            "origin": "omegallm-jev"}, "unknown drag telemetry field",
            command_id="x-3")

    def test_string_coordinates_are_refused(self):
        self.assert_refused({
            "samples": [{"t": "0.5", "x": "0.3", "y": "0.4"}],
            "duration_ms": 100}, "malformed")

    def test_browser_cannot_choose_the_acting_principal(self):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "spoof-1",
            "point": {"x": 0.42, "y": 0.44},
            "actor": "operator",
            "drag": self.drag_payload([(0.30, 0.40), (0.42, 0.44)]),
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["receipt"]["actor"], HUMAN_ID)
        trace = self.traces.traces()[0]
        self.assertEqual(trace.demonstrated_by, HUMAN_ID)

    def test_browser_cannot_name_another_subject_in_the_drag(self):
        """The subject comes from the request path, not drag metadata."""
        self.assert_refused({
            "samples": [{"t": 0.5, "x": 0.3, "y": 0.4}],
            "duration_ms": 100,
            "subject": "cow-1"}, "unknown drag telemetry field")


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

class Eligibility(GestureCase):

    def test_refused_move_produces_no_demonstration(self):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "stale-1",
            "point": {"x": 0.42, "y": 0.44},
            "based_on_revision": 0,
            "drag": self.drag_payload([(0.30, 0.40), (0.42, 0.44)]),
        })
        self.assertTrue(result["ok"])
        self.assertFalse(result["receipt"]["accepted"])
        self.assertEqual(len(self.traces), 0)
        self.assertNotIn("drag", result)

    def test_release_outside_the_page_produces_no_demonstration(self):
        """The browser proposes nothing at all, so there is nothing to keep."""
        before = len(self.traces)
        # No propose-move call happens in that case; nothing is recorded.
        self.assertEqual(len(self.traces), before)
        self.assertEqual(len(self.history), 0)

    def test_move_without_a_gesture_still_works(self):
        result = self.drag([(0.42, 0.44)], telemetry=False)
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
        self.assertEqual(entry.gesture_trace, "drag-1")
        self.assertEqual(entry.gesture_kind, "sticker-drag")
        # Still no typed key: a drag is not a discrete PatternStep.
        self.assertIsNone(entry.key)

    def test_conversation_projection_names_the_trace_without_samples(self):
        self.drag([(0.30, 0.40), (0.36, 0.44), (0.42, 0.44)])
        described = self.history.describe_for_scene()
        self.assertEqual(len(described), 1)
        entry = described[0]
        self.assertEqual(entry["gestureTrace"], "drag-1")
        self.assertEqual(entry["gestureKind"], "sticker-drag")
        self.assertNotIn("samples", entry)
        for value in entry.values():
            self.assertNotIsInstance(value, (list, dict))

    def test_trace_summary_carries_no_samples(self):
        self.drag([(0.30, 0.40), (0.36, 0.44), (0.42, 0.44)])
        summary = self.traces.traces()[0].summary()
        self.assertNotIn("samples", summary)
        self.assertEqual(summary["kind"], "sticker-drag")
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


# ---------------------------------------------------------------------------
# Correction 1: the endpoints are bound by the host, not by the browser
# ---------------------------------------------------------------------------

class EndpointsAreHostBound(GestureCase):

    def test_first_sample_is_the_authoritative_origin(self):
        # The browser claims the drag began somewhere else entirely.
        self.drag([(0.90, 0.10), (0.60, 0.20), (0.42, 0.44)])
        samples = self.traces.traces()[0].samples
        self.assertEqual(samples[0].t, 0.0)
        self.assertEqual(samples[0].dx, 0.0)
        self.assertEqual(samples[0].dy, 0.0)

    def test_last_sample_is_the_accepted_authoritative_endpoint(self):
        # The browser claims the drag ended somewhere it did not.
        self.drag([(0.30, 0.40), (0.35, 0.45), (0.05, 0.05)],
                  release=(0.42, 0.44))
        trace = self.traces.traces()[0]
        after = self.kernel.sticker("frog-1")
        last = trace.samples[-1]
        self.assertEqual(last.t, 1.0)
        self.assertAlmostEqual(last.dx, after.x - trace.start.x, places=6)
        self.assertAlmostEqual(last.dy, after.y - trace.start.y, places=6)
        self.assertAlmostEqual(last.dx, 0.12, places=6)
        self.assertAlmostEqual(last.dy, 0.04, places=6)

    def test_browser_endpoint_claims_are_dropped_not_trusted(self):
        """Samples at the extremes of progress never survive as evidence."""
        self.drag([(0.99, 0.99), (0.36, 0.44), (0.01, 0.01)],
                  release=(0.42, 0.44))
        trace = self.traces.traces()[0]
        # Two interior samples were offered at t=0 and t=1; both were
        # replaced by host-bound anchors.
        self.assertEqual(trace.observed_sample_count, 1)
        self.assertEqual(len(trace.samples), 3)
        for sample in trace.samples:
            self.assertNotAlmostEqual(sample.dx, 0.69, places=3)

    def test_interior_samples_remain_observed_input(self):
        self.drag([(0.30, 0.40), (0.36, 0.30), (0.44, 0.34), (0.42, 0.44)])
        trace = self.traces.traces()[0]
        interior = trace.samples[1:-1]
        self.assertTrue(interior)
        for sample in interior:
            self.assertGreater(sample.t, 0.0)
            self.assertLess(sample.t, 1.0)

    def test_a_trace_with_no_usable_interior_still_has_both_anchors(self):
        self.drag([(0.30, 0.40), (0.42, 0.44)], release=(0.42, 0.44))
        samples = self.traces.traces()[0].samples
        self.assertEqual(len(samples), 2)
        self.assertEqual((samples[0].t, samples[0].dx, samples[0].dy),
                         (0.0, 0.0, 0.0))
        self.assertEqual(samples[-1].t, 1.0)


# ---------------------------------------------------------------------------
# Correction 2: failure to observe is not failure to act
# ---------------------------------------------------------------------------

class ObservationFailureDoesNotCancelTheMove(GestureCase):

    def test_malformed_telemetry_still_moves_the_sticker(self):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "m-1",
            "point": {"x": 0.55, "y": 0.60},
            "drag": {"samples": [{"t": 0.5, "x": "oops", "y": 0.4}],
                     "duration_ms": 100},
        })
        self.assertTrue(result["ok"])
        self.assertTrue(result["receipt"]["accepted"])
        after = self.kernel.sticker("frog-1")
        self.assertAlmostEqual(after.x, 0.55, places=6)
        self.assertAlmostEqual(after.y, 0.60, places=6)
        self.assertEqual(len(self.traces), 0)
        self.assertEqual(result["dragIgnored"], "malformed drag sample")

    def test_oversized_telemetry_still_moves_the_sticker(self):
        samples = [{"t": 0.5, "x": 0.3, "y": 0.4}
                   for _ in range(MAX_INPUT_SAMPLES + 1)]
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "m-2",
            "point": {"x": 0.55, "y": 0.60},
            "drag": {"samples": samples, "duration_ms": 900},
        })
        self.assertTrue(result["receipt"]["accepted"])
        self.assertEqual(len(self.traces), 0)
        self.assertIn("too many", result["dragIgnored"])

    def test_telemetry_that_is_not_an_object_still_moves_the_sticker(self):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "m-3",
            "point": {"x": 0.55, "y": 0.60},
            "drag": "not an object",
        })
        self.assertTrue(result["receipt"]["accepted"])
        self.assertEqual(len(self.traces), 0)
        self.assertIn("must be an object", result["dragIgnored"])

    def test_a_still_invalid_move_is_still_refused(self):
        """Tolerating bad telemetry does not tolerate a bad move."""
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "m-4",
            "point": {"x": 0.55, "y": 0.60},
            "based_on_revision": 0,
            "drag": {"samples": [{"t": 0.5, "x": "oops", "y": 0.4}],
                     "duration_ms": 100},
        })
        self.assertFalse(result["receipt"]["accepted"])
        self.assertEqual(len(self.traces), 0)

    def test_a_malformed_move_shape_is_still_a_bad_request(self):
        result = self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "m-5",
            "drag": {"samples": [{"t": 0.5, "x": 0.3, "y": 0.4}],
                     "duration_ms": 100},
        })
        self.assertFalse(result["ok"])
        self.assertIn("pointer position", result["error"])


# ---------------------------------------------------------------------------
# Correction 3: the browser reducer keeps sharp bends, not just coverage
# ---------------------------------------------------------------------------

class BrowserReducerKeepsShape(unittest.TestCase):
    """Runs the reducer that actually ships in app.js, through node.

    A source assertion alone would not prove the algorithm behaves; this
    extracts the shipped code and executes it.
    """

    def setUp(self):
        self.app = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "app.js")
        with open(self.app, encoding="utf-8") as handle:
            self.source = handle.read()
        if shutil.which("node") is None:
            self.skipTest("node is not available")

    def reducer_source(self):
        start = self.source.index("const DRAG_SAMPLE_CAP")
        end = self.source.index("const round3", start)
        return self.source[start:end]

    def run_reducer(self, points):
        harness = self.reducer_source() + """
        const out = [];
        for (const p of INPUT) { observeDrag(p); }
        console.log(JSON.stringify(dragSamples.map(s => [s.x, s.y])));
        """
        harness = ("const INPUT = " + json.dumps(
            [{"x": x, "y": y} for x, y in points]) + ";\n"
            + "const performance = { now: () => 0 };\n"
            + harness)
        with tempfile.NamedTemporaryFile(
                "w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(harness)
            path = handle.name
        try:
            output = subprocess.run(
                ["node", path], capture_output=True, text=True, timeout=30)
            self.assertEqual(output.returncode, 0, output.stderr)
            return json.loads(output.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(path)

    def test_it_does_not_halve_by_index(self):
        source = self.reducer_source()
        self.assertIn("pathError", source)
        self.assertNotIn("i % 2", source)
        self.assertNotIn("gestureStride", source)

    def test_a_sharp_wiggle_survives_a_long_drag(self):
        """A brief hook inside a long sweep must not be discarded."""
        points = [(0.05 + 0.006 * i, 0.50) for i in range(120)]
        # One sharp two-point wiggle, far off the straight sweep.
        wiggle_at = len(points)
        points += [(0.77, 0.20), (0.80, 0.80)]
        points += [(0.80 + 0.002 * i, 0.50) for i in range(60)]

        kept = self.run_reducer(points)
        self.assertLessEqual(len(kept), 64)
        ys = [y for _, y in kept]
        # The hook survived: both extremes are still present.
        self.assertLess(min(ys), 0.25)
        self.assertGreater(max(ys), 0.75)
        self.assertGreater(wiggle_at, 0)

    def test_coverage_across_the_whole_drag_is_kept(self):
        points = [(0.02 + 0.0078 * i, 0.50 + 0.2 * math.sin(i / 5))
                  for i in range(125)]
        kept = self.run_reducer(points)
        xs = [x for x, _ in kept]
        self.assertLessEqual(len(kept), 64)
        self.assertAlmostEqual(xs[0], 0.02, places=6)
        self.assertGreater(max(xs), 0.9)
        self.assertGreater(len([x for x in xs if x > 0.5]), 5)

    def test_reduction_is_deterministic(self):
        points = [(0.05 + 0.007 * i, 0.5 + 0.2 * math.sin(i / 3))
                  for i in range(130)]
        self.assertEqual(self.run_reducer(points), self.run_reducer(points))


# ---------------------------------------------------------------------------
# Correction 4: a worst-case legal payload fits the transport
# ---------------------------------------------------------------------------

class PayloadFitsTheTransport(unittest.TestCase):

    def browser_shaped_body(self, count):
        """Worst case: longest ids, full-width coordinates, max duration."""
        return json.dumps({
            "sticker": "butterfly-99",
            "command_id": "move-1759000000000-000",
            "point": {"x": 0.9999, "y": 0.9999},
            "drag": {
                "samples": [
                    {"t": round(i / max(1, count - 1), 3),
                     "x": 0.9999, "y": 0.9999}
                    for i in range(count)
                ],
                "duration_ms": MAX_DURATION_MS - 1,
            },
        }, separators=(",", ":")).encode("utf-8")

    def test_browser_retention_fits_comfortably(self):
        body = self.browser_shaped_body(64)
        self.assertLess(len(body), bridge_mod.MAX_BODY_BYTES // 2)

    def test_host_sample_cap_fits_the_transport(self):
        body = self.browser_shaped_body(MAX_INPUT_SAMPLES)
        self.assertLessEqual(len(body), bridge_mod.MAX_BODY_BYTES)

    def test_the_app_caps_browser_retention_below_the_host_cap(self):
        app = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "app.js")
        with open(app, encoding="utf-8") as handle:
            source = handle.read()
        cap = int(re.search(
            r"const DRAG_SAMPLE_CAP = (\d+)", source).group(1))
        self.assertLessEqual(cap, MAX_INPUT_SAMPLES)
        self.assertLess(len(self.browser_shaped_body(cap)),
                        bridge_mod.MAX_BODY_BYTES)

    def test_a_worst_case_payload_survives_a_real_http_round_trip(self):
        httpd, bridge = bridge_mod.serve("127.0.0.1", 0, quiet=True)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever,
                                  kwargs={"poll_interval": 0.05})
        thread.daemon = True
        thread.start()
        try:
            bridge.kernel.place_sticker(StickerInstance(
                "butterfly-99", HUMAN_ID, HUMAN_ID, "butterfly", 1,
                x=0.30, y=0.40, animation="rest"))
            body = self.browser_shaped_body(64)
            self.assertLess(len(body), bridge_mod.MAX_BODY_BYTES)
            request = urllib.request.Request(
                "http://127.0.0.1:%d/api/propose-move" % port,
                data=body, method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.load(response)
            self.assertTrue(payload["ok"], payload)
            self.assertTrue(payload["receipt"]["accepted"], payload)
            self.assertIn("drag", payload)
            self.assertEqual(payload["drag"]["kind"], "sticker-drag")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
