"""Regression checks for StickerBook's voice-first authority boundary.

Voice and accessibility text are two human I/O modalities over one conversation
seam. Neither may grow a second action/mutation API.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VoiceContractCase(unittest.TestCase):

    def test_voice_transcript_uses_same_conversation_function_as_text(self):
        app = (ROOT / "web/static/app.js").read_text(encoding="utf-8")
        self.assertIn(
            "return window.SpeechRecognition || window.webkitSpeechRecognition",
            app,
        )
        self.assertIn(
            "converseWithStickerBook(transcript, true, textChatEnabled);",
            app,
        )
        self.assertIn("const payload = await observePoweredRequest(() => world.converse(body));", app)
        self.assertIn('fetch("/api/agent/converse"', app)
        self.assertIn("window.speechSynthesis.speak(utterance);", app)

    def test_voice_is_adult_enabled_and_requires_conversational_runtime(self):
        app = (ROOT / "web/static/app.js").read_text(encoding="utf-8")
        html = (ROOT / "web/static/index.html").read_text(encoding="utf-8")
        self.assertIn('id="voice-enable"', html)
        self.assertIn('id="voice-orb"', html)
        self.assertIn("voiceEnable.disabled = !connected || !SpeechRecognitionCtor", app)
        self.assertIn("connected &&", app)
        self.assertIn("voiceEnabled &&", app)

    def test_voice_has_no_dedicated_mutation_endpoint(self):
        app = (ROOT / "web/static/app.js").read_text(encoding="utf-8")
        # Speech input is converted to text before the one conversation seam.
        voice_start = app.index("function startVoiceConversation()")
        voice_end = app.index("voiceEnable.addEventListener", voice_start)
        voice_block = app[voice_start:voice_end]
        self.assertNotIn("/api/kernel/", voice_block)
        self.assertNotIn("/api/agent/jev", voice_block)
        self.assertNotIn("world.send(", voice_block)


if __name__ == "__main__":
    unittest.main()
