"""Tests for the live Omega loopback adapters.

These tests intentionally use only a local fake HTTP server. They prove the
host-side boundary and fail-closed URL policy; they are not evidence that a
real Omega/OpenShell sandbox has run.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_runtime import (  # noqa: E402
    DisabledAgentRuntime, LoopbackAgentRuntime, agent_runtime_from_env,
)
from jev_runtime import (  # noqa: E402
    DisabledJevRuntime, LoopbackJevRuntime, jev_runtime_from_env,
)


class _Handler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, fmt, *args):
        return

    def _send(self, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        role = "omegallm" if self.server.server_address[1] == self.server.llm_port else "omegajev"
        if self.path == "/health":
            payload = {"ok": True, "role": role}
            if role == "omegallm":
                payload["inference_options"] = [{
                    "id": "asicloud",
                    "label": "Sponsored ASI Cloud",
                    "description": "Sponsored MiniMax.",
                    "default_model": "minimax/minimax-m3",
                    "model_locked": True,
                    "sponsored": True,
                    "available": True,
                }]
            return self._send(payload)
        self.send_error(404)

    def do_POST(self):
        size = int(self.headers.get("Content-Length") or "0")
        body = json.loads(self.rfile.read(size).decode("utf-8"))
        self.__class__.requests.append((self.path, body))
        if self.path == "/converse":
            return self._send({
                "ok": True,
                "reply": "The cow can hop.",
                "goal": {"subject": "cow-1", "intent": "animate"},
            })
        if self.path == "/choose":
            key = sorted(body["actions"])[0]
            return self._send({"ok": True, "choice": key})
        self.send_error(404)


class RuntimeAdapterCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.llm = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.jev = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        _Handler.requests = []
        _Handler.llm_port = cls.llm.server_address[1]
        cls.llm.llm_port = _Handler.llm_port
        cls.jev.llm_port = _Handler.llm_port
        cls.threads = []
        for server in (cls.llm, cls.jev):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)

    @classmethod
    def tearDownClass(cls):
        for server in (cls.llm, cls.jev):
            server.shutdown()
            server.server_close()

    def setUp(self):
        _Handler.requests.clear()

    def test_agent_runtime_is_loopback_only_and_carries_no_authority_object(self):
        url = "http://127.0.0.1:%d" % self.llm.server_address[1]
        runtime = LoopbackAgentRuntime(url)
        self.assertEqual(runtime.capabilities(), {
            "creator_agent": False,
            "conversational_agent": True,
        })
        self.assertEqual(runtime.inference_options()[0]["id"], "asicloud")
        result = runtime.converse(
            text="Make the cow hop.",
            principal="human:player",
            scene={"revision": 7, "stickers": [{"id": "cow-1"}]},
            reference={"kind": "point", "x": 0.2, "y": 0.3},
            inference={
                "provider": "asicloud",
                "model": "minimax/minimax-m3",
            },
        )
        self.assertTrue(result["ok"])
        path, body = _Handler.requests[-1]
        self.assertEqual(path, "/converse")
        self.assertEqual(body["principal"], "human:player")
        self.assertEqual(body["scene"]["revision"], 7)
        self.assertEqual(body["inference"], {
            "provider": "asicloud",
            "model": "minimax/minimax-m3",
        })
        self.assertNotIn("kernel", body)
        self.assertNotIn("credential", json.dumps(body).lower())

    def test_jev_runtime_transmits_only_goal_scene_finite_actions_and_turns(self):
        url = "http://127.0.0.1:%d" % self.jev.server_address[1]
        runtime = LoopbackJevRuntime(url)
        self.assertTrue(runtime.available())
        result = runtime.choose(
            goal={"subject": "cow-1", "intent": "animate"},
            scene={"revision": 2},
            actions={"NOOP": "Do nothing.", "ANIMATE:cow-1:hop": "Hop."},
            turn=1,
            max_turns=6,
        )
        self.assertTrue(result["ok"])
        self.assertIn(result["choice"], {"NOOP", "ANIMATE:cow-1:hop"})
        path, body = _Handler.requests[-1]
        self.assertEqual(path, "/choose")
        self.assertEqual(
            sorted(body),
            ["actions", "goal", "max_turns", "scene", "turn"],
        )

    def test_non_loopback_urls_are_refused_before_network_use(self):
        for cls in (LoopbackAgentRuntime, LoopbackJevRuntime):
            for url in (
                "https://127.0.0.1:8761",
                "http://example.com:8761",
                "http://127.0.0.1:8761/path",
                "http://user:pass@127.0.0.1:8761",
            ):
                with self.subTest(cls=cls.__name__, url=url):
                    with self.assertRaises(ValueError):
                        cls(url)

    def test_environment_factories_are_inert_without_explicit_urls(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(agent_runtime_from_env(), DisabledAgentRuntime)
            self.assertIsInstance(jev_runtime_from_env(), DisabledJevRuntime)

    def test_bad_environment_url_fails_closed(self):
        with mock.patch.dict(os.environ, {
            "STICKERBOOK_OMEGA_LLM_URL": "http://example.com:8761",
            "STICKERBOOK_OMEGA_JEV_URL": "http://example.com:8762",
        }, clear=True):
            self.assertIsInstance(agent_runtime_from_env(), DisabledAgentRuntime)
            self.assertIsInstance(jev_runtime_from_env(), DisabledJevRuntime)


if __name__ == "__main__":
    unittest.main()
