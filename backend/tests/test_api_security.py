from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app


class ApiSecurityTests(unittest.TestCase):
    def test_cookie_session_headers_and_logout(self) -> None:
        alias = f"api-{uuid.uuid4().hex[:12]}"
        with TestClient(app) as client:
            health = client.get("/health/live")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.headers["x-content-type-options"], "nosniff")
            self.assertTrue(health.headers.get("x-request-id"))

            registered = client.post("/auth/register", json={"alias": alias, "password": "long-password"})
            self.assertEqual(registered.status_code, 200)
            self.assertNotIn("token", registered.json())
            self.assertIn("investigation_session", registered.cookies)

            session = client.get("/session")
            self.assertEqual(session.status_code, 200)
            self.assertEqual(session.json()["alias"], alias)

            self.assertEqual(client.post("/auth/logout").status_code, 200)
            self.assertEqual(client.get("/session").status_code, 401)


if __name__ == "__main__":
    unittest.main()
