from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.app.config import Settings
from backend.app.services.game import GameService


class RetrievalEvaluationTests(unittest.TestCase):
    def test_case_001_recall_at_five_and_mrr(self) -> None:
        game = GameService(Settings(db_path=Path("backend/data/retrieval-eval.db"), cases_path=Path("cases"), ai_provider="deterministic"))
        case = game.get_case("case-001")
        rows = json.loads(Path("backend/tests/retrieval_eval_case_001.json").read_text(encoding="utf-8"))
        recalls = []
        reciprocal_ranks = []
        for row in rows:
            results = game.retrieval.search(case, list(case.documents), row["query"], limit=5)
            ranked = [result.document_id for result in results]
            expected = set(row["expected"])
            recalls.append(len(expected & set(ranked)) / len(expected))
            first_rank = next((index for index, document_id in enumerate(ranked, start=1) if document_id in expected), 0)
            reciprocal_ranks.append(1 / first_rank if first_rank else 0)
        self.assertGreaterEqual(sum(recalls) / len(recalls), 0.66)
        self.assertGreaterEqual(sum(reciprocal_ranks) / len(reciprocal_ranks), 0.60)


if __name__ == "__main__":
    unittest.main()
