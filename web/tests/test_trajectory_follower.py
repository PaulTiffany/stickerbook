"""Deterministic mechanical following of a resolved subject-frame trajectory.

The mechanical follower is to trajectories what `replay_pattern` is to
remembered patterns: a host-driven reference path that proves the control
loop, progress semantics, boundary behaviour and audit format without any
model in the way. A powered follower swaps only the selector.

No OmegaLLM or OmegaJev inference occurs anywhere in this file's execution
paths, and every accepted motor step is an ordinary kernel move receipt.
"""

from __future__ import annotations

import math
import os
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402
import trajectory_execution as tx  # noqa: E402
from governed_history import ORIGIN_GESTURE_JEV  # noqa: E402
from jev_controller import MECHANICAL_SELECTOR_ID, MOVE_STEP  # noqa: E402
from test_interaction import FakeOmegaLLM, FakeOmegaJev  # noqa: E402

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "core"))

from stickerbook_core import (  # noqa: E402
    ALL_ACTIONS, MOVE_STICKER, MUTATING_ACTIONS, StickerInstance,
)

HUMAN_ID = farm.HUMAN_ID


class FollowerCase(unittest.TestCase):
    """A bird, a drawn path, and the resolved subject-frame reference."""

    def setUp(self):
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge_mod.Bridge(
            agent_runtime=self.llm, jev_runtime=self.jev)
        self.kernel = self.bridge.kernel
        self.controller = self.bridge.jev_controller

    def place(self, sticker_id="bird-1", *, x, y):
        self.kernel.place_sticker(StickerInstance(
            sticker_id, HUMAN_ID, HUMAN_ID, "bird", self.kernel.page,
            x=x, y=y))
        return self.kernel.sticker(sticker_id)

    def reference(self, points, *, frame="subject", subject="bird-1"):
        """Draw a path and have OmegaLLM refer to it in the given frame."""
        samples = [{"t": round(i / max(1, len(points) - 1), 4),
                    "x": x, "y": y} for i, (x, y) in enumerate(points)]
        event = self.bridge.observe_page_path(
            {"duration_ms": 600, "samples": samples})["sourceEvent"]
        self.llm.goal = {"subject": subject, "intent": "reference-trajectory",
                         "demonstration": event, "frame": frame}
        result = self.bridge.converse({"text": "like this"})
        self.assertTrue(result["jev"]["ok"], result)
        return self.bridge.last_trajectory_reference

    def follow(self, reference, *, prefix="follow", select=None):
        return self.controller.follow_trajectory(
            reference, actor=HUMAN_ID, command_prefix=prefix,
            requested_by=HUMAN_ID, select=select)

    def at(self, sticker_id="bird-1"):
        sticker = self.kernel.sticker(sticker_id)
        return (sticker.x, sticker.y)

    def straight_east(self):
        self.place(x=.5, y=.5)
        return self.reference([(.2, .5), (.3, .5), (.4, .5), (.5, .5)])


# ---------------------------------------------------------------------------
# The mechanical bookkeeping, as pure functions
# ---------------------------------------------------------------------------

