from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.models import CaseBriefInput, CaseIngestionInput, CreateCaseRequest
from backend.app.services.authoring import AuthoringService


BRIEF = """Case Title
The Lantern Street File

Premise
A neighborhood organizer is found dead after a late planning meeting, and everyone who stayed behind has a reason to lie.

Victim
Mira Doss, organizer of the Lantern Street redevelopment committee.

Setting
An old union hall with a locked upstairs office, a side archive room, and a service alley exit.

Suspects
Name: Owen Hart
Role: Treasurer
Public Summary: Careful and methodical, always seen near the records box.
Hidden Facts: He discovered that one reimbursement file was falsified.
Secrets: He hid one page from the archive before the police arrived.
Traits: guarded, precise
Speaking Style: Precise and stiff.
Catchphrase: Check the numbers.
Verbal Tells: Repeats times and amounts when nervous.
Outward Goal: Protect the committee from scandal.
Protective Target: the reimbursement files
Protective Reason: A financial scandal would destroy his reputation.

Name: Saira Vale
Role: Campaign lead
Public Summary: Persuasive and polished, often handling tense conversations.
Hidden Facts: She arranged a private meeting with Mira after the public session ended.
Secrets: She deleted a message about the upstairs office.
Traits: charming, strategic
Speaking Style: Smooth and controlled.
Catchphrase: There is always context.
Verbal Tells: Answers accusations with observations.
Outward Goal: Control the public narrative.
Protective Target: the private meeting
Protective Reason: The meeting places her too close to the final confrontation.

Relationships
- Owen believed Saira was hiding funding issues.
- Mira was preparing to expose someone at the next public meeting.

Timeline
- Mira asks the public volunteers to leave after the meeting wraps.
- Saira is seen returning upstairs for a private conversation.
- Owen is spotted near the records archive minutes later.

Evidence
Title: Reimbursement Ledger Copy
Summary: A photocopy of the ledger with one correction circled in red.
Type: financial_record
Tags: ledger, reimbursement, records
Hidden: no

Title: Deleted Message Transcript
Summary: A recovered message referencing the upstairs office door.
Type: communications_log
Tags: message, office, door
Hidden: yes

Hidden Truth
- Mira found proof that committee funds had been redirected.
- The private meeting became a confrontation over exposure and blame.

Solution
Culprit: Saira Vale
Motive: She believed Mira would expose the funding scheme and ruin her career.
Summary: Saira confronted Mira in private, then relied on confusion around the archive records to misdirect attention.
"""

SOURCE_PACKET = """The Glass Harbor Affair

Nadia Vance, chair of the harbor redevelopment fundraiser, is found dead inside the restored customs house after the final guests are dismissed. The building has an upstairs records room, a service corridor, and a balcony door facing the marina.

Elias Mercer, the finance director, is calm and meticulous. He was responsible for the event accounts and discovered a payment discrepancy before Nadia died. Elias moved one ledger page before police arrived because he feared the campaign would collapse if the donor irregularity became public.

Priya Sen, the campaign strategist, is charismatic and persuasive. She arranged a private meeting between Nadia and an unnamed donor, then deleted one voice note after the meeting. Priya wants to keep control of the campaign narrative and avoids direct answers about the balcony door.

Nadia received an urgent note during the closing toast. Priya was seen near the staircase shortly afterward. Elias entered the records room corridor before security lost sight of him. The victim was found after the guests were cleared.

Evidence includes an event ledger extract with a handwritten correction near a donor payment, a recovered deleted voice note mentioning the balcony door, and security notes showing a gap near the service corridor.

Hidden truth: Nadia discovered that redevelopment funds had been redirected. Priya confronted Nadia during the private meeting because she feared Nadia would expose the donor arrangement and destroy her career.
"""


class AuthoringServiceTests(unittest.TestCase):
    def test_create_case_scaffold_and_upload_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthoringService(Path(temp_dir))
            bundle = service.create_case(
                CreateCaseRequest(
                    id="case-test",
                    title="Case Test",
                    hook="A mystery scaffold.",
                    difficulty="easy",
                    estimated_minutes=30,
                ),
                "Aryan",
            )
            self.assertEqual(bundle.case.id, "case-test")
            self.assertEqual(bundle.case.status, "draft")
            asset = service.save_asset("case-test", "suspects", "photo.svg", b"<svg></svg>", "Aryan")
            self.assertEqual(asset.kind, "suspects")
            reloaded = service.load_bundle("case-test", "Aryan")
            self.assertTrue(any(item.path == "suspects/photo.svg" for item in reloaded.assets))
            self.assertTrue(any(item.path == "suspects/template-suspect.svg" for item in reloaded.assets))

    def test_generate_case_from_brief_returns_draft_bundle_with_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthoringService(Path(temp_dir))
            response = service.generate_case_from_brief(
                CaseBriefInput(case_id="case-brief", brief=BRIEF, difficulty="medium", estimated_minutes=45),
                "Aryan",
            )
            self.assertEqual(response.bundle.case.status, "draft")
            self.assertEqual(response.bundle.case.owner_alias, "Aryan")
            self.assertGreaterEqual(len(response.bundle.suspects), 2)
            self.assertTrue(response.bundle.documents)
            self.assertTrue(any(suspect.image_path == "suspects/template-suspect.svg" for suspect in response.bundle.suspects))
            self.assertTrue(any(document.image_path == "evidence/template-evidence.svg" for document in response.bundle.documents))

    def test_ingest_case_from_source_returns_grounded_draft_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthoringService(Path(temp_dir))
            response = service.ingest_case_from_source(
                CaseIngestionInput(case_id="case-source", source_text=SOURCE_PACKET, difficulty="medium", estimated_minutes=45),
                "Aryan",
            )
            self.assertEqual(response.bundle.case.status, "draft")
            self.assertEqual(response.bundle.case.owner_alias, "Aryan")
            self.assertEqual(response.bundle.case.title, "The Glass Harbor Affair")
            self.assertGreaterEqual(len(response.bundle.suspects), 2)
            self.assertTrue(response.bundle.documents)
            self.assertTrue(response.groundings)
            self.assertTrue(any(grounding.supporting_chunk_ids for grounding in response.groundings))

    def test_ingest_case_from_source_rejects_empty_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthoringService(Path(temp_dir))
            with self.assertRaises(ValueError):
                service.ingest_case_from_source(
                    CaseIngestionInput(case_id="case-empty", source_text="", difficulty="medium", estimated_minutes=45),
                    "Aryan",
                )

    def test_only_admin_can_approve_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthoringService(Path(temp_dir))
            service.generate_case_from_brief(
                CaseBriefInput(case_id="case-brief", brief=BRIEF, difficulty="medium", estimated_minutes=45),
                "Aryan",
            )
            with self.assertRaises(ValueError):
                service.approve_case("case-brief", "Aryan")
            approved = service.approve_case("case-brief", "Consultant")
            self.assertEqual(approved.case.status, "approved")


if __name__ == "__main__":
    unittest.main()
