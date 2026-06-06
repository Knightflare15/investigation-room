from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.auth import hash_password, verify_password
from backend.app.config import Settings
from backend.app.services.accounts import AuthService


class AuthServiceTests(unittest.TestCase):
    def test_password_hash_round_trip(self) -> None:
        hashed = hash_password("secret123")
        self.assertTrue(verify_password("secret123", hashed))
        self.assertFalse(verify_password("wrongpass", hashed))

    def test_register_and_login_player(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthService(Settings(db_path=Path(temp_dir) / "auth.db"))
            session = service.register("Aryan", "secret123")
            self.assertEqual(session.alias, "Aryan")
            self.assertEqual(session.role, "player")

            login = service.login("Aryan", "secret123")
            self.assertEqual(login.alias, "Aryan")
            self.assertEqual(login.role, "player")

    def test_admin_alias_requires_secret_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AuthService(Settings(db_path=Path(temp_dir) / "auth.db"))
            with self.assertRaises(PermissionError):
                service.register("Consultant", "secret123")

            session = service.register("Consultant", "secret123", admin_code="change-me")
            self.assertEqual(session.role, "admin")

            with self.assertRaises(PermissionError):
                service.login("Consultant", "secret123")

            login = service.login("Consultant", "secret123", admin_code="change-me")
            self.assertEqual(login.role, "admin")


if __name__ == "__main__":
    unittest.main()
