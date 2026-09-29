"""OmegaJev choosing the motor steps along a demonstrated trajectory.

Tranche C changes exactly one thing about following a trajectory: who picks
one of the current legal choices. Objective, monotonic progress, completion,
move_only table construction, revision discipline, page-edge behaviour, human
supersession and the audit record are all the shared implementation the
mechanical follower already established and `test_trajectory_follower.py`
still pins.

    child language      -> OmegaLLM   -> perform-trajectory
    resolved reference  -> host       -> CURRENT local objective
    bounded snapshot    -> OmegaJev   -> one offered key
    key                 -> kernel     -> ordinary move receipt
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402
import trajectory_execution as tx  # noqa: E402
import test_pattern_provider as provider_tests  # noqa: E402
from governed_history import ORIGIN_GESTURE_JEV  # noqa: E402
from jev_controller import (  # noqa: E402
    MOVE_STEP, OMEGA_JEV_ID, OMEGA_LLM_ID, TRAJECTORY_DECISION,
)
from test_interaction import FakeOmegaLLM  # noqa: E402

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "core"))

from stickerbook_core import (  # noqa: E402
    ALL_ACTIONS, MOVE_STICKER, MUTATING_ACTIONS, StickerInstance,
)

HUMAN_ID = farm.HUMAN_ID
_DESTINATION = re.compile(r"x=(-?\d+(?:\.\d+)?) y=(-?\d+(?:\.\d+)?)")


class TrajectoryJev:
    """A deterministic OmegaJev double that actually follows the course.

    It is given only the bounded trajectory scene and the offered action
    descriptions, and must work out a step from those alone. That it can is
    the evidence that the snapshot carries enough to choose with -- and that
    it needs no sample array to do it.
    """

    def __init__(self, *, answer=None, fail=False, available=True):
        self.calls = []
        self.answer = answer
        self.fail = fail
        self._available = available

    def available(self):
        return self._available

    def choose(self, *, goal, scene, actions, turn, max_turns):
        self.calls.append({
            "goal": dict(goal), "scene": scene, "actions": dict(actions),
            "turn": turn, "max_turns": max_turns,
        })
        if self.fail:
            raise RuntimeError("omegajev exploded")
        if self.answer is not None:
            return self.answer
        trajectory = scene.get("trajectory")
        if not trajectory:
            return {"ok": True, "choice": "NOOP"}
        target = (trajectory["objective"]["x"], trajectory["objective"]["y"])
        best, best_distance = None, None
        for key, description in sorted(actions.items()):
            found = _DESTINATION.search(description)
            if not found:
                continue
            here = (float(found.group(1)), float(found.group(2)))
            gap = math.hypot(here[0] - target[0], here[1] - target[1])
            if best_distance is None or gap < best_distance:
                best, best_distance = key, gap
        return {"ok": True, "choice": best or "NOOP"}


class PoweredCase(unittest.TestCase):

    def setUp(self):
        self.llm = FakeOmegaLLM()
        self.jev = TrajectoryJev()
        self.bridge = bridge_mod.Bridge(
            agent_runtime=self.llm, jev_runtime=self.jev)
        self.kernel = self.bridge.kernel
        self.controller = self.bridge.jev_controller

    def place(self, sticker_id="bird-1", *, x, y):
        self.kernel.place_sticker(StickerInstance(
            sticker_id, HUMAN_ID, HUMAN_ID, "bird", self.kernel.page,
            x=x, y=y))

    def drawn(self, points):
        samples = [{"t": round(i / max(1, len(points) - 1), 4),
                    "x": x, "y": y} for i, (x, y) in enumerate(points)]
        return self.bridge.observe_page_path(
            {"duration_ms": 500, "samples": samples})["sourceEvent"]

    def say(self, goal, text="Bird, do that movement starting where you are"):
        self.llm.goal = goal
        return self.bridge.converse({"text": text})

    def perform(self, points, *, frame="subject", subject="bird-1",
                text="Bird, do that movement starting where you are"):
        event = self.drawn(points)
        return self.say({"subject": subject, "intent": "perform-trajectory",
                         "demonstration": event, "frame": frame}, text)

    def short_east(self, **kwargs):
        self.place(x=.5, y=.5)
        return self.perform([(.2, .5), (.26, .5), (.32, .5), (.38, .5)],
                            **kwargs)

    def at(self, sticker_id="bird-1"):
        sticker = self.kernel.sticker(sticker_id)
        return (sticker.x, sticker.y)


# ---------------------------------------------------------------------------
# The child-facing semantic contract
# ---------------------------------------------------------------------------

class ProviderPerformTrajectory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        provider_tests.PatternProvider.setUpClass()

    def setUp(self):
        self.harness = provider_tests.PatternProvider()
        self.goal = {"subject": "bird-1", "intent": "perform-trajectory",
                     "demonstration": "input-event-1", "frame": "subject"}
        self.scene = {"stickers": [{"id": "bird-1"}], "interaction": {
            "signals": [{"kind": "page-path", "sourceEvent": "input-event-1",
                         "ref": "path-1"}]}}

    def staged(self, goal):
        return self.harness.staged(goal, {"scene": self.scene})

    def test_exactly_subject_intent_demonstration_and_subject_frame(self):
        self.assertEqual(self.staged(self.goal)["goal"], self.goal)

    def test_page_frame_is_refused_for_performing(self):
        # Referring to a page-frame course stays supported; performing one
        # does not, because its start can be far from the sticker.
        self.assertFalse(self.staged({**self.goal, "frame": "page"})["ok"])
        referring = {**self.goal, "intent": "reference-trajectory",
                     "frame": "page"}
        self.assertTrue(self.staged(referring)["ok"])

    def test_frame_is_required_with_no_default_and_no_guessing(self):
        for change in ({"frame": None}, {"frame": "auto"},
                       {"frame": "sticker"}, {"frame": ""}):
            with self.subTest(change=change):
                self.assertFalse(self.staged({**self.goal, **change})["ok"])
        bare = dict(self.goal)
        del bare["frame"]
        self.assertFalse(self.staged(bare)["ok"])

    def test_no_other_field_is_accepted(self):
        for change in ({"target": {}}, {"behavior": "fly"}, {"samples": []},
                       {"keys": []}, {"scale": 1}, {"facing": "left"},
                       {"label": "dance"}, {"pattern": "pattern-1"},
                       {"steps": 3}, {"speed": 1}):
            with self.subTest(change=change):
                self.assertFalse(self.staged({**self.goal, **change})["ok"])

    def test_the_demonstration_must_be_current_or_the_exact_pending_pair(self):
        self.scene["interaction"]["signals"] = []
        self.assertFalse(self.staged(self.goal)["ok"])
        self.scene["pendingReference"] = {
            "subject": "bird-1", "demonstration": "input-event-1",
            "kind": "page-path", "pathRef": "path-1"}
        self.assertTrue(self.staged(self.goal)["ok"])
        # Not some other event, not some other subject, not another kind.
        self.assertFalse(
            self.staged({**self.goal, "demonstration": "input-event-99"})["ok"])
        self.scene["stickers"].append({"id": "bird-2"})
        self.assertFalse(self.staged({**self.goal, "subject": "bird-2"})["ok"])
        self.scene["pendingReference"]["kind"] = "sticker-drag"
        self.assertFalse(self.staged(self.goal)["ok"])

    def test_fabricated_or_malformed_demonstrations_are_refused(self):
        for event in ("path-1", "input-event-0", "../path-1", "input-event",
                      "", None, 7):
            with self.subTest(event=event):
                self.assertFalse(
                    self.staged({**self.goal, "demonstration": event})["ok"])

    def test_an_invisible_subject_cannot_be_asked_to_perform(self):
        self.scene["stickers"] = []
        self.assertFalse(self.staged(self.goal)["ok"])

    def test_other_intents_do_not_gain_a_frame(self):
        for intent in ("bind-demonstration", "animate", "move",
                       "remember-pattern", "perform-pattern"):
            with self.subTest(intent=intent):
                self.assertFalse(
                    self.staged({**self.goal, "intent": intent})["ok"])


# ---------------------------------------------------------------------------
# End to end, with OmegaJev choosing
# ---------------------------------------------------------------------------

class PoweredShortPath(PoweredCase):

    def test_a_short_course_is_followed_to_completion(self):
        result = self.short_east()["jev"]
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"], "completed")
        self.assertIsNone(result["execution"]["stoppedReason"])
        self.assertEqual(result["execution"]["mode"], "agent")
        self.assertGreater(result["acceptedSteps"], 0)
        self.assertEqual(result["decisions"], result["submittedSteps"])
        self.assertTrue(self.jev.calls)
        self.assertLess(
            tx.distance(self.at(), (.5 + .18, .5)), MOVE_STEP)

    def test_every_accepted_step_is_an_ordinary_kernel_move_receipt(self):
        vocabulary = (ALL_ACTIONS, MUTATING_ACTIONS)
        before = len(self.kernel.receipts)
        result = self.short_east()["jev"]
        receipts = self.kernel.receipts[before:]
        self.assertEqual(len(receipts), result["submittedSteps"])
        for receipt in receipts:
            self.assertEqual(receipt.action, MOVE_STICKER)
            # The child originated the request, OmegaLLM translated it into a
            # bounded goal, OmegaJev selected this key, the kernel decided.
            self.assertEqual(receipt.actor, HUMAN_ID)
            self.assertEqual(receipt.requested_by, HUMAN_ID)
            self.assertEqual(receipt.translated_by, OMEGA_LLM_ID)
            self.assertEqual(receipt.selected_by, OMEGA_JEV_ID)
        self.assertEqual(vocabulary, (ALL_ACTIONS, MUTATING_ACTIONS))

    def test_the_reply_and_response_carry_no_raw_geometry(self):
        response = self.short_east()
        self.assertTrue(response["reply"])
        encoded = json.dumps(response)
        self.assertNotIn("samples", encoded)
        self.assertNotIn("sourceSamples", encoded)
        self.assertNotIn("resolvedSamples", encoded)
        # A bounded summary of the reference is present for debugging.
        self.assertIn("sampleCount", response["jev"]["reference"])

    def test_a_page_frame_goal_is_refused_by_the_host_too(self):
        self.place(x=.5, y=.5)
        result = self.perform([(.2, .5), (.3, .5)], frame="page")["jev"]
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid-trajectory-goal")
        self.assertEqual(self.jev.calls, [])
        self.assertEqual(len(self.bridge.trajectory_executions), 0)

    def test_performing_consumes_pending_carry_without_renewing_it(self):
        self.place(x=.5, y=.5)
        event = self.drawn([(.2, .5), (.26, .5), (.32, .5)])
        bound = self.say({"subject": "bird-1", "intent": "bind-demonstration",
                          "demonstration": event}, "that one")
        self.assertTrue(bound["jev"]["ok"], bound)
        self.assertIsNotNone(self.bridge.pending_reference)
        # A later turn performs the carried referent...
        result = self.say({"subject": "bird-1",
                           "intent": "perform-trajectory",
                           "demonstration": event, "frame": "subject"},
                          "now do it")["jev"]
        self.assertTrue(result["ok"], result)
        # ...and the carry is spent, not renewed.
        self.assertIsNone(self.bridge.pending_reference)

    def test_the_attempt_uses_its_own_frozen_reference(self):
        self.place(x=.5, y=.5)
        self.place("bird-2", x=.2, y=.8)
        seen = []
        original = self.controller.follow_trajectory

        def watched(reference, **kwargs):
            seen.append(reference)
            # Replacing the inspection slot mid-attempt must change nothing.
            self.bridge.last_trajectory_reference = None
            return original(reference, **kwargs)

        with patch.object(self.controller, "follow_trajectory",
                          side_effect=watched):
            result = self.perform(
                [(.2, .5), (.26, .5), (.32, .5)])["jev"]
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].frame, "subject")
        self.assertEqual(result["execution"]["pathRef"], seen[0].path_ref)


# ---------------------------------------------------------------------------
# What OmegaJev is and is not shown
# ---------------------------------------------------------------------------

class BoundedJevContext(PoweredCase):

    def test_the_decision_context_is_typed_and_is_not_a_semantic_goal(self):
        self.short_east()
        for call in self.jev.calls:
            self.assertEqual(set(call["goal"]), {"subject", "intent"})
            self.assertEqual(call["goal"]["intent"], TRAJECTORY_DECISION)
            self.assertEqual(call["goal"]["subject"], "bird-1")

    def test_ordinary_jev_goal_vocabulary_is_untouched(self):
        import jev_controller
        # `frame` never becomes an acceptable ordinary goal field, and the
        # OmegaLLM performing intent is not an ordinary Jev intent.
        self.assertNotIn("frame", jev_controller._ALLOWED_GOAL_FIELDS)
        self.assertNotIn("perform-trajectory", jev_controller._ALLOWED_INTENTS)
        self.assertNotIn(TRAJECTORY_DECISION, jev_controller._ALLOWED_INTENTS)
        _, error = self.controller.normalize_goal(
            {"subject": "bird-1", "intent": "animate", "frame": "subject"})
        self.assertEqual(error, "unknown-jev-goal-field")

    def test_the_scene_carries_only_the_bounded_trajectory_facts(self):
        self.short_east()
        call = self.jev.calls[0]
        self.assertEqual(set(call["scene"]), {
            "revision", "principal", "subject", "available_actions",
            "trajectory"})
        self.assertEqual(set(call["scene"]["trajectory"]), {
            "pathRef", "frame", "progressIndex", "waypointCount", "remaining",
            "position", "objective", "error", "next"})
        self.assertEqual(set(call["scene"]["subject"]), {"id", "x", "y"})
        self.assertLessEqual(len(call["scene"]["trajectory"]["next"]), 2)

    def test_no_sample_array_or_history_reaches_either_model(self):
        self.short_east()
        # No sample array under any spelling, to either loop. Checked as
        # substrings because a nested array would show up whatever its key.
        for payload in (json.dumps(self.jev.calls),
                        json.dumps(self.llm.scenes)):
            for leak in ("samples", "sourceSamples", "resolvedSamples",
                         "dragTrace", "transcript", "episodes"):
                self.assertNotIn(leak, payload, leak)
        drawn = [(p.x, p.y) for p
                 in self.bridge.last_trajectory_reference.resolved_samples]
        for call in self.jev.calls:
            trajectory = call["scene"]["trajectory"]
            # At most a two-point lookahead, never the retained course, so
            # nothing here could reconstruct what the child drew.
            self.assertLessEqual(len(trajectory["next"]), 2)
            self.assertLess(len(trajectory["next"]),
                            trajectory["waypointCount"])
            offered = {(p["x"], p["y"]) for p in trajectory["next"]}
            offered.add((trajectory["objective"]["x"],
                         trajectory["objective"]["y"]))
            self.assertLess(len(offered), len(drawn))
            # And no structure in the scene is an array of retained points.
            self.assertNotIn("sourceStart", json.dumps(call["scene"]))

    def test_jev_sees_exactly_the_current_finite_surface(self):
        self.short_east()
        for call in self.jev.calls:
            offered = set(call["actions"])
            self.assertEqual(offered, set(call["scene"]["available_actions"]))
            self.assertIn("NOOP", offered)
            for key in offered:
                self.assertTrue(key == "NOOP" or key.startswith("MOVE:bird-1:"),
                                key)
                self.assertFalse(key.startswith("ANIMATE:"), key)
                self.assertFalse(key.startswith("SCALE:"), key)
                self.assertFalse(key.startswith("FACE:"), key)

    def test_each_decision_is_made_against_a_freshly_built_current_table(self):
        self.short_east()
        calls = self.jev.calls
        self.assertGreater(len(calls), 1)
        revisions = [c["scene"]["revision"] for c in calls]
        positions = [(c["scene"]["subject"]["x"], c["scene"]["subject"]["y"])
                     for c in calls]
        progress = [c["scene"]["trajectory"]["progressIndex"] for c in calls]
        # The world advances between decisions and Jev is told so.
        self.assertEqual(revisions, sorted(revisions))
        self.assertEqual(len(set(revisions)), len(revisions))
        self.assertNotEqual(positions[0], positions[-1])
        self.assertEqual(progress, sorted(progress))
        # Each decision's revision matches the kernel state its own table was
        # built from, which is what its proposal is then submitted against.
        record = self.bridge.trajectory_executions.records()[-1]
        submitted = [s.receipt["basedOnRevision"] for s in record.steps]
        self.assertEqual(submitted, revisions[:len(submitted)])

    def test_turn_numbering_and_cap_are_reported_to_jev(self):
        self.short_east()
        turns = [c["turn"] for c in self.jev.calls]
        self.assertEqual(turns, list(range(1, len(turns) + 1)))
        for call in self.jev.calls:
            self.assertEqual(call["max_turns"], tx.MAX_AGENT_TRAJECTORY_STEPS)


# ---------------------------------------------------------------------------
# Bounded model spend
# ---------------------------------------------------------------------------

class AgentDecisionBudget(PoweredCase):

    def long_course(self):
        self.place(x=.2, y=.3)
        # A zigzag long enough to need far more motor steps than the agent
        # decision cap allows, while staying inside the page.
        points = [(round(.2 + .08 * i, 4), .3 if i % 2 == 0 else .7)
                  for i in range(8)]
        return self.perform(points)

    def test_the_agent_cap_stops_the_attempt_distinctly(self):
        result = self.long_course()["jev"]
        self.assertEqual(result["error"], "agent-step-budget-exhausted")
        self.assertEqual(result["result"], "partial")
        self.assertFalse(result["ok"])
        self.assertEqual(result["decisions"], tx.MAX_AGENT_TRAJECTORY_STEPS)
        self.assertEqual(len(self.jev.calls), tx.MAX_AGENT_TRAJECTORY_STEPS)
        self.assertGreater(result["acceptedSteps"], 0)

    def test_the_motor_cap_is_unchanged_and_was_not_the_limit(self):
        result = self.long_course()["jev"]
        self.assertEqual(tx.MAX_TRAJECTORY_STEPS, 48)
        self.assertEqual(tx.MAX_AGENT_TRAJECTORY_STEPS, 12)
        # The motor budget still comes from geometry and is larger here, so
        # the two caps are visibly different bounds.
        self.assertGreater(result["plannedSteps"],
                           tx.MAX_AGENT_TRAJECTORY_STEPS)
        self.assertNotEqual(result["error"], "step-budget-exhausted")

    def test_the_motor_cap_still_wins_when_it_is_the_smaller_bound(self):
        # A geometry/control bound and a model-resource bound report
        # differently, so a generous agent cap must not mask the motor cap.
        self.place(x=.5, y=.5)
        points = [(.5, .5)]
        for i in range(15):
            points.append((round(.5 + .02 * (i + 1), 4),
                           .15 if i % 2 == 0 else .85))
        event = self.drawn(points)
        self.llm.goal = {"subject": "bird-1", "intent": "reference-trajectory",
                         "demonstration": event, "frame": "subject"}
        self.assertTrue(self.bridge.converse({"text": "that"})["jev"]["ok"])
        reference = self.bridge.last_trajectory_reference
        result = self.controller.follow_trajectory_with_jev(
            reference, actor=HUMAN_ID, command_prefix="both",
            requested_by=HUMAN_ID, max_decisions=100)
        self.assertEqual(result["error"], "step-budget-exhausted")
        self.assertEqual(result["submittedSteps"], tx.MAX_TRAJECTORY_STEPS)

    def test_a_short_course_never_reaches_either_cap(self):
        result = self.short_east()["jev"]
        self.assertEqual(result["result"], "completed")
        self.assertLess(result["decisions"], tx.MAX_AGENT_TRAJECTORY_STEPS)
        self.assertLess(result["submittedSteps"], result["plannedSteps"])


# ---------------------------------------------------------------------------
# Selector outcomes stay distinct
# ---------------------------------------------------------------------------

class SelectorOutcomes(PoweredCase):

    def test_jev_declining_is_recorded_as_jev_noop_and_is_not_completion(self):
        self.jev.answer = {"ok": True, "choice": "NOOP"}
        result = self.short_east()["jev"]
        self.assertEqual(result["error"], "jev-noop")
        self.assertNotEqual(result["result"], "completed")
        self.assertEqual(result["result"], "stopped")
        self.assertFalse(result["ok"])
        # It declined once and was not asked again.
        self.assertEqual(len(self.jev.calls), 1)
        self.assertEqual(result["decisions"], 1)
        self.assertEqual(result["execution"]["steps"], [])
        # Not confused with the host's own stop conditions.
        for other in ("trajectory-objective-unreachable",
                      "step-budget-exhausted", "agent-step-budget-exhausted",
                      "selector-declined"):
            self.assertNotEqual(result["error"], other)

    def test_a_runtime_that_raises_is_a_failure_not_a_decision(self):
        self.jev.fail = True
        result = self.short_east()["jev"]
        self.assertEqual(result["error"], "jev-selection-failed")
        self.assertEqual(result["result"], "stopped")
        self.assertNotEqual(result["error"], "jev-noop")
        self.assertEqual(result["execution"]["selectorDetail"],
                         "jev-runtime-raised")
        self.assertEqual(result["execution"]["steps"], [])

    def test_a_runtime_that_answers_badly_is_also_a_failure(self):
        self.jev.answer = {"ok": False, "error": "model-overloaded"}
        result = self.short_east()["jev"]
        self.assertEqual(result["error"], "jev-selection-failed")
        self.assertNotEqual(result["error"], "jev-noop")
        # Provider detail is kept, bounded, and not interpreted.
        self.assertEqual(result["execution"]["selectorDetail"],
                         "model-overloaded")

    def test_selector_detail_is_bounded(self):
        self.jev.answer = {"ok": False, "error": "x" * 500}
        result = self.short_east()["jev"]
        self.assertEqual(len(result["execution"]["selectorDetail"]),
                         tx.MAX_SELECTOR_DETAIL)

    def test_a_disconnected_runtime_is_reported_before_anything_starts(self):
        self.jev._available = False
        result = self.short_east()["jev"]
        self.assertEqual(result["error"], "jev-unavailable")
        self.assertEqual(self.jev.calls, [])
        self.assertEqual(len(self.bridge.trajectory_executions), 0)

    def test_an_unknown_key_is_never_submitted_to_the_kernel(self):
        self.jev.answer = {"ok": True, "choice": "MOVE:bird-1:TELEPORT"}
        before = len(self.kernel.receipts)
        result = self.short_east()["jev"]
        self.assertEqual(result["error"], "unknown-selector-choice")
        self.assertEqual(result["result"], "stopped")
        self.assertEqual(result["execution"]["steps"], [])
        self.assertEqual(len(self.kernel.receipts), before)
        self.assertEqual(self.at(), (.5, .5))

    def test_a_key_for_another_sticker_is_also_refused(self):
        self.place("bird-2", x=.2, y=.2)
        self.jev.answer = {"ok": True, "choice": "MOVE:bird-2:STEP-E"}
        result = self.short_east()["jev"]
        self.assertEqual(result["error"], "unknown-selector-choice")
        self.assertEqual(self.at("bird-2"), (.2, .2))

    def test_jev_cannot_supply_coordinates(self):
        self.jev.answer = {"ok": True, "choice": "MOVE:bird-1:STEP-E",
                           "x": 0.99, "y": 0.01}
        result = self.short_east()["jev"]
        step = result["execution"]["steps"][0]
        # The host built the command behind the key; the extra fields are
        # simply not part of the contract and cannot reach the kernel.
        self.assertEqual(step["choice"], "MOVE:bird-1:STEP-E")
        self.assertEqual(step["receipt"]["accepted"], True)
        self.assertNotEqual(self.at(), (0.99, 0.01))


# ---------------------------------------------------------------------------
# The child outranks the chooser
# ---------------------------------------------------------------------------

class HumanOutranksJev(PoweredCase):

    def course(self):
        self.place(x=.5, y=.5)
        self.place("bird-2", x=.2, y=.2)
        return [(.1, .5), (.16, .5), (.22, .5), (.28, .5)]

    def while_jev_thinks(self, disturb):
        """Disturb the world once, during an OmegaJev decision."""
        fired = []
        original = self.jev.choose

        def choose(**request):
            if not fired:
                fired.append(disturb())
            return original(**request)

        points = self.course()
        with patch.object(self.jev, "choose", side_effect=choose):
            result = self.perform(points)["jev"]
        return result, (fired[0] if fired else None)

    def child_drag(self, x=.15, y=.85, sticker="bird-1"):
        landed = []
        thread = threading.Thread(target=lambda: landed.append(
            self.bridge.propose_move({
                "sticker": sticker, "command_id": "child-drag",
                "point": {"x": x, "y": y}})))
        thread.start()
        thread.join(5)
        self.assertFalse(thread.is_alive(), "the child's gesture blocked")
        return landed[0]

    def test_a_child_moving_the_subject_supersedes_the_powered_attempt(self):
        result, child = self.while_jev_thinks(self.child_drag)
        self.assertTrue(child["ok"], child)
        self.assertEqual(self.at(), (.15, .85))
        last = result["execution"]["steps"][-1]
        self.assertTrue(last["submitted"])
        self.assertFalse(last["receipt"]["accepted"])
        self.assertEqual(last["receipt"]["reason"], "stale-revision")
        self.assertTrue(last["superseded"])
        self.assertEqual(result["error"], "superseded-by-human")
        # No retry, no re-aim: the child's position is final.
        self.assertEqual(self.at(), (.15, .85))
        self.assertEqual(result["execution"]["mode"], "agent")

    def test_another_controller_moving_the_subject_is_not_supersession(self):
        def other_controller():
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

        result, receipt = self.while_jev_thinks(other_controller)
        self.assertTrue(receipt.accepted)
        last = result["execution"]["steps"][-1]
        self.assertEqual(last["receipt"]["reason"], "stale-revision")
        self.assertFalse(last["superseded"])
        self.assertEqual(result["error"], "world-changed")
        self.assertNotEqual(result["error"], "superseded-by-human")

    def test_a_child_moving_a_different_sticker_does_not_supersede(self):
        result, other = self.while_jev_thinks(
            lambda: self.child_drag(.3, .3, sticker="bird-2"))
        self.assertTrue(other["ok"], other)
        self.assertEqual(result["result"], "completed")
        self.assertIsNone(result["execution"]["stoppedReason"])
        for step in result["execution"]["steps"]:
            self.assertFalse(step["superseded"])
        self.assertEqual(self.at("bird-2"), (.3, .3))

    def test_no_world_lock_is_held_while_jev_thinks(self):
        observed = {}
        original = self.jev.choose

        def choose(**request):
            observed["own"] = self.bridge._world_lock._is_owned()
            acquired = []

            def probe():
                got = self.bridge._world_lock.acquire(timeout=5)
                acquired.append(got)
                if got:
                    self.bridge._world_lock.release()

            thread = threading.Thread(target=probe)
            thread.start()
            thread.join(5)
            observed["free"] = bool(acquired and acquired[0])
            return original(**request)

        with patch.object(self.jev, "choose", side_effect=choose):
            result = self.short_east()["jev"]
        self.assertTrue(result["ok"], result)
        self.assertIs(observed["own"], False)
        self.assertIs(observed["free"], True)

    def test_a_child_gesture_completes_while_jev_is_still_choosing(self):
        moved = {}
        original = self.jev.choose

        def choose(**request):
            if not moved:
                moved["result"] = self.child_drag(.3, .3, sticker="bird-2")
            return original(**request)

        self.place("bird-2", x=.2, y=.2)
        with patch.object(self.jev, "choose", side_effect=choose):
            self.short_east()
        self.assertTrue(moved["result"]["ok"])
        self.assertEqual(self.at("bird-2"), (.3, .3))


# ---------------------------------------------------------------------------
# The chooser is the independent variable
# ---------------------------------------------------------------------------

class MechanicalAndPoweredAreComparable(PoweredCase):

    def both(self):
        """Run the same frozen reference mechanically and then powered."""
        self.place(x=.5, y=.5)
        event = self.drawn([(.2, .5), (.26, .5), (.32, .5), (.38, .5)])
        self.llm.goal = {"subject": "bird-1", "intent": "reference-trajectory",
                         "demonstration": event, "frame": "subject"}
        self.assertTrue(self.bridge.converse({"text": "that"})["jev"]["ok"])
        reference = self.bridge.last_trajectory_reference
        mechanical = self.controller.follow_trajectory(
            reference, actor=HUMAN_ID, command_prefix="mech",
            requested_by=HUMAN_ID)
        # Put the subject back so the powered run faces the same problem.
        self.bridge.propose_move({
            "sticker": "bird-1", "command_id": "reset",
            "point": {"x": reference.subject_start.x,
                      "y": reference.subject_start.y}})
        powered = self.controller.follow_trajectory_with_jev(
            reference, actor=HUMAN_ID, command_prefix="jev",
            requested_by=HUMAN_ID)
        return reference, mechanical, powered

    def test_both_paths_share_progress_completion_and_result_vocabulary(self):
        reference, mechanical, powered = self.both()
        waypoints = len(reference.resolved_samples)
        for label, result in (("mechanical", mechanical), ("powered", powered)):
            with self.subTest(label=label):
                self.assertEqual(result["result"], "completed")
                self.assertIsNone(result["execution"]["stoppedReason"])
                self.assertEqual(result["progressReached"], waypoints - 1)
                self.assertEqual(result["execution"]["waypointCount"],
                                 waypoints)
                # Same geometry, so the same host-derived motor budget.
                self.assertEqual(result["plannedSteps"],
                                 mechanical["plannedSteps"])
                # Objective indices advance monotonically on both.
                indices = [s["objectiveIndex"]
                           for s in result["execution"]["steps"]]
                self.assertEqual(indices, sorted(indices))
                self.assertEqual(result["execution"]["pathRef"],
                                 reference.path_ref)

    def test_only_the_mode_and_attribution_distinguish_the_records(self):
        _, mechanical, powered = self.both()
        self.assertEqual(mechanical["execution"]["mode"], "mechanical")
        self.assertEqual(powered["execution"]["mode"], "agent")
        # Identical record shape, so the two are directly comparable.
        self.assertEqual(set(mechanical["execution"]),
                         set(powered["execution"]))
        self.assertEqual(set(mechanical), set(powered))
        for step in (mechanical["execution"]["steps"][0],
                     powered["execution"]["steps"][0]):
            self.assertEqual(set(step), {
                "index", "objectiveIndex", "objective", "submitted", "choice",
                "receipt", "unavailableReason", "superseded"})

    def test_the_legal_surface_is_built_the_same_way_for_both(self):
        # Capture what the mechanical selector was offered, then compare it
        # with what OmegaJev was offered for the same reference.
        mechanical_surfaces = []
        argmin = self.controller._mechanical_choice

        def watched(snapshot):
            mechanical_surfaces.append(set(snapshot["actions"]))
            return argmin(snapshot)

        self.place(x=.5, y=.5)
        event = self.drawn([(.2, .5), (.26, .5), (.32, .5), (.38, .5)])
        self.llm.goal = {"subject": "bird-1", "intent": "reference-trajectory",
                         "demonstration": event, "frame": "subject"}
        self.assertTrue(self.bridge.converse({"text": "that"})["jev"]["ok"])
        reference = self.bridge.last_trajectory_reference
        self.controller.follow_trajectory(
            reference, actor=HUMAN_ID, command_prefix="mech",
            requested_by=HUMAN_ID, select=watched)
        self.bridge.propose_move({
            "sticker": "bird-1", "command_id": "reset",
            "point": {"x": reference.subject_start.x,
                      "y": reference.subject_start.y}})
        self.controller.follow_trajectory_with_jev(
            reference, actor=HUMAN_ID, command_prefix="jev",
            requested_by=HUMAN_ID)

        powered_surfaces = [set(c["actions"]) for c in self.jev.calls]
        self.assertTrue(mechanical_surfaces and powered_surfaces)
        # Same construction: mid-page both offer the eight steps plus NOOP.
        self.assertEqual(mechanical_surfaces[0], powered_surfaces[0])
        for surface in mechanical_surfaces + powered_surfaces:
            self.assertIn("NOOP", surface)
            for key in surface - {"NOOP"}:
                self.assertTrue(key.startswith("MOVE:bird-1:"), key)

    def test_both_land_the_subject_on_the_final_retained_point(self):
        reference, mechanical, powered = self.both()
        last = reference.resolved_samples[-1]
        self.assertLess(tx.distance(self.at(), (last.x, last.y)), MOVE_STEP)
        self.assertGreater(mechanical["acceptedSteps"], 0)
        self.assertGreater(powered["acceptedSteps"], 0)

    def test_the_reference_survives_both_runs_unchanged(self):
        reference, _, _ = self.both()
        frozen = (reference.describe(), reference.resolved_samples,
                  reference.source_samples)
        self.assertEqual(
            (reference.describe(), reference.resolved_samples,
             reference.source_samples), frozen)


if __name__ == "__main__":
    unittest.main()
