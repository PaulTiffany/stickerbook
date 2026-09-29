"""Reproduce Omega's unregistered plugin execution plus provider import."""
import importlib
import importlib.util
import json
import logging
from pathlib import Path
import subprocess
import sys
import types
import unittest
import urllib.request
from unittest.mock import patch


RPC_DIR = Path(__file__).resolve().parents[2] / "runtime" / "omega"


class RpcIdentityCase(unittest.TestCase):
    def test_double_execution_shares_serving_state_for_both_roles(self):
        for role in ("omegajev", "omegallm"):
            with self.subTest(role=role):
                config = {"stickerbookRpcRole": role, "stickerbookRpcPort": 0}
                channels = types.ModuleType("channels")
                channels.CommChannel = object
                configuration = types.ModuleType("config")
                configuration.config_get_by_key = lambda key, default=None: config.get(key, default)
                logger = types.ModuleType("src.logger")
                logger.get_logger = logging.getLogger
                with patch.dict(sys.modules, {"channels": channels, "config": configuration,
                                              "src.logger": logger}):
                    sys.path.insert(0, str(RPC_DIR))
                    sys.modules.pop("stickerbookrpc", None)
                    sys.modules.pop("stickerbookrpc_state", None)
                    try:
                        spec = importlib.util.spec_from_file_location("omega_plugin_rpc", RPC_DIR / "stickerbookrpc.py")
                        serving = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(serving)
                        self.assertNotIn("omega_plugin_rpc", sys.modules)
                        channel = serving.StickerBookRPCChannel()
                        channel.start()
                        try:
                            provider = importlib.import_module("stickerbookrpc")
                            self.assertIsNot(provider, serving)
                            self.assertIs(provider.state, serving.state)
                            with self.assertRaisesRegex(RuntimeError, "role does not match"):
                                provider.set_provider_ready("omegallm" if role == "omegajev" else "omegajev")
                            provider.set_provider_ready(role)
                            self.assertEqual(serving.state.server.server_address[0], "127.0.0.1")
                            port = serving.state.server.server_address[1]
                            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
                                health = json.load(response)
                            self.assertTrue(health["ok"])
                            self.assertEqual(health["role"], role)
                            choice = {"goal": {}, "scene": {}, "actions": {"NOOP": "Do nothing this turn"},
                                      "turn": 1, "max_turns": 12}
                            self.assertIsNone(serving._validate_payload("omegajev", choice))
                            choice["max_turns"] = 13
                            self.assertEqual(serving._validate_payload("omegajev", choice), "invalid-turn")
                            serving.state.current = serving._Pending(1, {"example": True})
                            channel.receive()
                            self.assertEqual(provider.current_request(role), {"example": True})
                            self.assertTrue(provider.stage_result({"ok": True}))
                            self.assertEqual(serving.complete_staged(), "SB-RPC-RETURNED")
                            self.assertEqual(serving.state.current.response, {"ok": True})
                            code = "import stickerbookrpc_state as s; assert s.state.role == ''; assert not s.state.provider_ready"
                            subprocess.run([sys.executable, "-c", code], cwd=RPC_DIR, check=True)
                        finally:
                            channel.stop()
                    finally:
                        sys.path.remove(str(RPC_DIR))
                        sys.modules.pop("stickerbookrpc", None)
                        sys.modules.pop("stickerbookrpc_state", None)


if __name__ == "__main__":
    unittest.main()
