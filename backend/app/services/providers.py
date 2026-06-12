from __future__ import annotations

import json
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Generator

import httpx

from ..config import Settings

logger = logging.getLogger(__name__)


class ProviderUnavailable(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, threshold: int, cooldown_seconds: int) -> None:
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at = 0.0

    def allow(self) -> bool:
        return not self.opened_at or time.monotonic() - self.opened_at >= self.cooldown_seconds

    def success(self) -> None:
        self.failures = 0
        self.opened_at = 0.0

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


class ChatProvider(ABC):
    name = "unknown"

    @abstractmethod
    def complete(self, system_prompt: str, payload: dict[str, object]) -> str:
        raise NotImplementedError

    def stream(self, system_prompt: str, payload: dict[str, object]) -> Generator[str, None, None]:
        yield self.complete(system_prompt, payload)


class EmbeddingProvider(ABC):
    name = "unknown"

    @abstractmethod
    def embed(self, text: str) -> list[float] | None:
        raise NotImplementedError


class _HttpProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.breaker = CircuitBreaker(settings.ai_failure_threshold, settings.ai_circuit_seconds)

    def _post(self, url: str, payload: dict[str, object], timeout: int) -> dict[str, object]:
        if not self.breaker.allow():
            raise ProviderUnavailable("provider circuit is open")
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = httpx.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                self.breaker.success()
                return response.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep((0.08 * (attempt + 1)) + random.random() * 0.04)
        self.breaker.failure()
        raise ProviderUnavailable(str(last_error))


class OllamaProvider(_HttpProvider, ChatProvider, EmbeddingProvider):
    name = "ollama"

    def complete(self, system_prompt: str, payload: dict[str, object]) -> str:
        body = self._post(
            f"{self.settings.ollama_base_url}/api/chat",
            {
                "model": self.settings.ollama_chat_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, separators=(",", ":"))},
                ],
            },
            self.settings.ollama_chat_timeout_seconds,
        )
        return str(body.get("message", {}).get("content", "")).strip()

    def embed(self, text: str) -> list[float] | None:
        body = self._post(
            f"{self.settings.ollama_base_url}/api/embed",
            {"model": self.settings.ollama_embed_model, "input": text},
            10,
        )
        embeddings = body.get("embeddings")
        if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
            return [float(value) for value in embeddings[0]]
        return None


class GeminiProvider(_HttpProvider, ChatProvider, EmbeddingProvider):
    name = "gemini"

    def _key(self) -> str:
        if not self.settings.gemini_api_key:
            raise ProviderUnavailable("GEMINI_API_KEY is not configured")
        return self.settings.gemini_api_key

    def complete(self, system_prompt: str, payload: dict[str, object]) -> str:
        body = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_chat_model}:generateContent?key={self._key()}",
            {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, separators=(",", ":"))}]}],
                "generationConfig": {"temperature": 0.35, "maxOutputTokens": 500},
            },
            self.settings.ollama_chat_timeout_seconds,
        )
        candidates = body.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()

    def embed(self, text: str) -> list[float] | None:
        body = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_embed_model}:embedContent?key={self._key()}",
            {
                "model": f"models/{self.settings.gemini_embed_model}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": 768,
            },
            10,
        )
        values = body.get("embedding", {}).get("values", [])
        return [float(value) for value in values] if isinstance(values, list) and values else None


class FallbackChatProvider(ChatProvider):
    name = "deterministic"

    def complete(self, system_prompt: str, payload: dict[str, object]) -> str:
        raise ProviderUnavailable("deterministic dialogue fallback required")


class FallbackEmbeddingProvider(EmbeddingProvider):
    name = "deterministic"

    def embed(self, text: str) -> list[float] | None:
        return None


def create_chat_provider(settings: Settings) -> ChatProvider:
    if settings.ai_provider.lower() == "deterministic":
        return FallbackChatProvider()
    if settings.ai_provider.lower() == "gemini":
        return GeminiProvider(settings)
    return OllamaProvider(settings)


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.ai_provider.lower() == "deterministic":
        return FallbackEmbeddingProvider()
    if settings.ai_provider.lower() == "gemini":
        return GeminiProvider(settings)
    return OllamaProvider(settings)
