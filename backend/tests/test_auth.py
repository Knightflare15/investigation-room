from __future__ import annotations

import unittest

from backend.app.auth import issue_token, read_token, token_hash


class AuthTokenTests(unittest.TestCase):
    def test_tokens_are_opaque_and_high_entropy(self) -> None:
        token = issue_token("Nero Wolfe")
        self.assertGreaterEqual(len(token), 48)
        self.assertNotIn("Nero", token)
        self.assertEqual(len(token_hash(token)), 64)

    def test_legacy_stateless_tokens_fail_closed(self) -> None:
        self.assertIsNone(read_token(issue_token()))
        self.assertIsNone(read_token(None))
        self.assertIsNone(read_token("not-a-token"))

    def test_tokens_are_unique(self) -> None:
        self.assertNotEqual(issue_token(), issue_token())


if __name__ == "__main__":
    unittest.main()
