from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.database import SQLiteDatabase, create_database


class DatabaseFactoryTests(unittest.TestCase):
    def test_create_database_defaults_to_sqlite_without_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = create_database(None, Path(temp_dir) / "state.db")
            self.assertIsInstance(database, SQLiteDatabase)


if __name__ == "__main__":
    unittest.main()
