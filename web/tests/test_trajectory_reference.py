"""Semantic frame selection and immutable host resolution, without motor use."""

from dataclasses import FrozenInstanceError, replace
import json
import os
import sys
import threading
import unittest
from unittest.mock import DEFAULT, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge
import farm
import interaction
import page_path
import test_pattern_provider as provider_tests
from stickerbook_core import ALL_ACTIONS, MUTATING_ACTIONS, StickerInstance
from test_interaction import FakeOmegaLLM, FakeOmegaJev


def observed_path():
    # Neither endpoint time is 0/1; equal times are legal observed evidence.
    return {"duration_ms": 850, "samples": [
        {"t": .15, "x": .2, "y": .4},
        {"t": .15, "x": .5, "y": .1},
        {"t": .6, "x": .7, "y": .6},
        {"t": .9, "x": .2, "y": .4},
    ]}


class TrajectoryReference(unittest.TestCase):
    def setUp(self):
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge.Bridge(agent_runtime=self.llm, jev_runtime=self.jev)
        self.kernel = self.bridge.kernel
        for subject in ("bird-1", "bird-2"):
            self.kernel.place_sticker(StickerInstance(
                subject, farm.HUMAN_ID, farm.HUMAN_ID, "bird", self.kernel.page,
                x=.9, y=.1, scale=1.1, facing="left"))

    def capture(self, body=None):
        return self.bridge.observe_page_path(body or observed_path())["sourceEvent"]

    def goal(self, event, frame="subject", subject="bird-1"):
        return {"subject": subject, "intent": "reference-trajectory",
                "demonstration": event, "frame": frame}

    def say(self, goal):
        self.llm.goal = goal
        return self.bridge.converse({"text": "Where Bird is.", "input_mode": "voice"})

    def bind(self):
        event = self.capture()
        self.assertTrue(self.say({"subject": "bird-1", "intent": "bind-demonstration",
                                  "demonstration": event})["jev"]["ok"])
        return event

    def move(self, command_id, x=.4, y=.5):
        result = self.bridge.propose_move({"sticker": "bird-1", "command_id": command_id,
                                           "point": {"x": x, "y": y}})
        self.assertTrue(result["ok"], result)

    def test_page_frame_copies_retained_points_without_subject_segment(self):
        event = self.capture()
        result = self.say(self.goal(event, "page"))["jev"]
        self.assertTrue(result["ok"], result)
        reference = self.bridge.last_trajectory_reference
        self.assertEqual(reference.resolved_samples, reference.source_samples)
        self.assertEqual(reference.source_samples, self.bridge.page_paths.get("path-1").samples)
        self.assertEqual(len(reference.resolved_samples), 4)
        self.assertEqual(reference.resolved_samples[0].x, .2)
        self.assertNotEqual(reference.source_start, reference.subject_start)
        self.assertEqual(result["result"], "resolved")

    def test_subject_translation_preserves_displacement_order_timing_and_offpage(self):
        event = self.capture()
        self.assertTrue(self.say(self.goal(event))["jev"]["ok"])
        reference = self.bridge.last_trajectory_reference
        self.assertEqual(reference.observed_duration_ms, 850)
        self.assertEqual([p.t for p in reference.resolved_samples], [.15, .15, .6, .9])
        for p, q in zip(reference.source_samples, reference.resolved_samples):
            self.assertAlmostEqual(q.x, .9 + (p.x - .2))
            self.assertAlmostEqual(q.y, .1 + (p.y - .4))
            self.assertAlmostEqual(q.x - reference.resolved_samples[0].x, p.x - .2)
            self.assertAlmostEqual(q.y - reference.resolved_samples[0].y, p.y - .4)
        self.assertAlmostEqual(reference.resolved_samples[1].x, 1.2)
        self.assertAlmostEqual(reference.resolved_samples[1].y, -.2)
        self.assertEqual(reference.resolved_samples[-1].x, .9)  # out-and-return retained

    def test_resolution_uses_position_after_inference_and_remains_stable(self):
        event = self.capture()
        source_revision = self.kernel.revision
        self.llm.goal = self.goal(event)
        converse = self.llm.converse

        def moved_during_inference(**request):
            self.move("during-inference", .4, .5)
            return converse(**request)

        with patch.object(self.llm, "converse", side_effect=moved_during_inference):
            self.bridge.converse({"text": "Start where Bird is"})
        reference = self.bridge.last_trajectory_reference
        self.assertEqual(reference.source_scene_revision, source_revision)
        self.assertEqual(reference.resolution_scene_revision, source_revision + 1)
        self.assertEqual((reference.subject_start.x, reference.subject_start.y), (.4, .5))
        frozen = reference.describe(), reference.resolved_samples
        self.move("after-resolution", .8, .8)
        self.assertEqual(frozen, (reference.describe(), reference.resolved_samples))
        with self.assertRaises(FrozenInstanceError):
            reference.resolved_samples[0].x = 0
        with self.assertRaises(FrozenInstanceError):
            reference.subject_start.x = 0

    def test_snapshot_excludes_concurrent_bridge_mutation(self):
        event = self.capture()
        self.llm.goal = self.goal(event)
        snapshot_entered, writer_waiting, release = (threading.Event() for _ in range(3))
        armed = threading.Event()
        underlying = self.bridge._world_lock
        original_view, original_converse = self.kernel.view, self.llm.converse
        results = []

        class ObservedLock:
            def __enter__(self):
                if threading.current_thread().name == "trajectory-writer":
                    writer_waiting.set()
                underlying.acquire()

            def __exit__(self, *args):
                underlying.release()

        def inference(**request):
            armed.set()
            return original_converse(**request)

        def held_view(principal):
            if armed.is_set():
                armed.clear()
                snapshot_entered.set()
                if not release.wait(5):
                    raise RuntimeError("snapshot test timed out")
            return original_view(principal)

        self.bridge._world_lock = ObservedLock()
        initial_revision = self.kernel.revision
        with patch.object(self.llm, "converse", side_effect=inference), \
                patch.object(self.kernel, "view", side_effect=held_view):
            reader = threading.Thread(target=lambda: results.append(
                self.bridge.converse({"text": "Start here"})))
            writer = threading.Thread(name="trajectory-writer", target=lambda: results.append(
                self.bridge.propose_move({"sticker": "bird-1", "command_id": "concurrent",
                                          "point": {"x": .4, "y": .5}})))
            reader.start()
            try:
                self.assertTrue(snapshot_entered.wait(5))
                writer.start()
                self.assertTrue(writer_waiting.wait(5))
            finally:
                release.set()
                reader.join(5)
                if writer.ident is not None:
                    writer.join(5)
            self.assertFalse(reader.is_alive() or writer.is_alive())
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["ok"] for result in results))
        reference = self.bridge.last_trajectory_reference
        self.assertEqual(reference.resolution_scene_revision, initial_revision)
        self.assertEqual(reference.subject_start.x, .9)
        self.assertEqual(self.kernel.sticker("bird-1").x, .4)

    def test_pending_clarification_dereferences_only_admitted_path_and_consumes(self):
        event = self.bind()
        original_get = self.bridge.page_paths.get
        with patch.object(self.bridge.interactions, "get", side_effect=AssertionError("episode search")), \
                patch.object(self.bridge.page_paths, "get", wraps=original_get) as get:
            result = self.say(self.goal(event))
        self.assertTrue(result["jev"]["ok"], result)
        get.assert_called_once_with("path-1")
        self.assertEqual(self.llm.scenes[-1]["interaction"]["signals"], [])
        self.assertEqual(self.bridge.last_trajectory_reference.source_episode, "episode-1")
        self.assertIsNone(self.bridge.pending_reference)

    def test_current_and_pending_allow_either_model_selection(self):
        for choose_pending in (True, False):
            with self.subTest(choose_pending=choose_pending):
                pending = self.bind()
                current = self.capture()
                result = self.say(self.goal(pending if choose_pending else current))["jev"]
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["demonstration"], pending if choose_pending else current)
                self.assertEqual(self.llm.scenes[-1]["pendingReference"]["demonstration"], pending)
                self.assertEqual(self.llm.scenes[-1]["interaction"]["signals"][0]["sourceEvent"], current)
                self.assertIsNone(self.bridge.pending_reference)

    def test_wrong_pending_subject_event_or_frame_has_no_geometry_fallback(self):
        for change in ({"subject": "bird-2"}, {"demonstration": "input-event-999"},
                       {"demonstration": "../path-1"}, {"frame": "auto"}, {"samples": []}):
            with self.subTest(change=change):
                event = self.bind()
                with patch.object(self.bridge.interactions, "get", side_effect=AssertionError("history")), \
                        patch.object(self.bridge.page_paths, "get", side_effect=AssertionError("unadmitted read")):
                    result = self.say({**self.goal(event), **change})["jev"]
                self.assertFalse(result["ok"])
                self.assertIsNone(self.bridge.pending_reference)

    def test_evicted_pending_geometry_fails_and_resolved_copy_survives_eviction(self):
        event = self.bind()
        for _ in range(page_path.MAX_TRACES):
            self.capture()
        result = self.say(self.goal(event))["jev"]
        self.assertEqual(result["error"], "trajectory-evidence-unavailable")
        self.assertIsNone(self.bridge.last_trajectory_reference)
        current = self.capture()
        self.assertTrue(self.say(self.goal(current))["jev"]["ok"])
        reference = self.bridge.last_trajectory_reference
        source = reference.source_samples
        for _ in range(page_path.MAX_TRACES):
            self.capture()
        self.assertIsNone(self.bridge.page_paths.get(reference.path_ref))
        self.assertEqual(reference.source_samples, source)

    def test_principal_and_page_mismatch_fail(self):
        for changes in ({"principal": "human:other"}, {"page": "other-page"}):
            with self.subTest(changes=changes):
                event = self.bind()
                trace = self.bridge.page_paths.get(self.bridge.pending_reference.path_ref)
                with patch.object(self.bridge.page_paths, "get", return_value=replace(trace, **changes)):
                    result = self.say(self.goal(event))["jev"]
                self.assertEqual(result["error"], "trajectory-provenance-mismatch")

    def test_old_unrelated_event_and_sticker_drag_are_not_supported(self):
        event = self.capture()
        self.say(None)
        with patch.object(self.bridge.page_paths, "get", side_effect=AssertionError("history search")):
            self.assertFalse(self.say(self.goal(event))["jev"]["ok"])
        observed = self.bridge.observed_inputs.add(farm.HUMAN_ID,
            interaction.InputSignal(kind="sticker-drag", ref="drag-1"), issue_event=True)
        self.assertFalse(self.say(self.goal(observed.signal.source_event))["jev"]["ok"])

    def test_subject_must_be_visible_on_current_kernel_page(self):
        self.kernel.place_sticker(StickerInstance(
            "elsewhere", farm.HUMAN_ID, farm.HUMAN_ID, "bird", self.kernel.page + 1))
        for subject in ("missing", "elsewhere"):
            self.assertFalse(self.say(self.goal(self.capture(), subject=subject))["jev"]["ok"])

    def test_exact_host_fields_required_and_other_intents_do_not_gain_frame(self):
        for change in ({"frame": None}, {"frame": "unknown"}, {"target": {}},
                       {"behavior": "fly"}, {"samples": []}, {"keys": []},
                       {"scale": 1}, {"facing": "left"}):
            with self.subTest(change=change):
                self.assertFalse(self.say({**self.goal(self.capture()), **change})["jev"]["ok"])
        goal = self.goal(self.capture())
        del goal["frame"]
        self.assertFalse(self.say(goal)["jev"]["ok"])
        for intent in ("bind-demonstration", "animate", "remember-pattern"):
            self.assertFalse(self.say({**self.goal(self.capture()), "intent": intent})["jev"]["ok"])

    def test_no_jev_kernel_memory_or_scene_geometry_effect(self):
        event = self.capture()
        before = (self.kernel.revision, self.kernel.receipts, len(self.bridge.patterns),
                  len(self.bridge.replays), ALL_ACTIONS, MUTATING_ACTIONS)
        with patch.object(self.kernel, "propose", side_effect=AssertionError("mutation")), \
                patch.object(self.kernel, "propose_key", side_effect=AssertionError("action")), \
                patch.object(self.bridge.jev_controller, "run_semantic_goal", side_effect=AssertionError("Jev")):
            result = self.say(self.goal(event))
        self.assertTrue(result["jev"]["ok"], result)
        self.assertEqual(before, (self.kernel.revision, self.kernel.receipts, len(self.bridge.patterns),
                                  len(self.bridge.replays), ALL_ACTIONS, MUTATING_ACTIONS))
        self.assertEqual(self.jev.calls, [])
        self.assertNotIn("samples", json.dumps(result))
        self.say(None)
        self.assertNotIn("samples", json.dumps(self.llm.scenes))
        self.assertNotIn("reference", self.llm.scenes[-1])


