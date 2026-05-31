from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.config import Settings
from backend.app.services.game import GameService


class StreamingTalkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        # Point Ollama at a port nothing is listening on so stream_reply takes the
        # deterministic heuristic fallback — no live model needed.
        settings = Settings(
            db_path=Path(self.temp_dir.name) / "test.db",
            cases_path=Path("cases"),
            ollama_base_url="http://127.0.0.1:1",
            ollama_chat_model="fake-chat",
            ollama_embed_model="fake-embed",
            default_alias="Tester",
        )
        self.game = GameService(settings)
        self.alias = "Tester"
        self.suspect_id = "sus_mara"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_stream_persists_exactly_one_round_matching_streamed_text(self) -> None:
        tokens = list(self.game.stream_talk_to_suspect("case-001", self.alias, self.suspect_id, "Why did you do it?"))
        streamed = "".join(tokens)
        self.assertTrue(streamed.strip(), "stream should yield a non-empty reply")

        conversation = self.game.db.load_conversation("case-001", self.alias, self.suspect_id)
        self.assertIsNotNone(conversation)
        detective_turns = [t for t in conversation.transcript if t.speaker == "detective"]
        suspect_turns = [t for t in conversation.transcript if t.speaker != "detective"]

        # Single LLM round: exactly one detective turn and one suspect turn (no double-call).
        self.assertEqual(len(detective_turns), 1)
        self.assertEqual(len(suspect_turns), 1)
        # The persisted reply is exactly what was streamed to the player.
        self.assertEqual(suspect_turns[0].text, streamed)


if __name__ == "__main__":
    unittest.main()
