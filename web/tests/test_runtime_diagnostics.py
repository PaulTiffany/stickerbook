"""Safe loopback failure categories never reflect response bodies or exceptions."""
import io
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_runtime import AgentRuntimeError, LoopbackAgentRuntime
import bridge
from test_bridge import FakeAgentRuntime

class Diagnostics(unittest.TestCase):
    def test_transport_categories_do_not_expose_provider_text(self):
        runtime = LoopbackAgentRuntime('http://127.0.0.1:8761')
        cases = [(urllib.error.HTTPError(runtime.base_url, status, 'SECRET', {}, io.BytesIO(b'SECRET')), code)
                 for status, code in [(409, 'omegallm-busy'), (503, 'omegallm-not-ready'),
                                      (504, 'omegallm-timeout'), (500, 'omegallm-http-error')]]
        cases += [(TimeoutError('SECRET'), 'omegallm-timeout'),
                  (urllib.error.URLError(TimeoutError('SECRET')), 'omegallm-timeout'),
                  (urllib.error.URLError('SECRET'), 'omegallm-unavailable')]
        for error, code in cases:
            with self.subTest(code=code), patch('urllib.request.urlopen', side_effect=error):
                with self.assertRaises(AgentRuntimeError) as caught:
                    runtime._json('/converse', {})
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn('SECRET', str(caught.exception))

    def test_bridge_reports_stage_without_exception_detail(self):
        class Runtime(FakeAgentRuntime):
            def capabilities(self): return {'conversational_agent': True, 'creator_agent': False}
            def converse(self, **kwargs): raise AgentRuntimeError('omegallm-timeout')
        result = bridge.Bridge(agent_runtime=Runtime()).converse({'text': 'Hello'})
        self.assertEqual(result['error'], 'omegallm-timeout')
        self.assertEqual(result['diagnostic'], {'stage': 'omegallm-runtime', 'reason': 'omegallm-timeout'})

    def test_child_message_uses_friendly_mapping_and_dev_has_bounded_stage(self):
        source = (Path(__file__).resolve().parents[1] / 'static/app.js').read_text(encoding='utf-8')
        self.assertIn('messages[payload && payload.error]', source)
        self.assertIn('if (DEV && payload && payload.diagnostic)', source)