class ProgressAndObjective(unittest.TestCase):
    """Progress is monotonic, sequential, and never a nearest-point search."""

    class P:
        def __init__(self, x, y):
            self.x, self.y = x, y

    def points(self, pairs):
        return tuple(self.P(x, y) for x, y in pairs)

    def test_advance_walks_only_consecutive_points_within_reach(self):
        points = self.points([(0, 0), (.01, 0), (.02, 0), (.5, 0), (.51, 0)])
        # From the origin, the first three are within one step; the fourth is
        # far, so progress stops there rather than running to the end.
        self.assertEqual(tx.advance(points, 0, (0, 0), MOVE_STEP), 3)

    def test_advance_never_moves_backward(self):
        points = self.points([(0, 0), (.5, 0), (0, 0)])
        # Standing back at the origin with progress already at 2 must not
        # rewind to 0 just because the origin is nearby again.
        self.assertEqual(tx.advance(points, 2, (0, 0), MOVE_STEP), 2)

    def test_a_coincident_first_and_last_point_is_not_completion(self):
        # The out-and-return shape that a nearest-point rule would erase:
        # index 0 and index 2 are the same coordinate.
        points = self.points([(.5, .5), (.5, .9), (.5, .5)])
        self.assertFalse(tx.is_complete(points, 0, (.5, .5), MOVE_STEP))
        # Progress can only reach the final index by passing the excursion.
        self.assertEqual(tx.advance(points, 0, (.5, .5), MOVE_STEP), 1)
        self.assertTrue(tx.is_complete(points, 2, (.5, .5), MOVE_STEP))

    def test_objective_is_the_point_at_the_progress_index(self):
        points = self.points([(0, 0), (.5, 0), (1, 0)])
        self.assertEqual(tx.objective_of(points, 1), (.5, 0))

    def test_planned_steps_from_arc_length_with_a_hard_cap(self):
        flat = self.points([(0, .5), (.6, .5)])
        self.assertAlmostEqual(tx.arc_length(flat), .6)
        self.assertEqual(tx.planned_steps(flat, MOVE_STEP),
                         math.ceil(1.25 * .6 / MOVE_STEP))
        # A single point needs no motor decisions at all.
        self.assertEqual(tx.planned_steps(self.points([(0, 0)]), MOVE_STEP), 0)
        # Arbitrarily long geometry is capped, never unbounded.
        long_path = self.points([(0, i % 2) for i in range(40)])
        self.assertEqual(tx.planned_steps(long_path, MOVE_STEP),
                         tx.MAX_TRAJECTORY_STEPS)

    def test_result_vocabulary(self):
        accepted = [tx.TrajectoryStepRecord(
            index=1, objective_index=0, objective=(0, 0), submitted=True,
            receipt={"accepted": True})]
        refused = [tx.TrajectoryStepRecord(
            index=1, objective_index=0, objective=(0, 0), submitted=True,
            receipt={"accepted": False})]
        self.assertEqual(tx.result_of(accepted, True), "completed")
        self.assertEqual(tx.result_of(accepted, False), "partial")
        self.assertEqual(tx.result_of(refused, False), "stopped")
        self.assertEqual(tx.result_of([], False), "stopped")


# ---------------------------------------------------------------------------
# Following a simple path
# ---------------------------------------------------------------------------

class StraightPath(FollowerCase):

    def test_mechanical_following_completes_on_the_final_waypoint(self):
        reference = self.straight_east()
        result = self.follow(reference)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"], "completed")
        self.assertIsNone(result["execution"]["stoppedReason"])
        self.assertIsNone(result["execution"]["stoppedAt"])
        last = reference.resolved_samples[-1]
        self.assertLess(
            tx.distance(self.at(), (last.x, last.y)), MOVE_STEP)
        self.assertEqual(result["progressReached"],
                         len(reference.resolved_samples) - 1)

    def test_only_finite_offered_moves_are_ever_submitted(self):
        reference = self.straight_east()
        result = self.follow(reference)
        for step in result["execution"]["steps"]:
            self.assertTrue(step["choice"].startswith("MOVE:bird-1:"))
            self.assertEqual(step["receipt"]["action"], MOVE_STICKER)
            # Each step names the objective it was aiming at.
            self.assertIn(step["objectiveIndex"],
                          range(len(reference.resolved_samples)))

    def test_the_audit_record_is_inspectable_and_counts_honestly(self):
        reference = self.straight_east()
        result = self.follow(reference)
        record = result["execution"]
        self.assertEqual(record["pathRef"], reference.path_ref)
        self.assertEqual(record["frame"], "subject")
        self.assertEqual(record["sourceEpisode"], reference.source_episode)
        self.assertEqual(record["subject"], "bird-1")
        self.assertEqual(record["requestedBy"], HUMAN_ID)
        self.assertEqual(record["mode"], "mechanical")
        self.assertEqual(record["waypointCount"],
                         len(reference.resolved_samples))
        self.assertEqual(record["submittedSteps"], len(record["steps"]))
        self.assertEqual(record["acceptedSteps"], len(record["steps"]))
        self.assertLessEqual(record["submittedSteps"], record["plannedSteps"])
        # Filed in the bounded host log, and retrievable by id.
        logged = self.bridge.trajectory_executions.get(record["executionId"])
        self.assertIsNotNone(logged)
        self.assertEqual(logged.to_dict(), record)

    def test_an_already_satisfied_reference_completes_with_no_proposals(self):
        self.place(x=.5, y=.5)
        # A path drawn in one spot: in subject frame every point resolves
        # onto the subject, so there is nothing to do.
        reference = self.reference([(.3, .3), (.3, .3), (.3, .3)])
        before = self.kernel.revision
        result = self.follow(reference)
        self.assertEqual(result["result"], "completed")
        self.assertEqual(result["execution"]["steps"], [])
        self.assertEqual(result["acceptedSteps"], 0)
        self.assertEqual(self.kernel.revision, before)

    def test_a_page_frame_reference_is_not_executable(self):
        self.place(x=.5, y=.5)
        reference = self.reference(
            [(.2, .5), (.4, .5)], frame="page")
        self.assertEqual(reference.frame, "page")
        result = self.follow(reference)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "trajectory-frame-not-executable")
        # Nothing was attempted, and the reference is still valid data.
        self.assertEqual(len(self.bridge.trajectory_executions), 0)
        self.assertEqual(len(reference.resolved_samples), 2)


