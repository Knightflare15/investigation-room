from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from backend.app.auth import token_hash
from backend.app.config import Settings
from backend.app.models import CaseIngestionInput
from backend.app.services.accounts import AuthService
from backend.app.services.authoring import AuthoringService


class ProductionGuardrailTests(unittest.TestCase):
    def test_database_session_expires_and_revokes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthService(Settings(db_path=Path(temp_dir) / "auth.db", session_ttl_seconds=60))
            session = service.register("SecureUser", "long-password")
            stored = service.db.load_session(token_hash(session.token), int(time.time()))
            self.assertIsNotNone(stored)
            service.revoke(session.token)
            self.assertIsNone(service.db.load_session(token_hash(session.token), int(time.time())))

    def test_unsafe_upload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthoringService(Path(temp_dir))
            bundle = service.create_case(
                __import__("backend.app.models", fromlist=["CreateCaseRequest"]).CreateCaseRequest(
                    id="safe-case", title="Safe Case", hook="Test"
                ),
                "Aryan",
            )
            with self.assertRaises(ValueError):
                service.save_asset(bundle.case.id, "evidence", "payload.svg", b"<svg/>", "Aryan", "image/svg+xml")

    def test_source_ingestion_size_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            CaseIngestionInput(case_id="", source_text="x" * 50001)


if __name__ == "__main__":
    unittest.main()
