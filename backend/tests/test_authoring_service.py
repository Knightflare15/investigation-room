from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.services.authoring import AuthoringService
from backend.app.models import CreateCaseRequest


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
                )
            )
            self.assertEqual(bundle.case.id, "case-test")
            asset = service.save_asset("case-test", "suspects", "photo.svg", b"<svg></svg>")
            self.assertEqual(asset.kind, "suspects")
            reloaded = service.load_bundle("case-test")
            self.assertEqual(len(reloaded.assets), 1)


if __name__ == "__main__":
    unittest.main()