# ---------------------------------------------------------------------------
# Waypoints finer than one motor step
# ---------------------------------------------------------------------------

class DenseWaypoints(FollowerCase):

    def dense(self):
        self.place(x=.5, y=.5)
        # Twenty-one waypoints spaced .015 apart: a quarter of a motor step.
        return self.reference([(.2 + .015 * i, .5) for i in range(21)])

    def test_spacing_is_below_one_motor_step(self):
        reference = self.dense()
        points = reference.resolved_samples
        gaps = [tx.distance((points[i].x, points[i].y),
                            (points[i + 1].x, points[i + 1].y))
                for i in range(len(points) - 1)]
        self.assertTrue(all(gap < MOVE_STEP for gap in gaps), gaps)

    def test_progress_does_not_demand_one_motor_step_per_waypoint(self):
        reference = self.dense()
        waypoints = len(reference.resolved_samples)
        result = self.follow(reference)
        self.assertEqual(result["result"], "completed")
        # The whole point of the lookahead rule: far fewer decisions than
        # retained points, because several are consumed per step.
        self.assertLess(result["submittedSteps"], waypoints)
        self.assertEqual(result["progressReached"], waypoints - 1)

    def test_objective_indices_advance_monotonically_and_skip_no_excursion(self):
        reference = self.dense()
        result = self.follow(reference)
        indices = [s["objectiveIndex"] for s in result["execution"]["steps"]]
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(len(set(indices)), len(indices))


# ---------------------------------------------------------------------------
# Loops and out-and-return paths
# ---------------------------------------------------------------------------

