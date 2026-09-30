"""Real provider parsing/staging through host memory and finite Jev replay."""

import importlib.util
import json
import logging
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge
import farm
from stickerbook_core import StickerInstance
from test_interaction import FakeOmegaLLM
from test_remember_and_recall import FakeOmegaJev


class PatternProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        filename = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "llm", "omega_llm", "providers",
            "stickerbook_llm.py")
        providers = types.ModuleType("providers")
        providers.LLMProvider = type("LLMProvider", (), {})
        config = types.ModuleType("config")
        config.config_get_by_key = lambda *args: None
        logger = types.ModuleType("src.logger")
        logger.get_logger = logging.getLogger
        with patch.dict(sys.modules, {"providers": providers, "config": config,
                                      "src": types.ModuleType("src"),
                                      "src.logger": logger}):
            spec = importlib.util.spec_from_file_location("pattern_provider_test", filename)
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def setUp(self):
        self.jev = FakeOmegaJev()
        self.bridge = bridge.Bridge(jev_runtime=self.jev)
        self.bridge.kernel.place_sticker(StickerInstance(
            "frog-1", farm.HUMAN_ID, farm.HUMAN_ID, "frog", self.bridge.kernel.page,
            x=.5, y=.5, animation="rest"))

    def staged(self, goal, request=None):
        rpc = types.ModuleType("stickerbookrpc")
        rpc.current_request = Mock(return_value=request or {
            "text": "Remember that", "scene": {}, "inference": {}})
        rpc.stage_result = Mock(return_value=True)
        provider = self.module.StickerBookLLMProvider()
        transport = Mock()
        transport.complete.return_value = json.dumps({"reply": "Let me try.", "goal": goal})
        with patch.dict(sys.modules, {"stickerbookrpc": rpc}), \
                patch.object(self.module, "harden_llm_commands"), \
                patch.object(self.module, "clean_inference", return_value=("test", "test", {})), \
                patch.object(provider, "_transport", return_value=transport), \
                patch.object(self.module, "logger", Mock()):
            self.assertEqual(provider.chat("ignored Omega prompt"), "sb-return")
        return rpc.stage_result.call_args.args[0]

    def test_valid_shapes_match_host_normalization(self):
        for extra in ({"intent": "remember-pattern", "label": "  happy   dance  "},
                      {"intent": "perform-pattern", "label": "happy dance"},
                      {"intent": "perform-pattern", "pattern": "pattern-1"},
                      {"intent": "perform-pattern", "pattern": "pattern-1", "label": "dance"},
                      {"intent": "remember-pattern", "label": "x" * 48},
                      {"intent": "perform-pattern", "pattern": "x" * 64}):
            with self.subTest(extra=extra):
                raw = {"subject": "frog-1", **extra}
                result = self.staged(raw)
                expected, error = self.bridge.jev_controller.normalize_goal(raw)
                self.assertIsNone(error)
                self.assertTrue(result["ok"])
                self.assertEqual(result["goal"], expected)

    def test_invalid_labels_fail_closed_in_real_chat(self):
        for label in (None, "", "  ", "x" * 49, "MOVE:frog-1:STEP-E",
                      "happy\ndance", "happy\rdance", "happy\tdance", 7, []):
            with self.subTest(label=label):
                result = self.staged({"subject": "frog-1", "intent": "remember-pattern",
                                      "label": label})
                self.assertEqual(result, {"ok": False, "error": "omegallm-failed-closed",
                                          "reason": "invalid-semantic-response"})

    def test_native_recall_and_teaching_use_only_offered_experience(self):
        rpc = types.ModuleType('stickerbookrpc')
        rpc.current_request = Mock(return_value={'text': 'I like that curve.',
            'scene': {'page': {'id': 'farm'}, 'recentExperiences': [{'id': 'accepted-1'}]}, 'inference': {}})
        rpc.recall_memory = Mock(return_value=[{'kind': 'conversation', 'child': 'Call me River.'}])
        rpc.remember_conversation = Mock()
        rpc.stage_result = Mock(return_value=True)
        provider = self.module.StickerBookLLMProvider()
        transport = Mock()
        response = {'reply': 'Thanks River.', 'teaching': {'experience': 'accepted-1',
                    'valence': 'positive', 'lesson': 'Likes gentle curves.'}}
        with patch.dict(sys.modules, {'stickerbookrpc': rpc}), \
                patch.object(self.module, 'harden_llm_commands'), \
                patch.object(self.module, 'clean_inference', return_value=('test', 'test', {})), \
                patch.object(provider, '_transport', return_value=transport):
            transport.complete.return_value = json.dumps(response)
            provider.chat('ignored raw history')
            self.assertEqual(rpc.stage_result.call_args.args[0]['teaching'], response['teaching'])
            rpc.remember_conversation.assert_called_once_with('farm', 'I like that curve.', 'Thanks River.')
            self.assertIn('River', str(transport.complete.call_args))
            response['teaching']['experience'] = 'invented'
            transport.complete.return_value = json.dumps(response)
            provider.chat('ignored raw history')
            self.assertEqual(rpc.stage_result.call_args.args[0]['reason'], 'unknown-teaching-experience')
            self.assertEqual(rpc.remember_conversation.call_count, 1)

    def test_sponsored_completion_budget_and_empty_response_diagnostics(self):
        transport = self.module.OpenAICompatibleTransport('http://unused', 'ASI_API_KEY', 40)
        with patch.object(transport, '_request', return_value={'choices':[{'message':{'content':'{"reply":"Hello"}'}}]}) as request, \
                patch.object(transport, '_token', return_value='test-placeholder'):
            transport.complete('minimax/minimax-m3', {'text':'hello','scene':{}},1200)
        payload = request.call_args.args[0]
        self.assertEqual(payload['reasoning_effort'],'low')
        self.assertEqual(payload['max_tokens'],4096)
        for finish, reason in [('length','inference-output-budget'), ('stop','inference-empty-content')]:
            with self.assertRaisesRegex(ValueError, reason):
                self.module._extract_content({'choices':[{'finish_reason':finish,'message':{'content':None}}]})

    def test_missing_and_invalid_pattern_references_fail_closed(self):
        for value in (None, "", "x" * 65, "ANIMATE:frog-1:hop", 8, {}):
            with self.subTest(value=value):
                self.assertFalse(self.staged({"subject": "frog-1",
                    "intent": "perform-pattern", "pattern": value})["ok"])
        for intent in ("remember-pattern", "perform-pattern"):
            self.assertFalse(self.staged({"subject": "frog-1", "intent": intent})["ok"])

    def test_steps_geometry_and_control_fields_cannot_enter_pattern_goal(self):
        for intent in ("remember-pattern", "perform-pattern"):
            for field, value in (("steps", []), ("key", "MOVE:frog-1:STEP-E"),
                                 ("samples", []), ("demonstration", "input-event-1"),
                                 ("target", {"kind": "point", "x": .5, "y": .5}),
                                 ("behavior", "hop"), ("scale", 1), ("facing", "left")):
                with self.subTest(intent=intent, field=field):
                    self.assertFalse(self.staged({"subject": "frog-1", "intent": intent,
                        "label": "dance", field: value})["ok"])

    def test_pattern_fields_do_not_expand_other_intents(self):
        for intent in ("animate", "move", "bind-demonstration"):
            self.assertFalse(self.staged({"subject": "frog-1", "intent": intent,
                                          "label": "dance"})["ok"])

    def install_provider_runtime(self, goal):
        test = self

        class Runtime(FakeOmegaLLM):
            def converse(self, **request):
                return test.staged(goal, request)

        self.bridge.agent_runtime = Runtime()
        self.bridge._inference_selection = self.bridge._default_inference_selection()

    def test_provider_to_host_remember_then_jev_perform(self):
        self.assertTrue(self.bridge.animate({"sticker": "frog-1", "command_id": "teach"})["ok"])
        before = (self.bridge.kernel.revision, len(self.bridge.kernel.receipts), len(self.jev.calls))
        self.install_provider_runtime({"subject": "frog-1", "intent": "remember-pattern",
                                       "label": "happy dance"})
        remembered = self.bridge.converse({"text": "Remember that as your happy dance"})["jev"]
        self.assertTrue(remembered["ok"], remembered)
        self.assertEqual(before, (self.bridge.kernel.revision,
                                  len(self.bridge.kernel.receipts), len(self.jev.calls)))
        # The just-played hop is not offered again while already active.
        # A real child move returns the sticker to rest before replay.
        moved = self.bridge.propose_move({"sticker": "frog-1", "command_id": "rest",
                                          "point": {"x": .55, "y": .5}})
        self.assertTrue(moved["ok"], moved)
        replay_receipts = len(self.bridge.kernel.receipts)
        self.install_provider_runtime({"subject": "frog-1", "intent": "perform-pattern",
                                       "label": "happy dance"})
        performed = self.bridge.converse({"text": "Do your happy dance"})["jev"]
        self.assertTrue(performed["ok"], performed)
        self.assertGreater(len(self.jev.calls), before[2])
        self.assertGreater(len(self.bridge.kernel.receipts), replay_receipts)
        for call in self.jev.calls:
            self.assertIn("NOOP", call["actions"])

    def test_host_still_rejects_unknown_memory_and_missing_history(self):
        for goal, error in (({"intent": "remember-pattern", "label": "dance"},
                              "no-accepted-pattern-steps"),
                             ({"intent": "perform-pattern", "label": "dance"},
                              "unknown-pattern"),
                             ({"intent": "perform-pattern", "pattern": "pattern-999"},
                              "unknown-pattern")):
            with self.subTest(goal=goal):
                self.install_provider_runtime({"subject": "frog-1", **goal})
                result = self.bridge.converse({"text": "dance"})["jev"]
                self.assertEqual(result["error"], error)
        self.assertEqual(self.jev.calls, [])


if __name__ == "__main__":
    unittest.main()
