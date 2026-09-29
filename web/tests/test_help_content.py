"""In-app documentation audience and projection tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
sys.path.insert(0, str(WEB))

import help_content  # noqa: E402
from bridge import Bridge  # noqa: E402
from jev_runtime import DisabledJevRuntime  # noqa: E402


class RecordingAgentRuntime:
    def __init__(self):
        self.scene = None

    def capabilities(self):
        return {"conversational_agent": True, "creator_agent": False}

    def inference_options(self):
        return [{
            "id": "asicloud",
            "label": "Sponsored ASI Cloud",
            "description": "Sponsored MiniMax.",
            "default_model": "minimax/minimax-m3",
            "model_locked": True,
            "sponsored": True,
            "available": True,
        }]

    def converse(
            self, *, text, principal, scene, reference=None,
            inference=None):
        self.scene = scene
        return {"ok": True, "reply": "You can drag stickers around the page."}


class HelpContentCase(unittest.TestCase):

    def test_help_schema_has_separate_child_and_adult_branches(self):
        help_doc = help_content.full_help()
        self.assertEqual(help_doc["version"], 1)
        self.assertTrue(help_doc["child"]["topics"])
        self.assertTrue(help_doc["adult"]["sections"])
        self.assertEqual(
            help_content.child_help_for_omega(),
            help_doc["child"],
        )

    def test_child_help_contains_no_operator_or_secret_setup_instructions(self):
        child = json.dumps(
            help_content.child_help_for_omega(), sort_keys=True).lower()
        forbidden = (
            "api key",
            "openrouter",
            "docker",
            "openshell",
            "wsl",
            "repository",
            "github",
            "provider credential",
            "start stickerbook.cmd",
            "stop stickerbook.cmd",
            "policy approval",
        )
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, child)

    def test_adult_guide_explains_parent_relevant_boundaries(self):
        adult = json.dumps(help_content.full_help()["adult"]).lower()
        for phrase in (
            "voice is off",
            "omega",
            "authority kernel",
            "public github pages",
            "cannot approve openshell policy changes",
            "stop stickerbook.cmd",
            "not labeled live-host verified",
            "sponsored asi cloud",
            "anthropic",
            "openai",
            "openrouter",
            "asi:one",
            "child cannot select a provider",
            "chalked",
            "alphaclaw",
            "bgi commons",
            "does not imply",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, adult)

    def test_omegallm_scene_receives_child_help_only(self):
        runtime = RecordingAgentRuntime()
        bridge = Bridge(
            agent_runtime=runtime,
            jev_runtime=DisabledJevRuntime(),
        )
        result = bridge.converse({"text": "How do I play?"})
        self.assertTrue(result["ok"])
        self.assertIsNotNone(runtime.scene)
        self.assertIn("child_help", runtime.scene)
        projected = json.dumps(runtime.scene, sort_keys=True)
        self.assertIn("How StickerBook works", projected)
        self.assertNotIn("Responsible adult guide", projected)
        self.assertNotIn("Start StickerBook.cmd", projected)
        self.assertNotIn("OPENROUTER_API_KEY", projected)

    def test_browser_surfaces_exist_for_both_audiences(self):
        html = (WEB / "static" / "index.html").read_text(encoding="utf-8")
        app = (WEB / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="child-help-btn"', html)
        self.assertIn('id="child-help-panel"', html)
        self.assertIn('id="adult-guide-sections"', html)
        self.assertIn('id="inference-provider"', html)
        self.assertIn('id="inference-model"', html)
        self.assertIn("PROJECT-LINEAGE.md", html)
        self.assertIn('fetch("static/help.json"', app)
        self.assertIn("renderHelpContent()", app)

    def test_public_pages_artifact_includes_help_data(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8")
        self.assertIn(
            "cp web/static/help.json _site/static/help.json", workflow)
        self.assertIn(
            r"help\.json|assets/.+))$' || true)", workflow)
        self.assertEqual(
            workflow.count("uses: actions/deploy-pages@v4"), 1)
        self.assertEqual(
            workflow.count("name: Deploy public mechanical demo"), 1)


if __name__ == "__main__":
    unittest.main()