class ClosedLoop(FollowerCase):

    def loop(self, turns=16, radius=.12):
        self.place(x=.5, y=.5)
        points = [(round(.5 + radius * math.sin(2 * math.pi * k / turns), 4),
                   round(.5 - radius + radius * math.cos(
                       2 * math.pi * k / turns), 4))
                  for k in range(turns + 1)]
        return self.reference(points)

    def test_first_and_final_points_coincide_without_instant_completion(self):
        reference = self.loop()
        points = reference.resolved_samples
        self.assertEqual((points[0].x, points[0].y),
                         (points[-1].x, points[-1].y))
        self.assertEqual((points[0].x, points[0].y), self.at())
        # The subject is standing exactly on the final waypoint's coordinate
        # and the trajectory is nonetheless not complete.
        self.assertFalse(tx.is_complete(points, 0, self.at(), MOVE_STEP))

    def test_monotonic_progress_traverses_the_whole_excursion(self):
        reference = self.loop()
        points = reference.resolved_samples
        result = self.follow(reference)
        self.assertEqual(result["result"], "completed")
        self.assertEqual(result["progressReached"], len(points) - 1)
        indices = [s["objectiveIndex"] for s in result["execution"]["steps"]]
        self.assertEqual(indices, sorted(indices))
        # It really went around: some objective was near the far side of the
        # loop, not just around the shared start/end coordinate.
        origin = (points[0].x, points[0].y)
        excursion = max(
            tx.distance((s["objective"]["x"], s["objective"]["y"]), origin)
            for s in result["execution"]["steps"])
        self.assertGreater(excursion, 2 * MOVE_STEP)
        self.assertAlmostEqual(excursion, 2 * .12, places=2)

    def test_the_subject_returns_near_the_start_only_at_the_end(self):
        reference = self.loop()
        result = self.follow(reference)
        points = reference.resolved_samples
        origin = (points[0].x, points[0].y)
        self.assertLess(tx.distance(self.at(), origin), MOVE_STEP)
        # And it was genuinely away from the origin partway through.
        halfway = result["execution"]["steps"][
            len(result["execution"]["steps"]) // 2]
        self.assertGreater(
            tx.distance((halfway["objective"]["x"], halfway["objective"]["y"]),
                        origin), MOVE_STEP)


# ---------------------------------------------------------------------------
# Page edges: duplicate destinations, and unreachable objectives
# ---------------------------------------------------------------------------

class PageEdges(FollowerCase):

    def test_two_keys_may_share_a_clamped_destination_and_the_tie_is_stable(self):
        self.place(x=.0, y=.0)
        goal = {"subject": "bird-1"}
        table, moves = self.controller._table(HUMAN_ID, goal, move_only=True)
        # At the corner the clamped diagonals collapse onto axis steps.
        self.assertEqual(moves["STEP-NE"], moves["STEP-E"])
        self.assertEqual(moves["STEP-SW"], moves["STEP-S"])
        # The table is NOT deduplicated: this is the honest legal surface a
        # powered chooser will later be shown.
        self.assertEqual(len(moves), 5)
        self.assertEqual(len(set(moves.values())), 3)
        self.assertIn("MOVE:bird-1:STEP-NE", table)
        self.assertIn("MOVE:bird-1:STEP-E", table)

    def test_the_tie_break_picks_the_same_key_every_run(self):
        chosen = set()
        for _ in range(5):
            self.setUp()
            self.place(x=.0, y=.0)
            reference = self.reference([(.2, .2), (.3, .2), (.4, .2)])
            result = self.follow(reference)
            chosen.add(result["execution"]["steps"][0]["choice"])
        # Lexicographic on the action key after distance: STEP-E beats
        # STEP-NE for an identical destination. Same key, every time.
        self.assertEqual(chosen, {"MOVE:bird-1:STEP-E"})

    def test_an_offpage_objective_stops_truthfully_without_deforming_it(self):
        self.place(x=.9, y=.5)
        reference = self.reference([(.1, .5), (.3, .5), (.5, .5), (.7, .5)])
        points = reference.resolved_samples
        # Subject frame translates this path off the east edge.
        self.assertGreater(points[-1].x, 1.0)
        frozen = tuple((p.x, p.y) for p in points)

        result = self.follow(reference)
        self.assertEqual(result["result"], "partial")
        self.assertEqual(result["error"], "trajectory-objective-unreachable")
        self.assertGreater(result["acceptedSteps"], 0)
        # Pinned at the edge, and the reference is untouched.
        self.assertEqual(self.at()[0], 1.0)
        self.assertEqual(
            tuple((p.x, p.y) for p in reference.resolved_samples), frozen)
        self.assertGreater(reference.resolved_samples[-1].x, 1.0)

    def test_unreachable_is_host_determined_not_a_selector_decline(self):
        self.place(x=.9, y=.5)
        reference = self.reference([(.1, .5), (.5, .5)])
        seen = []
        original = self.controller._mechanical_choice

        def watched(snapshot):
            decision = original(snapshot)
            seen.append(decision["choice"])
            return decision

        result = self.follow(reference, select=watched)
        self.assertEqual(result["error"], "trajectory-objective-unreachable")
        # The selector was never asked to choose for the step that stopped
        # the attempt, and never returned NOOP.
        self.assertNotIn("NOOP", seen)
        self.assertEqual(len(seen), result["submittedSteps"])
        for step in result["execution"]["steps"]:
            self.assertTrue(step["submitted"])
            self.assertIsNone(step["unavailableReason"])


# ---------------------------------------------------------------------------
# Bounded attempts
# ---------------------------------------------------------------------------

class StepBudget(FollowerCase):

    def long_zigzag(self):
        self.place(x=.5, y=.5)
        # Arc length far beyond what 48 motor steps can cover, kept on-page
        # so the stop is the budget rather than an edge.
        points = [(.5, .5)]
        for i in range(15):
            points.append((round(.5 + .02 * (i + 1), 4),
                           .15 if i % 2 == 0 else .85))
        return self.reference(points)

    def test_a_long_path_is_capped_and_never_reports_completion(self):
        reference = self.long_zigzag()
        points = reference.resolved_samples
        self.assertGreater(
            1.25 * tx.arc_length(points) / MOVE_STEP, tx.MAX_TRAJECTORY_STEPS)
        result = self.follow(reference)
        self.assertEqual(result["plannedSteps"], tx.MAX_TRAJECTORY_STEPS)
        self.assertNotEqual(result["result"], "completed")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "step-budget-exhausted")
        self.assertEqual(result["result"], "partial")
        self.assertEqual(result["submittedSteps"], tx.MAX_TRAJECTORY_STEPS)
        self.assertLess(result["progressReached"], len(points) - 1)

    def test_the_budget_comes_from_geometry_before_any_step_is_taken(self):
        reference = self.straight_east()
        points = reference.resolved_samples
        expected = math.ceil(1.25 * tx.arc_length(points) / MOVE_STEP)
        result = self.follow(reference)
        self.assertEqual(result["plannedSteps"], expected)
        self.assertLess(result["submittedSteps"], result["plannedSteps"])

    def test_budget_exhaustion_is_never_recorded_as_a_decline(self):
        result = self.follow(self.long_zigzag())
        for step in result["execution"]["steps"]:
            self.assertNotEqual(step["choice"], "NOOP")
            self.assertTrue(step["receipt"]["accepted"])
        self.assertEqual(result["execution"]["stoppedReason"],
                         "step-budget-exhausted")


