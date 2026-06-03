from __future__ import annotations

import unittest

from backend.app.auth import issue_token, read_token


class AuthTokenTests(unittest.TestCase):
    def test_issue_then_read_roundtrip(self) -> None:
        token = issue_token("Nero Wolfe")
        player = read_token(token)
        self.assertIsNotNone(player)
        assert player is not None
        self.assertEqual(player.alias, "Nero Wolfe")
        self.assertEqual(player.role, "player")

    def test_tampered_payload_rejected(self) -> None:
        token = issue_token("Nero")
        payload_b64, _, signature = token.partition(".")
        # Swap in a different payload while keeping the original signature.
        forged = issue_token("Mallory").partition(".")[0] + "." + signature
        self.assertIsNone(read_token(forged))

    def test_garbage_and_missing_tokens_rejected(self) -> None:
        self.assertIsNone(read_token(None))
        self.assertIsNone(read_token(""))
        self.assertIsNone(read_token("not-a-token"))
        self.assertIsNone(read_token("a.b.c"))


if __name__ == "__main__":
    unittest.main()