class ProviderTrajectory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        provider_tests.PatternProvider.setUpClass()

    def setUp(self):
        self.harness = provider_tests.PatternProvider()
        self.goal = {"subject": "bird-1", "intent": "reference-trajectory",
                     "demonstration": "input-event-1", "frame": "page"}
        self.scene = {"stickers": [{"id": "bird-1"}], "interaction": {"signals": [
            {"kind": "page-path", "sourceEvent": "input-event-1", "ref": "path-1"}]}}

    def staged(self, goal):
        return self.harness.staged(goal, {"scene": self.scene})

    def test_both_frames_accepted_without_added_fields(self):
        for frame in ("page", "subject"):
            goal = {**self.goal, "frame": frame}
            self.assertEqual(self.staged(goal)["goal"], goal)

    def test_frame_and_exact_schema_enforced(self):
        for change in ({"frame": "auto"}, {"frame": "unknown"}, {"frame": None},
                       {"target": {}}, {"behavior": "fly"}, {"samples": []},
                       {"keys": []}, {"scale": 1}, {"facing": "left"},
                       {"demonstration": "path-1"}, {"demonstration": "input-event-0"}):
            with self.subTest(change=change):
                self.assertFalse(self.staged({**self.goal, **change})["ok"])
        del self.goal["frame"]
        self.assertFalse(self.staged(self.goal)["ok"])

    def test_other_intents_reject_frame(self):
        for intent in ("bind-demonstration", "animate", "move", "remember-pattern", "perform-pattern"):
            self.assertFalse(self.staged({**self.goal, "intent": intent})["ok"])

    def test_current_or_exact_pending_pair_only_and_visible_subject_required(self):
        self.scene["interaction"]["signals"] = []
        self.assertFalse(self.staged(self.goal)["ok"])
        self.scene["pendingReference"] = {"subject": "bird-1", "demonstration": "input-event-1",
                                          "kind": "page-path", "pathRef": "path-1"}
        self.assertTrue(self.staged(self.goal)["ok"])
        self.assertFalse(self.staged({**self.goal, "demonstration": "input-event-999"})["ok"])
        self.scene["stickers"].append({"id": "bird-2"})
        self.assertFalse(self.staged({**self.goal, "subject": "bird-2"})["ok"])
        self.scene["pendingReference"]["kind"] = "sticker-drag"
        self.assertFalse(self.staged(self.goal)["ok"])
        self.scene["pendingReference"]["kind"] = "page-path"
        self.scene["stickers"] = []
        self.assertFalse(self.staged(self.goal)["ok"])