# ---------------------------------------------------------------------------
# The child is the higher-authority actor
# ---------------------------------------------------------------------------

class HumanIntervention(FollowerCase):

    def crossing(self):
        self.place(x=.5, y=.5)
        self.place("bird-2", x=.2, y=.2)
        return self.reference([(.1, .5), (.2, .5), (.3, .5), (.4, .5)])

    def at_the_seam(self, reference, disturb):
        """Run one attempt, disturbing the world once at the selector seam."""
        fired = []
        original = self.controller._mechanical_choice

        def select(snapshot):
            if not fired:
                fired.append(disturb())
            return original(snapshot)

        result = self.follow(reference, select=select)
        return result, fired[0] if fired else None

    def child_drag(self, x=.15, y=.85, sticker="bird-1"):
        """A real child gesture, on its own thread, through the bridge."""
        landed = []
        thread = threading.Thread(target=lambda: landed.append(
            self.bridge.propose_move({
                "sticker": sticker, "command_id": "child-drag",
                "point": {"x": x, "y": y}})))
        thread.start()
        thread.join(5)
        # It must complete while selection is paused, not merely eventually.
        self.assertFalse(thread.is_alive(), "the child's gesture blocked")
        return landed[0]

    def test_a_child_moving_the_subject_supersedes_the_attempt(self):
        reference = self.crossing()
        result, child = self.at_the_seam(reference, self.child_drag)

        self.assertTrue(child["ok"], child)
        # The child's move is what happened, and it stands.
        self.assertEqual(self.at(), (.15, .85))
        # The stale motor proposal was submitted and refused AS stale.
        last = result["execution"]["steps"][-1]
        self.assertTrue(last["submitted"])
        self.assertFalse(last["receipt"]["accepted"])
        self.assertEqual(last["receipt"]["reason"], "stale-revision")
        self.assertTrue(last["superseded"])
        # The attempt stops, truthfully, with no retry and no re-aim.
        self.assertEqual(result["error"], "superseded-by-human")
        self.assertEqual(result["execution"]["stoppedAt"],
                         len(result["execution"]["steps"]))
        self.assertEqual(self.at(), (.15, .85))

    def test_supersession_needs_direct_human_evidence_for_this_subject(self):
        # The SAME subject moved by another controller path also stales the
        # table, but calling that "the child did it" would be fabricated
        # provenance. The neutral reason is used instead.
        reference = self.crossing()

        def agent_moves_subject():
            sticker = self.kernel.sticker("bird-1")
            moves = self.controller._move_candidates(sticker)
            receipt = self.kernel.propose_key(
                HUMAN_ID, "MOVE:bird-1:STEP-S", "other-controller",
                based_on_revision=self.kernel.revision, requested_by=HUMAN_ID,
                selected_by="agent:someone-else", move_candidates=moves)
            self.bridge.history.record(
                receipt, origin=ORIGIN_GESTURE_JEV,
                key="MOVE:bird-1:STEP-S", subject_id="bird-1")
            return receipt

        result, receipt = self.at_the_seam(reference, agent_moves_subject)
        self.assertTrue(receipt.accepted)
        last = result["execution"]["steps"][-1]
        self.assertEqual(last["receipt"]["reason"], "stale-revision")
        self.assertFalse(last["superseded"])
        self.assertEqual(result["error"], "world-changed")
        self.assertNotEqual(result["error"], "superseded-by-human")

    def test_a_change_to_another_sticker_does_not_disturb_the_attempt(self):
        # The kernel's staleness check is per-sticker, so an unrelated
        # mutation advances the global revision without staling this table.
        reference = self.crossing()
        result, other = self.at_the_seam(
            reference, lambda: self.child_drag(.3, .3, sticker="bird-2"))
        self.assertTrue(other["ok"], other)
        self.assertEqual(result["result"], "completed")
        self.assertIsNone(result["execution"]["stoppedReason"])
        for step in result["execution"]["steps"]:
            self.assertFalse(step["superseded"])
        self.assertEqual(self.at("bird-2"), (.3, .3))

    def test_no_world_lock_is_held_across_the_selector_seam(self):
        reference = self.crossing()
        observed = {}
        original = self.controller._mechanical_choice

        def select(snapshot):
            # This thread holds nothing...
            observed["own"] = self.bridge._world_lock._is_owned()
            # ...and no other holder is blocking the world either. An
            # RLock must be released by its owner, so the probe thread takes
            # and returns it itself.
            acquired = []

            def probe_lock():
                got = self.bridge._world_lock.acquire(timeout=5)
                acquired.append(got)
                if got:
                    self.bridge._world_lock.release()

            probe = threading.Thread(target=probe_lock)
            probe.start()
            probe.join(5)
            observed["free"] = bool(acquired and acquired[0])
            return original(snapshot)

        result = self.follow(reference, select=select)
        self.assertTrue(result["ok"], result)
        self.assertIs(observed["own"], False)
        self.assertIs(observed["free"], True)


