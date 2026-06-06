from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.config import Settings
from backend.app.services.game import GameService
from backend.app.models import BoardLinkRequest, CaseBriefInput, RescanRequest, SearchRequest, SubmitTheoryRequest, TogglePinRequest
from backend.app.services.authoring import AuthoringService


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
        response = self.game.rescan_case(
            "case-001",
            self.alias,
            RescanRequest(focus="Ashdown Suite", location_id="loc_ashdown_hotel"),
        )
        self.assertIn("doc_hotel_ledger", response.unlocked_documents)

    def test_rescan_wrong_location_does_not_unlock_hidden_document(self) -> None:
        response = self.game.rescan_case(
            "case-001",
            self.alias,
            RescanRequest(focus="Ashdown Suite", location_id="loc_service_corridor"),
        )
        self.assertEqual(response.unlocked_documents, [])

    def test_blank_rescan_does_not_unlock_hidden_document(self) -> None:
        response = self.game.rescan_case("case-001", self.alias, RescanRequest(focus="", location_id="loc_ashdown_hotel"))
        self.assertEqual(response.unlocked_documents, [])
        self.assertEqual(response.unlocked_suspects, [])

    def test_board_link_only_logs_theory_without_unlocking(self) -> None:
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
        self.assertEqual(response.unlocked_suspects, [])
        state = self.game.get_or_create_state("case-001", self.alias)
        self.assertNotIn("sus_lena", state.unlocked_suspect_ids)

    def test_board_link_with_document_node_id_preserves_canonical_link_id(self) -> None:
        response = self.game.add_board_link(
            "case-001",
            self.alias,
            BoardLinkRequest(
                source_id="victim",
                target_id="doc_hotel_ledger",
                link_type="secret-meeting",
            ),
        )
        self.assertTrue(response.is_valid)
        self.assertEqual(response.link_id, "victim-hotel-ledger-secret-meeting")
        self.assertEqual(response.unlocked_suspects, [])

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

    def test_restart_case_resets_progress_but_keeps_submission_history(self) -> None:
        self.game.talk_to_suspect("case-001", self.alias, "sus_rohan", "What do you know about Lena Orlov?")
        self.game.toggle_pin("case-001", self.alias, TogglePinRequest(document_id="doc_incident"))
        self.game.submit_theory(
            "case-001",
            self.alias,
            SubmitTheoryRequest(
                culprit_id="sus_mara",
                motive_text="She feared the partnership dissolution.",
                timeline_text="She arranged a side meeting after the dinner broke apart.",
                evidence_ids=["doc_incident", "doc_autopsy", "doc_hotel_ledger"],
            ),
        )

        initial_state = self.game.get_case("case-001").config.start_state
        restarted = self.game.restart_case("case-001", self.alias)

        self.assertEqual(restarted.state.unlocked_document_ids, initial_state.initial_document_ids)
        self.assertEqual(restarted.state.unlocked_suspect_ids, initial_state.initial_suspect_ids)
        self.assertEqual(restarted.state.pinned_evidence_ids, [])
        self.assertEqual(restarted.state.board_links, [])
        self.assertEqual(restarted.state.rescan_history, [])
        self.assertEqual(restarted.conversations, [])
        stats = self.game.get_community_stats("case-001", self.alias)
        self.assertEqual(stats.culprit_counts["sus_mara"], 1)

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

    def test_talk_returns_retrieved_grounding_results(self) -> None:
        response = self.game.talk_to_suspect("case-001", self.alias, "sus_rohan", "What happened with the hotel suite?")
        self.assertTrue(response.grounding_results, "expected retrieved evidence context for dialogue grounding")
        self.assertTrue(
            any(result.document_id == "doc_incident" for result in response.grounding_results),
            "expected archive grounding to include the incident summary for a hotel/suite query",
        )

    def test_conversation_can_unlock_hidden_suspect_from_named_context(self) -> None:
        settings = Settings(
            db_path=Path(self.temp_dir.name) / "conversation-unlock.db",
            cases_path=Path("cases"),
            ollama_base_url="http://127.0.0.1:1",
            ollama_chat_model="fake-chat",
            ollama_embed_model="fake-embed",
            default_alias="Tester",
        )
        fallback_game = GameService(settings)
        response = fallback_game.talk_to_suspect("case-001", self.alias, "sus_rohan", "What do you know about Lena Orlov?")
        self.assertTrue(response.reply.strip())
        state = fallback_game.get_or_create_state("case-001", self.alias)
        self.assertIn("sus_lena", state.unlocked_suspect_ids)

    def test_heuristic_dialogue_uses_authored_personality_voice(self) -> None:
        settings = Settings(
            db_path=Path(self.temp_dir.name) / "fallback-test.db",
            cases_path=Path("cases"),
            ollama_base_url="http://127.0.0.1:1",
            ollama_chat_model="fake-chat",
            ollama_embed_model="fake-embed",
            default_alias="Tester",
        )
        fallback_game = GameService(settings)
        response = fallback_game.talk_to_suspect("case-001", self.alias, "sus_rohan", "Tell me about the hotel records.")
        self.assertTrue(response.reply.strip())
        self.assertNotIn("That's an administrative matter.", response.reply)
        self.assertNotIn("answers in a", response.reply.lower())
        self.assertNotIn("cadence", response.reply.lower())
        self.assertNotIn("voice", response.reply.lower())

    def test_begin_interrogation_session_compacts_existing_transcript(self) -> None:
        self.game.talk_to_suspect("case-001", self.alias, "sus_mara", "Tell me about the private booking.")
        conversation = self.game.begin_interrogation_session("case-001", self.alias, "sus_mara")
        self.assertEqual(conversation.transcript, [])
        self.assertTrue(conversation.memory_summary)
        self.assertIn("Pressed Mara Voss", conversation.memory_summary)

    def test_llm_reply_metadata_leak_falls_back_to_clean_heuristic(self) -> None:
        settings = Settings(
            db_path=Path(self.temp_dir.name) / "sanitize-test.db",
            cases_path=Path("cases"),
            ollama_base_url="http://127.0.0.1:11434",
            ollama_chat_model="fake-chat",
            ollama_embed_model="fake-embed",
            default_alias="Tester",
        )
        game = GameService(settings)
        case = game.get_case("case-001")
        state = game.get_or_create_state("case-001", self.alias)
        suspect = case.suspects["sus_mara"]
        conversation = game._get_conversation("case-001", self.alias, "sus_mara")
        grounding = game.get_talk_grounding("case-001", self.alias, "sus_mara", "did you know about the private booking?")

        game.dialogue._call_ollama = lambda *args, **kwargs: None  # type: ignore[method-assign]
        sanitized = game.dialogue._sanitize_reply(
            'Mara Voss glances at Incident Summary and answers in a polished, economical cadence. "Let\'s be exact."',
            suspect,
        )

        self.assertIsNone(sanitized)
        response = game.dialogue.generate(case, suspect, conversation, state, "did you know about the private booking?", grounding)
        self.assertNotIn("answers in a", response.reply.lower())
        self.assertNotIn("cadence", response.reply.lower())

    def test_public_listing_hides_draft_case_but_owner_can_open_it(self) -> None:
        brief = """Case Title
Draft Harbor Case

Premise
A donor is found dead after a private strategy meeting.

Victim
Hale Rowan, donor liaison.

Setting
An old harbor office with a records room and private stairwell.

Suspects
Name: Mira Holt
Role: Organizer
Public Summary: Calm and persuasive in public.
Hidden Facts: She arranged the final meeting.
Secrets: She hid one ledger page.

Name: Devin Cross
Role: Treasurer
Public Summary: Meticulous and defensive around the accounts.
Hidden Facts: He discovered the missing funds.
Secrets: He concealed one invoice.

Relationships
- Mira and Devin were both hiding committee problems.

Timeline
- The meeting ended late.
- Mira returned upstairs.
- Devin went to the records room.

Evidence
Title: Ledger Copy
Summary: A copied page showing one suspicious payment.
Type: financial_record
Tags: ledger, payment
Hidden: no

Hidden Truth
- The donor discovered redirected funds.

Solution
Culprit: Mira Holt
Motive: She feared public exposure.
Summary: Mira used the private meeting to silence the donor.
"""
        with tempfile.TemporaryDirectory() as temp_cases_dir:
            authoring = AuthoringService(Path(temp_cases_dir))
            authoring.generate_case_from_brief(
                CaseBriefInput(case_id="case-draft", brief=brief, difficulty="medium", estimated_minutes=30),
                "Tester",
            )
            settings = Settings(
                db_path=Path(self.temp_dir.name) / "visibility-test.db",
                cases_path=Path(temp_cases_dir),
                ollama_base_url="http://127.0.0.1:1",
                ollama_chat_model="fake-chat",
                ollama_embed_model="fake-embed",
                default_alias="Tester",
            )
            game = GameService(settings)
            self.assertEqual(game.list_cases(), [])
            pending = game.list_pending_cases("Consultant")
            self.assertEqual([item.id for item in pending], ["case-draft"])
            with self.assertRaises(PermissionError):
                game.list_pending_cases("Mallory")
            detail = game.get_case_detail("case-draft", "Tester")
            self.assertEqual(detail.case.id, "case-draft")
            with self.assertRaises(KeyError):
                game.get_case_detail("case-draft", "Mallory")


if __name__ == "__main__":
    unittest.main()
