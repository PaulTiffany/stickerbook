"""One admitted referent survives inference failure, not ordinary consumption."""

import json
import os
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge
import farm
import test_pattern_provider as provider_tests
from stickerbook_core import StickerInstance
from test_input_event import path
from test_interaction import FakeOmegaLLM, FakeOmegaJev


class SemanticCarry(unittest.TestCase):
    def setUp(self):
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge.Bridge(agent_runtime=self.llm, jev_runtime=self.jev)
        for subject in ("bird-1", "bird-2"):
            self.bridge.kernel.place_sticker(StickerInstance(
                subject, farm.HUMAN_ID, farm.HUMAN_ID, "bird", self.bridge.kernel.page))

    def capture(self):
        return self.bridge.observe_page_path(path())["sourceEvent"]

    def say(self, event=None, subject="bird-1", **extra):
        self.llm.goal = None if event is None else {
            "subject": subject, "intent": "bind-demonstration", "demonstration": event}
        return self.bridge.converse({"text": "Where Bird is.", "input_mode": "voice", **extra})

    def admit(self):
        event = self.capture()
        self.assertTrue(self.say(event)["jev"]["ok"])
        return self.bridge.pending_reference

    def test_admission_and_successful_unrelated_turn_consumption(self):
        pending = self.admit()
        self.assertEqual(pending.describe(), {
            "subject": "bird-1", "demonstration": "input-event-1",
            "pathRef": "path-1", "sourceEpisode": "episode-1",
            "principal": farm.HUMAN_ID, "page": "farm", "kind": "page-path"})
        self.say()
        self.assertEqual(self.llm.scenes[-1]["pendingReference"], pending.describe())
        self.assertEqual(self.llm.scenes[-1]["interaction"]["signals"], [])
        self.assertIsNone(self.bridge.pending_reference)
        self.say()
        self.assertNotIn("pendingReference", self.llm.scenes[-1])

    def test_exact_failure_then_retry_sequence_preserves_input_and_carry(self):
        pending = self.admit()
        before = (self.bridge.kernel.revision, len(self.bridge.kernel.receipts))
        with patch.object(self.llm, "converse", side_effect=RuntimeError("offline")) as call:
            self.assertFalse(self.say()["ok"])
            self.assertEqual(call.call_args.kwargs["scene"]["pendingReference"], pending.describe())
        self.assertEqual(len(self.bridge.interactions), 2)
        self.assertEqual(self.bridge.interactions.latest().utterance_text, "Where Bird is.")
        self.assertEqual(self.bridge.pending_reference, pending)
        self.say()
        self.assertEqual(self.llm.scenes[-1]["pendingReference"], pending.describe())
        self.assertIsNone(self.bridge.pending_reference)
        self.assertEqual(len(self.bridge.interactions), 3)
        self.assertEqual(before, (self.bridge.kernel.revision, len(self.bridge.kernel.receipts)))
        self.assertEqual(self.jev.calls, [])

    def test_invalid_and_failed_runtime_responses_preserve_carry(self):
        pending = self.admit()
        for response in (None, {}, {"ok": False, "error": "omegallm-failed-closed"},
                         {"ok": True, "reply": ""}, {"ok": True, "reply": 1}):
            with self.subTest(response=response), patch.object(self.llm, "converse", return_value=response):
                self.assertFalse(self.say()["ok"])
                self.assertEqual(self.bridge.pending_reference, pending)

    def test_new_binding_replaces_and_old_one_becomes_inadmissible(self):
        old = self.admit()
        new = self.capture()
        self.assertTrue(self.say(new)["jev"]["ok"])
        self.assertEqual(self.bridge.pending_reference.demonstration, new)
        self.assertEqual(self.bridge.pending_reference.source_episode, "episode-2")
        self.assertFalse(self.say(old.demonstration)["jev"]["ok"])
        self.assertIsNone(self.bridge.pending_reference)

    def test_explicit_pending_rebind_preserves_original_provenance(self):
        pending = self.admit()
        self.assertTrue(self.say(pending.demonstration)["jev"]["ok"])
        self.assertEqual(self.bridge.pending_reference, pending)
        self.assertEqual(self.llm.scenes[-1]["interaction"]["signals"], [])

    def test_current_and_pending_coexist_without_recency_selection(self):
        pending = self.admit()
        current = self.capture()
        self.assertTrue(self.say(pending.demonstration)["jev"]["ok"])
        scene = self.llm.scenes[-1]
        self.assertEqual(scene["pendingReference"]["demonstration"], pending.demonstration)
        self.assertEqual(scene["interaction"]["signals"][0]["sourceEvent"], current)
        self.assertEqual(self.bridge.pending_reference, pending)
        # Unselected current evidence does not become eligible on a later turn.
        self.assertFalse(self.say(current)["jev"]["ok"])

    def test_subject_cannot_be_changed_via_pending(self):
        pending = self.admit()
        self.assertFalse(self.say(pending.demonstration, subject="bird-2")["jev"]["ok"])
        self.assertIsNone(self.bridge.pending_reference)

    def test_failed_fabricated_and_old_bindings_do_not_admit(self):
        old = self.capture()
        self.say()
        for event in (old, "input-event-999", "path-1"):
            self.assertFalse(self.say(event)["jev"]["ok"])
            self.assertIsNone(self.bridge.pending_reference)

    def test_client_cannot_supply_or_rewrite_carry(self):
        pending = self.admit()
        forged = {**pending.describe(), "subject": "bird-2", "pathRef": "path-999"}
        self.say(pending.demonstration, pendingReference=forged)
        self.assertEqual(self.bridge.pending_reference, pending)
        self.assertEqual(self.llm.scenes[-1]["pendingReference"], pending.describe())

    def test_no_history_lookup_samples_or_mutation_for_carry(self):
        pending = self.admit()
        before = (self.bridge.kernel.revision, len(self.bridge.kernel.receipts))
        with patch.object(self.bridge.interactions, "get", side_effect=AssertionError("history lookup")), \
                patch.object(self.bridge.page_paths, "get", side_effect=AssertionError("historical trace lookup")):
            self.assertTrue(self.say(pending.demonstration)["jev"]["ok"])
        self.assertNotIn("samples", json.dumps(self.llm.scenes[-1]))
        self.assertEqual(before, (self.bridge.kernel.revision, len(self.bridge.kernel.receipts)))
        self.assertEqual(self.jev.calls, [])

    def test_double_click_bypasses_llm_and_does_not_consume_carry(self):
        pending = self.admit()
        calls = len(self.llm.scenes)
        self.bridge.animate({"sticker": "bird-1", "command_id": "double-click"})
        self.assertEqual(len(self.llm.scenes), calls)
        self.assertEqual(self.bridge.pending_reference, pending)

    def test_concurrent_linguistic_requests_consume_only_one_window(self):
        pending = self.admit()
        entered = threading.Event()
        second_waiting = threading.Event()
        release = threading.Event()
        lock = threading.Lock()
        scenes, results = [], []

        class ObservedLock:
            attempts = 0

            def __enter__(self):
                self.attempts += 1
                if self.attempts == 2:
                    second_waiting.set()
                lock.acquire()

            def __exit__(self, *args):
                lock.release()

        def runtime(**request):
            scenes.append(request["scene"])
            if len(scenes) == 1:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test release timed out")
            return {"ok": True, "reply": "Hello"}

        self.bridge._conversation_lock = ObservedLock()
        with patch.object(self.llm, "converse", side_effect=runtime):
            threads = [threading.Thread(target=lambda: results.append(
                self.bridge.converse({"text": "Hello"}))) for _ in range(2)]
            threads[0].start()
            self.assertTrue(entered.wait(5))
            threads[1].start()
            try:
                self.assertTrue(second_waiting.wait(5))
            finally:
                release.set()
                for thread in threads:
                    thread.join(5)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["ok"] for result in results))
        self.assertEqual(scenes[0]["pendingReference"], pending.describe())
        self.assertNotIn("pendingReference", scenes[1])


class ProviderCarry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        provider_tests.PatternProvider.setUpClass()

    def test_real_provider_admits_only_exposed_subject_event_pair(self):
        harness = provider_tests.PatternProvider()
        goal = {"subject": "bird-1", "intent": "bind-demonstration",
                "demonstration": "input-event-1"}
        scene = {"interaction": {"signals": []}, "pendingReference": {
            "subject": "bird-1", "demonstration": "input-event-1",
            "kind": "page-path", "pathRef": "path-1", "sourceEpisode": "episode-1",
            "principal": farm.HUMAN_ID, "page": "farm"}}
        self.assertTrue(harness.staged(goal, {"scene": scene})["ok"])
        for change in ({"subject": "bird-2"}, {"demonstration": "input-event-999"},
                       {"demonstration": "path-1"}, {"pathRef": "path-999"}):
            with self.subTest(change=change):
                self.assertFalse(harness.staged({**goal, **change}, {"scene": scene})["ok"])
        scene["pendingReference"]["kind"] = "sticker-drag"
        self.assertFalse(harness.staged(goal, {"scene": scene})["ok"])
