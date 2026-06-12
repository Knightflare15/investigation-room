from __future__ import annotations

import unittest
from unittest import mock

from backend.app.config import Settings
from backend.app.services.providers import GeminiProvider, OllamaProvider


class ProviderContractTests(unittest.TestCase):
    @mock.patch("backend.app.services.providers.httpx.post")
    def test_ollama_contract(self, post: mock.MagicMock) -> None:
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {"message": {"content": "Grounded reply"}, "embeddings": [[1, 2, 3]]}
        provider = OllamaProvider(Settings())
        self.assertEqual(provider.complete("system", {"x": "y"}), "Grounded reply")
        self.assertEqual(provider.embed("text"), [1.0, 2.0, 3.0])

    @mock.patch("backend.app.services.providers.httpx.post")
    def test_gemini_contract(self, post: mock.MagicMock) -> None:
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.side_effect = [
            {"candidates": [{"content": {"parts": [{"text": "Grounded reply"}]}}]},
            {"embedding": {"values": [1, 2, 3]}},
        ]
        provider = GeminiProvider(Settings(gemini_api_key="test"))
        self.assertEqual(provider.complete("system", {"x": "y"}), "Grounded reply")
        self.assertEqual(provider.embed("text"), [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
