from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from urllib import error, request

from ..config import Settings
from ..models import CaseDocument, LoadedCase, SearchResult


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", text.lower())


def _extract_context_candidates(text: str) -> list[str]:
    matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|Room\s+\d+|[A-Z][a-z]+ Suite)\b", text)
    return list(dict.fromkeys(match.strip() for match in matches if len(match.strip()) > 3))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


@dataclass
class ChunkRecord:
    chunk_id: str
    document: CaseDocument
    text: str


class OllamaClient:
    _MAX_CACHE = 2048

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embedding_cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float] | None:
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        payload = json.dumps({"model": self.settings.ollama_embed_model, "input": text}).encode("utf-8")
        req = request.Request(
            f"{self.settings.ollama_base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return None

        vector = None
        embeddings = body.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            if isinstance(embeddings[0], list):
                vector = embeddings[0]
            elif all(isinstance(item, (int, float)) for item in embeddings):
                vector = embeddings
        if vector is None:
            return None
        if len(self._embedding_cache) >= self._MAX_CACHE:
            del self._embedding_cache[next(iter(self._embedding_cache))]
        self._embedding_cache[text] = vector
        return vector


class RetrievalService:
    def __init__(self, settings: Settings) -> None:
        self.ollama = OllamaClient(settings)

    def build_chunks(self, documents: list[CaseDocument]) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        for document in documents:
            paragraphs = [paragraph.strip() for paragraph in document.body.split("\n\n") if paragraph.strip()]
            if not paragraphs:
                paragraphs = [document.body.strip()]
            for index, paragraph in enumerate(paragraphs, start=1):
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"{document.id}::p{index}",
                        document=document,
                        text=paragraph,
                    )
                )
        return chunks

    def search(
        self,
        case: LoadedCase,
        document_ids: list[str],
        query: str,
        limit: int = 6,
    ) -> list[SearchResult]:
        documents = [case.documents[doc_id] for doc_id in document_ids if doc_id in case.documents]
        chunks = self.build_chunks(documents)
        query_tokens = _tokenize(query)
        query_vector = self.ollama.embed(query)

        scored: list[SearchResult] = []
        for chunk in chunks:
            chunk_tokens = _tokenize(chunk.text)
            overlap = len(set(query_tokens) & set(chunk_tokens))
            entity_matches = [tag for tag in chunk.document.entity_tags if tag.lower() in query.lower()]
            keyword_score = overlap + (1.5 * len(entity_matches))
            semantic_score = 0.0
            if query_vector is not None:
                chunk_vector = self.ollama.embed(chunk.text)
                if chunk_vector is not None:
                    semantic_score = _cosine_similarity(query_vector, chunk_vector) * 4.0
            total_score = keyword_score + semantic_score
            if total_score <= 0:
                continue
            snippet = chunk.text[:280] + ("..." if len(chunk.text) > 280 else "")
            scored.append(
                SearchResult(
                    document_id=chunk.document.id,
                    title=chunk.document.title,
                    folder=chunk.document.folder,
                    snippet=snippet,
                    score=round(total_score, 3),
                    matched_entity_tags=entity_matches,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        deduped: list[SearchResult] = []
        seen_docs: set[str] = set()
        for result in scored:
            if result.document_id in seen_docs:
                continue
            deduped.append(result)
            seen_docs.add(result.document_id)
            if len(deduped) >= limit:
                break
        return deduped

    def surface_from_context(
        self,
        case: LoadedCase,
        document_ids: list[str],
        contexts: list[str],
        limit: int = 6,
    ) -> list[SearchResult]:
        return self.search(case, document_ids, " ".join(contexts), limit=limit)

    def retrieve_dialogue_context(
        self,
        case: LoadedCase,
        document_ids: list[str],
        query: str,
        evidence: CaseDocument | None = None,
        limit: int = 3,
    ) -> list[SearchResult]:
        """Return compact evidence snippets to ground dialogue replies.

        This is a small RAG-style retrieval step for interrogation: given the
        current question (and optional confronted evidence), pull the most
        relevant unlocked archive passages so dialogue can be anchored in case
        material instead of only the suspect profile.
        """
        results = self.search(case, document_ids, query, limit=limit)
        if evidence is None:
            return results

        evidence_result = SearchResult(
            document_id=evidence.id,
            title=evidence.title,
            folder=evidence.folder,
            snippet=evidence.body[:280] + ("..." if len(evidence.body) > 280 else ""),
            score=999.0,
            matched_entity_tags=list(evidence.entity_tags),
        )
        deduped = [evidence_result]
        deduped.extend(result for result in results if result.document_id != evidence.id)
        return deduped[:limit]

    def derive_contexts(self, text: str, documents: list[CaseDocument] | None = None) -> list[str]:
        contexts = _extract_context_candidates(text)
        if documents:
            for document in documents:
                if document.title.lower() in text.lower():
                    contexts.append(document.title)
                for tag in document.entity_tags:
                    if tag.lower() in text.lower():
                        contexts.append(tag)
        return list(dict.fromkeys(contexts))