class WorldLockScope(unittest.TestCase):
    """The world lock serializes world operations, never model think-time.

    The trajectory snapshot needs subject position, visibility and revision to
    be coherent with respect to bridge-mediated mutations. That requires the
    lock to be held briefly around each kernel read and each kernel proposal.
    It does NOT require holding it across OmegaLLM or OmegaJev inference, and
    doing so would queue a child's own gestures behind model latency.
    """

    def setUp(self):
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge.Bridge(agent_runtime=self.llm, jev_runtime=self.jev)
        self.kernel = self.bridge.kernel
        self.kernel.place_sticker(StickerInstance(
            "bird-1", farm.HUMAN_ID, farm.HUMAN_ID, "bird", self.kernel.page,
            x=.9, y=.1))

    def free_during(self, call):
        """Can an unrelated thread take the world lock while `call` runs?"""
        observed = []

        def probe():
            acquired = self.bridge._world_lock.acquire(timeout=5)
            observed.append(acquired)
            if acquired:
                self.bridge._world_lock.release()

        thread = threading.Thread(target=probe)
        thread.start()
        thread.join(5)
        observed.append(not thread.is_alive())
        call()
        return observed

    def test_omega_inference_does_not_hold_the_world_lock(self):
        # Both loops' think-time must run with the lock released: OmegaLLM's
        # already did, and a Jev-bound goal must not reintroduce it.
        self.llm.goal = {"subject": "bird-1", "intent": "animate"}
        seen = {}
        llm_converse, jev_choose = self.llm.converse, self.jev.choose

        def converse(**request):
            seen["llm"] = self.free_during(lambda: None)
            return llm_converse(**request)

        def choose(**request):
            seen["jev"] = self.free_during(lambda: None)
            return jev_choose(**request)

        with patch.object(self.llm, "converse", side_effect=converse), \
                patch.object(self.jev, "choose", side_effect=choose):
            result = self.bridge.converse({"text": "Flap your wings"})
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.jev.calls, "OmegaJev was not reached")
        self.assertEqual(seen, {"llm": [True, True], "jev": [True, True]})

    def test_double_click_does_not_hold_the_world_lock_across_the_jev_seam(self):
        # A child's double-tap reaches the same Jev seam without OmegaLLM.
        # available() is a network health probe and the choice is inference:
        # neither may run with the world lock held.
        seen = {}
        jev_available, jev_choose = self.jev.available, self.jev.choose

        def available():
            seen["available"] = self.free_during(lambda: None)
            return jev_available()

        def choose(**request):
            seen["choose"] = self.free_during(lambda: None)
            return jev_choose(**request)

        with patch.object(self.jev, "available", side_effect=available), \
                patch.object(self.jev, "choose", side_effect=choose):
            result = self.bridge.animate({"sticker": "bird-1",
                                          "command_id": "tap"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(seen, {"available": [True, True],
                                "choose": [True, True]})

    def test_a_child_gesture_is_not_queued_behind_jev_think_time(self):
        # A real human move must complete while OmegaJev is still choosing.
        self.llm.goal = {"subject": "bird-1", "intent": "animate"}
        moved = []
        jev_choose = self.jev.choose

        def choose(**request):
            thread = threading.Thread(target=lambda: moved.append(
                self.bridge.propose_move({
                    "sticker": "bird-1", "command_id": "during-jev",
                    "point": {"x": .3, "y": .3}})))
            thread.start()
            thread.join(5)
            moved.append(not thread.is_alive())
            return jev_choose(**request)

        with patch.object(self.jev, "choose", side_effect=choose):
            self.assertTrue(self.bridge.converse({"text": "Flap"})["ok"])
        self.assertEqual(len(moved), 2, "the gesture never finished")
        self.assertTrue(moved[0]["ok"] and moved[1])
        self.assertEqual(self.kernel.sticker("bird-1").x, .3)

    def test_kernel_mutations_and_coherent_reads_remain_serialized(self):
        # Narrowing scope must not leave a mutation path unprotected. Every
        # bridge-reachable kernel mutation, and the multi-object snapshot read
        # the trajectory frame needs, run with the world lock held.
        #
        # kernel.sticker() is deliberately exempt: it is one dict lookup
        # returning a frozen StickerInstance, so it cannot observe a
        # half-applied mutation, and requiring the lock for it would put the
        # lock back around validation that precedes model inference.
        mutations = ("propose", "propose_key", "begin_turn")
        coherent = ("view", "available_actions")
        witnessed = set()
        held = []

        def watch(name, original):
            def observe(*args, **kwargs):
                witnessed.add(name)
                held.append((name, self.bridge._world_lock._is_owned()))
                return original(*args, **kwargs)
            return observe

        targets = {name: getattr(self.kernel, name)
                   for name in mutations + coherent}
        with patch.multiple(self.kernel, **{
                name: DEFAULT for name in targets}) as mocks:
            for name, mock in mocks.items():
                mock.side_effect = watch(name, targets[name])
            self.llm.goal = {"subject": "bird-1", "intent": "animate"}
            self.assertTrue(self.bridge.converse({"text": "Flap"})["ok"])
            self.bridge.propose_move({"sticker": "bird-1", "command_id": "gesture",
                                      "point": {"x": .4, "y": .4}})
            self.bridge.animate({"sticker": "bird-1", "command_id": "tap"})
            self.bridge.place({"asset": "bird", "command_id": "place",
                               "point": {"x": .5, "y": .5}})
            self.bridge.remove({"sticker": "bird-1", "command_id": "rm"})
            self.bridge.state()
        # All three mutation entrypoints and both coherent reads were
        # actually exercised, so an empty result cannot pass vacuously.
        self.assertEqual(witnessed, set(mutations + coherent))
        unprotected = sorted({name for name, owned in held if not owned})
        self.assertEqual(unprotected, [])
