from __future__ import annotations

import unittest
from unittest import mock

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - exercised only when optional Postgres deps are absent
    psycopg = None
    Jsonb = None

from backend.app.database import PostgresDatabase
from backend.app.models import PlayerCaseState


@unittest.skipIf(psycopg is None or Jsonb is None, "psycopg is not installed")
class PostgresDialectTests(unittest.TestCase):
    """Exercise the BaseDatabase Postgres branch without a live server by mocking psycopg."""

    def _make_db(self):
        self.cursor = mock.MagicMock()
        connection = mock.MagicMock()
        connection.cursor.return_value.__enter__.return_value = self.cursor
        connect_cm = mock.MagicMock()
        connect_cm.__enter__.return_value = connection
        self._patch = mock.patch.object(psycopg, "connect", return_value=connect_cm)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        return PostgresDatabase("postgresql://example/db")

    def _executes_for(self, table: str) -> list[tuple]:
        return [
            call.args
            for call in self.cursor.execute.call_args_list
            if f"INTO {table}" in call.args[0]
        ]

    def test_uses_pg_placeholders_and_jsonb_wrapping(self) -> None:
        db = self._make_db()
        db.save_player_state(PlayerCaseState(player_alias="Nero", case_id="case-001"))

        inserts = self._executes_for("player_case_states")
        self.assertEqual(len(inserts), 1, "save_player_state should issue one upsert")
        sql, params = inserts[0]

        # Postgres dialect: %s placeholders, never SQLite's ?.
        self.assertIn("%s", sql)
        self.assertNotIn("?", sql)
        self.assertIn("EXCLUDED.", sql)

        # JSON columns are passed as Jsonb wrappers (no ::jsonb casts needed in SQL).
        self.assertTrue(any(isinstance(p, Jsonb) for p in params), "expected Jsonb-wrapped JSON params")


if __name__ == "__main__":
    unittest.main()
