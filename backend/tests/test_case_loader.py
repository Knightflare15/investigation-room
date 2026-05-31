from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.case_loader import load_case


class CaseLoaderTests(unittest.TestCase):
    def test_case_loads_expected_documents_and_suspects(self) -> None:
        case = load_case(Path("cases/case-001"))
        self.assertEqual(case.config.id, "case-001")
        self.assertIn("sus_mara", case.suspects)
        self.assertIn("doc_incident", case.documents)
        self.assertEqual(case.documents["doc_incident"].folder, "crime_scene")
        self.assertTrue(case.documents["doc_incident"].image_url)
        self.assertTrue(case.suspects["sus_mara"].image_url)


if __name__ == "__main__":
    unittest.main()
