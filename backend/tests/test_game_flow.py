from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.config import Settings
from backend.app.services.game import GameService
from backend.app.models import BoardLinkRequest, RescanRequest, SearchRequest, SubmitTheoryRequest


class GameFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings(
            db_path=Path(self.temp_dir.name) / "test.db",
            cases_path=Path("cases"),
            ollama_base_url="http://127.0.0.1:11434",
            ollama_chat_model="fake-chat",
            ollama_embed_model="fake-embed",
            default_alias="Tester",
        )
        self.game = GameService(settings)
        self.alias = "Tester"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rescan_unlocks_hidden_document_from_context(self) -> None:
        response = self.game.rescan_case("case-001", self.alias, RescanRequest(focus="Ashdown Suite"))
        self.assertIn("doc_hotel_ledger", response.unlocked_documents)

    def test_board_link_unlocks_hidden_suspect(self) -> None:
        response = self.game.add_board_link(
            "case-001",
            self.alias,
            BoardLinkRequest(
                source_id="victim",
                target_id="hotel-ledger",
                link_type="secret-meeting",
            ),
        )
        self.assertTrue(response.is_valid)
        self.assertIn("sus_lena", response.unlocked_suspects)

    def test_theory_submission_updates_stats(self) -> None:
        self.game.get_or_create_state("case-001", self.alias)
        response = self.game.submit_theory(
            "case-001",
            self.alias,
            SubmitTheoryRequest(
                culprit_id="sus_mara",
                motive_text="She feared the partnership dissolution.",
                timeline_text="She arranged a side meeting after the dinner broke apart.",
                evidence_ids=["doc_incident", "doc_autopsy", "doc_hotel_ledger"],
            ),
        )
        self.assertTrue(response.saved)
        self.assertEqual(response.stats.culprit_counts["sus_mara"], 1)

    def test_case_detail_does_not_leak_private_suspect_data(self) -> None:
        detail = self.game.get_case_detail("case-001", self.alias)
        payload = detail.model_dump(mode="json")
        self.assertTrue(payload["suspects"], "expected at least one unlocked suspect")
        for suspect in payload["suspects"]:
            self.assertNotIn("private_truth", suspect)
            self.assertNotIn("dialogue_rules", suspect)
            self.assertNotIn("memory_rules", suspect)
            # public fields the UI relies on must still be present
            self.assertIn("public_profile", suspect)
            self.assertIn("display_name", suspect)


if __name__ == "__main__":
    unittest.main()

