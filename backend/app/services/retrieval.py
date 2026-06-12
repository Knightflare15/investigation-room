from __future__ import annotations

import json
import hashlib
import math
import re
from dataclasses import dataclass

from ..config import Settings
from ..models import CaseDocument, LoadedCase, SearchResult
from .providers import EmbeddingProvider, ProviderUnavailable, create_embedding_provider


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
        self.provider = create_embedding_provider(settings)
        self._embedding_cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float] | None:
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        try:
            vector = self.provider.embed(text)
        except ProviderUnavailable:
            return None
        if vector is None:
            return None
        if len(self._embedding_cache) >= self._MAX_CACHE:
            del self._embedding_cache[next(iter(self._embedding_cache))]
        self._embedding_cache[text] = vector
        return vector


class RetrievalService:
    def __init__(self, settings: Settings) -> None:
        self.ollama = OllamaClient(settings)
        self._chunk_embedding_cache: dict[str, list[float] | None] = {}

    def _compute_chunk_embedding(self, chunk: ChunkRecord) -> list[float] | None:
        return self.ollama.embed(chunk.text)

    def _get_chunk_embedding(self, chunk: ChunkRecord) -> list[float] | None:
        if chunk.chunk_id not in self._chunk_embedding_cache:
            self._chunk_embedding_cache[chunk.chunk_id] = self._compute_chunk_embedding(chunk)
        return self._chunk_embedding_cache[chunk.chunk_id]

    def build_chunks(self, documents: list[CaseDocument]) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        for document in documents:
            tokens = re.findall(r"\S+", document.body)
            windows = [" ".join(tokens[start : start + 120]) for start in range(0, len(tokens), 90)]
            if not windows:
                windows = [document.body.strip()]
            for index, text in enumerate(windows, start=1):
                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"{document.case_id}:v1:{document.id}:{content_hash}:{index}",
                        document=document,
                        text=text,
                    )
                )
        return chunks

    def search(
        self,
        case: LoadedCase,
        document_ids: list[str],
        query: str,
        limit: int = 6,
        *,
        preferred_document_ids: set[str] | None = None,
        preferred_terms: list[str] | None = None,
        hidden_document_ids: set[str] | None = None,
        strong_match_terms: list[str] | None = None,
    ) -> list[SearchResult]:
        documents = [case.documents[doc_id] for doc_id in document_ids if doc_id in case.documents]
        chunks = self.build_chunks(documents)
        query_tokens = _tokenize(query)
        query_vector = self.ollama.embed(query)
        preferred_terms = [term.lower() for term in (preferred_terms or []) if term.strip()]
        strong_match_terms = [term.lower() for term in (strong_match_terms or []) if term.strip()]

        candidates: list[tuple[float, float, ChunkRecord, list[str]]] = []
        for chunk in chunks:
            chunk_tokens = _tokenize(chunk.text)
            overlap = len(set(query_tokens) & set(chunk_tokens))
            entity_matches = [tag for tag in chunk.document.entity_tags if tag.lower() in query.lower()]
            keyword_score = overlap + (1.5 * len(entity_matches))
            text_lower = f"{chunk.document.title} {chunk.text} {' '.join(chunk.document.entity_tags)}".lower()
            if preferred_document_ids and chunk.document.id in preferred_document_ids:
                keyword_score += 1.5
            if preferred_terms:
                keyword_score += 1.2 * sum(1 for term in preferred_terms if term in text_lower)
            if hidden_document_ids and chunk.document.id in hidden_document_ids:
                strong_match = any(term in text_lower for term in strong_match_terms) if strong_match_terms else False
                if not strong_match:
                    keyword_score -= 1.5
            semantic_score = 0.0
            if query_vector is not None:
                chunk_vector = self._get_chunk_embedding(chunk)
                if chunk_vector is not None:
                    semantic_score = _cosine_similarity(query_vector, chunk_vector) * 4.0
            if keyword_score <= 0 and semantic_score < 0.65:
                continue
            candidates.append((keyword_score, semantic_score, chunk, entity_matches))

        lexical_order = {
            item[2].chunk_id: rank
            for rank, item in enumerate(sorted(candidates, key=lambda item: item[0], reverse=True), start=1)
        }
        semantic_order = {
            item[2].chunk_id: rank
            for rank, item in enumerate(sorted(candidates, key=lambda item: item[1], reverse=True), start=1)
        }
        scored: list[SearchResult] = []
        for keyword_score, semantic_score, chunk, entity_matches in candidates:
            rrf = (1 / (60 + lexical_order[chunk.chunk_id])) + (1 / (60 + semantic_order[chunk.chunk_id]))
            total_score = keyword_score + semantic_score + (rrf * 20)
            snippet = chunk.text[:280] + ("..." if len(chunk.text) > 280 else "")
            scored.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
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
        doc_counts: dict[str, int] = {}
        for result in scored:
            if doc_counts.get(result.document_id, 0) >= 2:
                continue
            deduped.append(result)
            doc_counts[result.document_id] = doc_counts.get(result.document_id, 0) + 1
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
        suspect: object | None = None,
        memory_summary: str = "",
        discovered_contexts: list[str] | None = None,
        preferred_document_ids: set[str] | None = None,
        limit: int = 3,
    ) -> list[SearchResult]:
        """Return compact evidence snippets to ground dialogue replies.

        This is a small RAG-style retrieval step for interrogation: given the
        current question (and optional confronted evidence), pull the most
        relevant unlocked archive passages so dialogue can be anchored in case
        material instead of only the suspect profile.
        """
        suspect_terms: list[str] = []
        if suspect is not None:
            display_name = getattr(suspect, "display_name", "")
            role = getattr(getattr(suspect, "public_profile", None), "role", "")
            protective_target = getattr(getattr(suspect, "personality_profile", None), "protective_target", "")
            suspect_terms.extend([display_name, role, protective_target])
        context_terms = (discovered_contexts or [])[-4:]
        preferred_terms = [memory_summary, *context_terms, *suspect_terms]
        hidden_document_ids = {doc_id for doc_id in document_ids if case.documents[doc_id].unlock_rule}
        results = self.search(
            case,
            document_ids,
            query,
            limit=limit,
            preferred_document_ids=preferred_document_ids,
            preferred_terms=preferred_terms,
            hidden_document_ids=hidden_document_ids,
            strong_match_terms=[query, *(evidence.entity_tags if evidence else [])],
        )
        if evidence is None:
            return results

        evidence_result = SearchResult(
            chunk_id=f"{evidence.id}::direct",
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