# ---------------------------------------------------------------------------
# What following a trajectory is NOT allowed to be
# ---------------------------------------------------------------------------

class TrajectoryCarriesNoAuthority(FollowerCase):

    def test_no_model_of_either_loop_is_consulted(self):
        reference = self.straight_east()
        calls = len(self.llm.texts)
        with patch.object(self.jev, "choose",
                          side_effect=AssertionError("OmegaJev")), \
                patch.object(self.jev, "available",
                             side_effect=AssertionError("Jev probe")), \
                patch.object(self.llm, "converse",
                             side_effect=AssertionError("OmegaLLM")):
            result = self.follow(reference)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.jev.calls, [])
        self.assertEqual(len(self.llm.texts), calls)

    def test_every_accepted_step_is_an_ordinary_kernel_move_receipt(self):
        reference = self.straight_east()
        vocabulary = (ALL_ACTIONS, MUTATING_ACTIONS)
        before = len(self.kernel.receipts)
        result = self.follow(reference)
        receipts = self.kernel.receipts[before:]
        self.assertEqual(len(receipts), result["submittedSteps"])
        for receipt in receipts:
            self.assertEqual(receipt.action, MOVE_STICKER)
            self.assertIn(receipt.action, ALL_ACTIONS)
            self.assertEqual(receipt.actor, HUMAN_ID)
            # Controller motion under the child's authority, recorded as such.
            self.assertEqual(receipt.selected_by, MECHANICAL_SELECTOR_ID)
            self.assertIsNone(receipt.translated_by)
        # No new kernel action vocabulary was introduced.
        self.assertEqual(vocabulary, (ALL_ACTIONS, MUTATING_ACTIONS))

    def test_following_creates_no_pattern_memory_and_no_semantic_carry(self):
        reference = self.straight_east()
        before = (len(self.bridge.patterns), len(self.bridge.replays),
                  self.bridge.pending_reference)
        self.follow(reference)
        self.assertEqual(
            (len(self.bridge.patterns), len(self.bridge.replays),
             self.bridge.pending_reference), before)

    def test_the_reference_is_never_mutated_by_following_it(self):
        reference = self.straight_east()
        frozen = (reference.describe(), reference.resolved_samples,
                  reference.source_samples, reference.observed_duration_ms)
        self.follow(reference)
        self.assertEqual(
            (reference.describe(), reference.resolved_samples,
             reference.source_samples, reference.observed_duration_ms), frozen)

    def test_observed_timing_is_ignored_by_execution_and_left_intact(self):
        reference = self.straight_east()
        self.assertEqual(reference.observed_duration_ms, 600)
        times = [p.t for p in reference.resolved_samples]
        result = self.follow(reference)
        # No timing appears anywhere in the execution record.
        record = result["execution"]
        self.assertNotIn("durationMs", record)
        self.assertNotIn("t", record)
        for step in record["steps"]:
            self.assertEqual(set(step["objective"]), {"x", "y"})
        self.assertEqual([p.t for p in reference.resolved_samples], times)
        self.assertEqual(reference.observed_duration_ms, 600)

    def test_the_trajectory_is_never_compiled_into_a_key_sequence(self):
        # Each step's table is rebuilt from current state: moving the subject
        # between attempts changes which keys are chosen, so no step list
        # could have been precomputed.
        reference = self.straight_east()
        first = [s["choice"] for s in
                 self.follow(reference, prefix="a")["execution"]["steps"]]
        self.bridge.propose_move({"sticker": "bird-1", "command_id": "moved",
                                  "point": {"x": .5, "y": .2}})
        second = [s["choice"] for s in
                  self.follow(reference, prefix="b")["execution"]["steps"]]
        self.assertNotEqual(first, second)
        self.assertTrue(second)

    def test_the_selector_only_ever_sees_current_offered_choices(self):
        reference = self.straight_east()
        seen = []
        original = self.controller._mechanical_choice

        def select(snapshot):
            table, _ = self.controller._table(
                HUMAN_ID, {"subject": "bird-1"}, move_only=True)
            seen.append((set(snapshot["actions"]), set(table)))
            # Only moves carry destinations; NOOP is not a candidate.
            self.assertIn("NOOP", snapshot["actions"])
            self.assertNotIn("NOOP", snapshot["destinations"])
            return original(snapshot)

        self.follow(reference, select=select)
        self.assertTrue(seen)
        for offered, current in seen:
            self.assertEqual(offered, current)

    def test_an_invalid_selector_choice_is_refused_not_submitted(self):
        reference = self.straight_east()
        result = self.follow(
            reference,
            select=lambda snapshot: {"ok": True, "choice": "MOVE:bird-1:FLY"})
        self.assertEqual(result["error"], "unknown-selector-choice")
        self.assertEqual(result["execution"]["steps"], [])
        self.assertEqual(result["result"], "stopped")

    def test_a_declining_selector_is_not_completion(self):
        reference = self.straight_east()
        result = self.follow(
            reference, select=lambda snapshot: {"ok": True, "choice": "NOOP"})
        self.assertNotEqual(result["result"], "completed")
        self.assertEqual(result["error"], "selector-declined")
        self.assertEqual(result["result"], "stopped")


if __name__ == "__main__":
    unittest.main()
