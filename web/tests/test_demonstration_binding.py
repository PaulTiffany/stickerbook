"""Bounded semantic reference to a current, host-observed page path."""

import importlib.util
import json
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge  # noqa: E402
import book  # noqa: E402
import farm  # noqa: E402
import interaction  # noqa: E402
from stickerbook_core import StickerInstance  # noqa: E402
from test_input_event import box, path  # noqa: E402
from test_interaction import FakeOmegaLLM, FakeOmegaJev  # noqa: E402


class Binding(unittest.TestCase):
    def setUp(self):
        self.kernel = farm.build_world()
        self.kernel.place_sticker(StickerInstance(
            "bird-1", farm.HUMAN_ID, farm.HUMAN_ID, "bird", book.DEFAULT_PAGE,
            x=.4, y=.4, animation="rest"))
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge.Bridge(self.kernel, agent_runtime=self.llm,
                                    jev_runtime=self.jev)

    def bind(self, event, reference=None):
        self.llm.goal = {"subject": "bird-1", "intent": "bind-demonstration",
                         "demonstration": event}
        request = {"text": "Make the bird go like this", "input_mode": "voice"}
        if reference is not None:
            request["reference"] = reference
        return self.bridge.converse(request)

    def test_one_current_event_binds_without_motor_or_world_effect(self):
        capture = self.bridge.observe_page_path(path())
        revision, receipts = self.kernel.revision, len(self.kernel.receipts)
        result = self.bind(capture["sourceEvent"],
                           box(source_event=capture["sourceEvent"]))
        self.assertEqual(result["jev"], {
            "ok": True, "result": "bound", "subject": "bird-1",
            "demonstration": "input-event-1", "pathRef": "path-1"})
        self.assertEqual(result["interaction"]["deicticReference"]["sourceEvent"],
                         "input-event-1")
        self.assertEqual(self.kernel.revision, revision)
        self.assertEqual(len(self.kernel.receipts), receipts)
        self.assertEqual(self.jev.calls, [])
        self.assertEqual(self.bridge._jev_counter, 0)
        scene = json.dumps(self.llm.scenes[-1])
        self.assertNotIn("samples", scene)
        self.assertNotIn('"circle"', scene)
        self.assertNotIn('"route"', scene)
        self.assertEqual(set(self.llm.goal),
                         {"subject", "intent", "demonstration"})

    def test_two_current_events_allow_model_to_choose_first_or_second(self):
        first = self.bridge.observe_page_path(path())
        second = self.bridge.observe_page_path(path((.1, .2), (.7, .6)))
        current_box = box((.1, .2), (.7, .6), second["sourceEvent"])
        # The current box points at the second path, but the model's first
        # choice is still admissible. The host does not choose by recency.
        first_result = self.bind(first["sourceEvent"], current_box)
        self.assertEqual(first_result["jev"]["pathRef"], "path-1")
        self.assertEqual(first_result["interaction"]["deicticReference"][
            "sourceEvent"], second["sourceEvent"])
        self.assertEqual([s["sourceEvent"] for s in
                          first_result["interaction"]["signals"]],
                         [first["sourceEvent"], second["sourceEvent"]])

        # On a fresh turn with two new paths, the model can choose the second.
        third = self.bridge.observe_page_path(path())
        fourth = self.bridge.observe_page_path(path((.1, .2), (.7, .6)))
        second_result = self.bind(fourth["sourceEvent"])
        self.assertEqual(second_result["jev"]["pathRef"], "path-4")
        self.assertNotEqual(third["sourceEvent"], fourth["sourceEvent"])

    def test_old_fabricated_malformed_and_unsupported_events_fail_closed(self):
        old = self.bridge.observe_page_path(path())
        self.bridge.converse({"text": "first turn"})
        self.bridge.observe_page_path(path())
        for event, error in ((old["sourceEvent"],
                              "demonstration-not-in-current-episode"),
                             ("input-event-999", "demonstration-not-in-current-episode"),
                             ("../input-event-2", "invalid-demonstration-reference")):
            with self.subTest(event=event):
                # Each turn needs a fresh current path for the admissibility
                # check to distinguish old/fabricated from absent context.
                self.bridge.observe_page_path(path())
                result = self.bind(event)
                self.assertEqual(result["jev"]["error"], error)
        unsupported = self.bridge.observed_inputs.add(farm.HUMAN_ID, interaction.InputSignal(
            kind="sticker-drag", ref="drag-1", subject="bird-1"),
            issue_event=True)
        result = self.bind(unsupported.signal.source_event)
        self.assertEqual(result["jev"]["error"],
                         "demonstration-not-in-current-episode")

    def test_extra_fields_and_unknown_subject_fail(self):
        event = self.bridge.observe_page_path(path())["sourceEvent"]
        self.llm.goal = {"subject": "bird-1", "intent": "bind-demonstration",
                         "demonstration": event, "samples": []}
        self.assertEqual(self.bridge.converse({"text": "like this"})["jev"]["error"],
                         "invalid-demonstration-goal")
        self.bridge.observe_page_path(path())
        self.llm.goal = {"subject": "missing", "intent": "bind-demonstration",
                         "demonstration": "input-event-2"}
        self.assertEqual(self.bridge.converse({"text": "like this"})["jev"]["error"],
                         "invalid-demonstration-subject")

    def test_failed_path_capture_cannot_be_bound(self):
        failed = self.bridge.observe_page_path({
            "duration_ms": 200, "samples": [{"t": 0, "x": "bad", "y": .2}]})
        self.assertFalse(failed["ok"])
        result = self.bind("input-event-1", box())
        self.assertEqual(result["interaction"]["signals"], [])
        self.assertNotIn("sourceEvent",
                         result["interaction"]["deicticReference"])
        self.assertEqual(result["jev"]["error"],
                         "demonstration-not-in-current-episode")
        self.assertEqual(self.jev.calls, [])

    def test_ordinary_goal_still_uses_jev_and_double_click_bypasses_llm(self):
        self.llm.goal = {"subject": "bird-1", "intent": "animate"}
        self.bridge.converse({"text": "Make bird dance"})
        self.assertTrue(self.jev.calls)
        calls = len(self.llm.scenes)
        self.bridge.animate({"sticker": "bird-1", "command_id": "double"})
        self.assertEqual(len(self.llm.scenes), calls)


class ProviderContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        filename = os.path.join(root, "llm", "omega_llm", "providers",
                                "stickerbook_llm.py")
        providers = types.ModuleType("providers")
        providers.LLMProvider = type("LLMProvider", (), {})
        config = types.ModuleType("config")
        config.config_get_by_key = lambda *args: None
        logger = types.ModuleType("src.logger")
        logger.get_logger = lambda *args: None
        with patch.dict(sys.modules, {"providers": providers, "config": config,
                                      "src": types.ModuleType("src"),
                                      "src.logger": logger}):
            spec = importlib.util.spec_from_file_location("stickerbook_llm_test", filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        cls.provider = module

    def test_current_page_path_only(self):
        goal = {"subject": "bird-1", "intent": "bind-demonstration",
                "demonstration": "input-event-2"}
        scene = {"interaction": {"signals": [
            {"kind": "page-path", "sourceEvent": "input-event-2"}]}}
        clean = self.provider.clean_goal(goal)
        self.provider.validate_demonstration_goal(clean, scene)
        for bad_scene in ({"interaction": {"signals": []}},
                          {"interaction": {"signals": [{
                              "kind": "sticker-drag",
                              "sourceEvent": "input-event-2"}]}},
                          {}):
            with self.subTest(scene=bad_scene), self.assertRaises(ValueError):
                self.provider.validate_demonstration_goal(clean, bad_scene)

    def test_malformed_unknown_and_geometry_fields_rejected(self):
        base = {"subject": "bird-1", "intent": "bind-demonstration",
                "demonstration": "input-event-1"}
        for changed in ({"demonstration": "input-event-0"},
                        {"demonstration": "input-event-" + "9" * 30},
                        {"demonstration": "path-1"},
                        {"samples": []}, {"classification": "circle"},
                        {"target": {"kind": "point", "x": .2, "y": .3}}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.provider.clean_goal({**base, **changed})
        with self.assertRaises(ValueError):
            self.provider.clean_goal({"subject": "bird-1", "intent": "move",
                                      "demonstration": "input-event-1"})


if __name__ == "__main__":
    unittest.main()
