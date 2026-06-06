from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from urllib import error, request

from pydantic import BaseModel, Field, ValidationError

from ..config import Settings
from ..models import (
    CaseIngestionInput,
    EvidenceDraft,
    ExtractedCaseDraft,
    ExtractedSuspectDraft,
    SourceChunk,
    SourceGrounding,
)
from .retrieval import OllamaClient

logger = logging.getLogger(__name__)

STOPWORDS = {
    "about",
    "after",
    "again",
    "along",
    "also",
    "before",
    "behind",
    "between",
    "because",
    "could",
    "during",
    "every",
    "found",
    "from",
    "have",
    "into",
    "later",
    "meeting",
    "night",
    "over",
    "people",
    "police",
    "private",
    "public",
    "scene",
    "someone",
    "their",
    "there",
    "through",
    "under",
    "victim",
    "where",
    "while",
    "with",
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "source"


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", text.lower())


def _entities(text: str) -> list[str]:
    matches = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text)
    ignored = {
        "Case",
        "Case Title",
        "Evidence",
        "Hidden Truth",
        "Premise",
        "Relationships",
        "Setting",
        "Solution",
        "Suspects",
        "Timeline",
        "Victim",
    }
    return list(dict.fromkeys(match for match in matches if match not in ignored and len(match) > 3))


def _keywords(text: str, limit: int = 8) -> list[str]:
    counts = Counter(token for token in _tokens(text) if len(token) > 4 and token not in STOPWORDS)
    return [word for word, _ in counts.most_common(limit)]


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


class _TitlePremiseExtraction(BaseModel):
    title: str = ""
    premise: str = ""


class _VictimSettingExtraction(BaseModel):
    victim: str = ""
    setting: str = ""


class _SuspectsExtraction(BaseModel):
    suspects: list[ExtractedSuspectDraft] = Field(default_factory=list)


class _RelationshipTimelineExtraction(BaseModel):
    relationships: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)


class _EvidenceExtraction(BaseModel):
    evidence: list[EvidenceDraft] = Field(default_factory=list)


class _SolutionExtraction(BaseModel):
    hidden_truth: list[str] = Field(default_factory=list)
    culprit_name: str = ""
    motive: str = ""
    solution_summary: str = ""


class SourceIngestionService:
    """Turn pasted creator source text into a grounded extracted draft.

    This is intentionally separate from gameplay retrieval. It builds a temporary
    source index, retrieves relevant passages for each extraction pass, and emits
    citations so the author can audit the generated case before approval.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ollama = OllamaClient(settings)

    def extract(self, payload: CaseIngestionInput) -> tuple[ExtractedCaseDraft, list[SourceGrounding]]:
        source_text = self._normalize(payload.source_text)
        if not source_text:
            raise ValueError("Source text is empty.")
        chunks = self.chunk_source(source_text)
        if not chunks:
            raise ValueError("Source text is too short to ingest.")
        chunk_vectors = {chunk.id: self.ollama.embed(chunk.text) for chunk in chunks}

        warnings: list[str] = []
        if len(source_text) < 700:
            warnings.append("Source text is thin; generated case may need manual strengthening in authoring.")
        if payload.focus_section:
            warnings.append(f"Focused regeneration ran for section: {payload.focus_section}.")

        title_chunks = self.retrieve(chunks, payload.title_hint or "case title mystery name", limit=2, chunk_vectors=chunk_vectors)
        premise_chunks = self.retrieve(chunks, "premise conflict death mystery incident", limit=3, chunk_vectors=chunk_vectors)
        victim_chunks = self.retrieve(chunks, "victim dead killed found body", limit=3, chunk_vectors=chunk_vectors)
        setting_chunks = self.retrieve(chunks, "setting location place room building scene", limit=3, chunk_vectors=chunk_vectors)
        suspect_chunks = self.retrieve(chunks, "suspects persons involved motives secrets alibi", limit=6, chunk_vectors=chunk_vectors)
        timeline_chunks = self.retrieve(chunks, "timeline time seen arrived left before after chronology", limit=5, chunk_vectors=chunk_vectors)
        evidence_chunks = self.retrieve(chunks, "evidence ledger message report note call receipt footage forensic hidden door", limit=6, chunk_vectors=chunk_vectors)
        truth_chunks = self.retrieve(chunks, "hidden truth secret lie culprit motive killed expose confrontation", limit=5, chunk_vectors=chunk_vectors)

        heuristic_title = self._extract_title(payload, title_chunks or chunks)
        heuristic_premise = self._extract_premise(premise_chunks or chunks)
        title_premise = self._extract_json(
            _TitlePremiseExtraction,
            title_chunks or premise_chunks or chunks[:2],
            "Extract the case title and a short premise from these grounded source chunks.",
        )
        title = (title_premise.title.strip() if title_premise and title_premise.title.strip() else heuristic_title)
        premise = (title_premise.premise.strip() if title_premise and title_premise.premise.strip() else heuristic_premise)

        heuristic_victim = self._extract_victim(victim_chunks or chunks)
        heuristic_setting = self._extract_setting(setting_chunks or chunks)
        victim_setting = self._extract_json(
            _VictimSettingExtraction,
            victim_chunks + [chunk for chunk in setting_chunks if chunk not in victim_chunks],
            "Extract the victim and the main setting from these grounded source chunks.",
        )
        victim = (victim_setting.victim.strip() if victim_setting and victim_setting.victim.strip() else heuristic_victim)
        setting = (victim_setting.setting.strip() if victim_setting and victim_setting.setting.strip() else heuristic_setting)

        heuristic_suspects = self._extract_suspects(suspect_chunks or chunks, victim)
        suspect_extraction = self._extract_json(
            _SuspectsExtraction,
            suspect_chunks or chunks[:4],
            "Extract the main suspects. Include role, public summary, hidden facts, secrets, personality traits, speaking style, verbal tells, outward goal, protective target, and protective reason when supported.",
        )
        suspects = suspect_extraction.suspects if suspect_extraction and suspect_extraction.suspects else heuristic_suspects
        suspect_method = "ollama" if suspect_extraction and suspect_extraction.suspects else "heuristic"
        if len(suspects) < 2:
            suspects.extend(self._fallback_suspects(chunks, victim, len(suspects)))
            warnings.append("Fewer than two clear suspects were found; fallback suspects were added for playability.")
            suspect_method = "heuristic"

        heuristic_evidence = self._extract_evidence(evidence_chunks or chunks, payload.case_id)
        evidence_extraction = self._extract_json(
            _EvidenceExtraction,
            evidence_chunks or chunks[:4],
            "Extract evidence items. Return compact titles, summaries, details, doc_type, folder, tags, and whether each item should stay hidden at first.",
        )
        evidence = evidence_extraction.evidence if evidence_extraction and evidence_extraction.evidence else heuristic_evidence
        evidence_method = "ollama" if evidence_extraction and evidence_extraction.evidence else "heuristic"
        if not evidence:
            evidence = self._fallback_evidence(premise, setting, truth_chunks)
            warnings.append("No clear evidence objects were found; generated starter documents from source passages.")
            evidence_method = "heuristic"

        heuristic_timeline = self._extract_timeline(timeline_chunks or chunks)
        heuristic_relationships = self._extract_relationships(suspect_chunks or chunks, suspects)
        timeline_relationships = self._extract_json(
            _RelationshipTimelineExtraction,
            timeline_chunks + [chunk for chunk in suspect_chunks if chunk not in timeline_chunks],
            "Extract the important timeline events and relationships for the case.",
        )
        relationships = timeline_relationships.relationships if timeline_relationships and timeline_relationships.relationships else heuristic_relationships
        timeline = timeline_relationships.timeline if timeline_relationships and timeline_relationships.timeline else heuristic_timeline
        relationship_method = "ollama" if timeline_relationships and (timeline_relationships.relationships or timeline_relationships.timeline) else "heuristic"

        heuristic_hidden_truth = self._extract_hidden_truth(truth_chunks or chunks)
        heuristic_culprit_name, heuristic_motive, heuristic_solution_summary = self._extract_solution(truth_chunks or suspect_chunks or chunks, suspects)
        solution_extraction = self._extract_json(
            _SolutionExtraction,
            truth_chunks or suspect_chunks or chunks[:4],
            "Extract hidden truths, culprit_name, motive, and a short solution summary grounded only in these chunks.",
        )
        hidden_truth = solution_extraction.hidden_truth if solution_extraction and solution_extraction.hidden_truth else heuristic_hidden_truth
        culprit_name = solution_extraction.culprit_name.strip() if solution_extraction and solution_extraction.culprit_name.strip() else heuristic_culprit_name
        motive = solution_extraction.motive.strip() if solution_extraction and solution_extraction.motive.strip() else heuristic_motive
        solution_summary = solution_extraction.solution_summary.strip() if solution_extraction and solution_extraction.solution_summary.strip() else heuristic_solution_summary
        solution_method = "ollama" if solution_extraction and any([solution_extraction.hidden_truth, solution_extraction.culprit_name, solution_extraction.motive, solution_extraction.solution_summary]) else "heuristic"
        if not culprit_name:
            culprit_name = suspects[0].name
            warnings.append("No explicit culprit was found; defaulted to the strongest suspect candidate.")
            solution_method = "heuristic"
        if not motive:
            motive = f"{culprit_name} had something personal or professional to lose if the truth surfaced."
            warnings.append("No explicit motive was found; generated a conservative motive from the source.")
            solution_method = "heuristic"
        contradictions = self._derive_contradictions(timeline, relationships, hidden_truth, evidence)

        extracted = ExtractedCaseDraft(
            case_id=payload.case_id,
            title=title,
            premise=premise,
            setting=setting,
            victim=victim,
            relationships=relationships,
            timeline=timeline,
            hidden_truth=hidden_truth,
            solution_summary=solution_summary,
            culprit_name=culprit_name,
            motive=motive,
            contradictions=contradictions,
            suspects=suspects[:5],
            evidence=evidence[:6],
            warnings=warnings,
        )

        groundings = [
            self._grounding("title", title, title_chunks or chunks[:1], self._confidence_for_method("ollama" if title_premise and title_premise.title.strip() else "heuristic"), "ollama" if title_premise and title_premise.title.strip() else "heuristic"),
            self._grounding("premise", premise, premise_chunks or chunks[:2], self._confidence_for_method("ollama" if title_premise and title_premise.premise.strip() else "heuristic"), "ollama" if title_premise and title_premise.premise.strip() else "heuristic"),
            self._grounding("victim", victim, victim_chunks or chunks[:2], self._confidence_for_method("ollama" if victim_setting and victim_setting.victim.strip() else "heuristic"), "ollama" if victim_setting and victim_setting.victim.strip() else "heuristic"),
            self._grounding("setting", setting, setting_chunks or chunks[:2], self._confidence_for_method("ollama" if victim_setting and victim_setting.setting.strip() else "heuristic"), "ollama" if victim_setting and victim_setting.setting.strip() else "heuristic"),
        ]
        groundings.extend(
            self._item_groundings("suspect", [suspect.name for suspect in suspects], suspect_chunks or chunks[:4], suspect_method)
        )
        groundings.extend(
            self._item_groundings("evidence", [item.title for item in evidence], evidence_chunks or chunks[:4], evidence_method)
        )
        groundings.extend(
            self._item_groundings("timeline", timeline[:4], timeline_chunks or chunks[:4], relationship_method)
        )
        groundings.extend(
            self._item_groundings("relationship", relationships[:4], suspect_chunks or chunks[:4], relationship_method)
        )
        groundings.extend(
            self._item_groundings("hidden_truth", hidden_truth[:4], truth_chunks or chunks[:4], solution_method)
        )
        groundings.append(
            self._grounding("solution", f"{culprit_name} | {motive}", truth_chunks or chunks[:2], self._confidence_for_method(solution_method), solution_method)
        )
        return extracted, [grounding for grounding in groundings if grounding.supporting_chunk_ids]

    def chunk_source(self, source_text: str) -> list[SourceChunk]:
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", source_text) if paragraph.strip()]
        chunks: list[SourceChunk] = []
        buffer: list[str] = []
        section_hint = "source"

        def flush() -> None:
            nonlocal buffer
            if not buffer:
                return
            text = "\n\n".join(buffer).strip()
            chunk_id = f"src_{len(chunks) + 1:03d}_{_slugify(section_hint)[:24]}"
            chunks.append(
                SourceChunk(
                    id=chunk_id,
                    text=text,
                    detected_entities=_entities(text)[:12],
                    keywords=_keywords(text),
                    section_hint=section_hint,
                )
            )
            buffer = []

        for paragraph in paragraphs:
            heading = paragraph.strip().strip(":")
            if len(heading) <= 48 and not re.search(r"[.!?]", heading) and len(paragraph.split()) <= 6:
                flush()
                section_hint = heading.lower()
                continue
            if sum(len(item) for item in buffer) + len(paragraph) > 900:
                flush()
            buffer.append(paragraph)
        flush()
        return chunks

    def retrieve(
        self,
        chunks: list[SourceChunk],
        query: str,
        limit: int = 4,
        *,
        chunk_vectors: dict[str, list[float] | None] | None = None,
    ) -> list[SourceChunk]:
        query_tokens = set(_tokens(query))
        query_vector = self.ollama.embed(query)
        lexical_scored: list[tuple[float, SourceChunk]] = []
        for chunk in chunks:
            text_tokens = set(_tokens(chunk.text))
            overlap = len(query_tokens & text_tokens)
            entity_bonus = sum(1 for entity in chunk.detected_entities if entity.lower() in query.lower()) * 1.5
            keyword_bonus = sum(1 for keyword in chunk.keywords if keyword in query.lower()) * 1.2
            score = overlap + entity_bonus + keyword_bonus
            if score > 0 or query_vector is not None:
                lexical_scored.append((score, chunk))
        lexical_scored.sort(key=lambda item: item[0], reverse=True)
        shortlisted = lexical_scored[: max(limit * 4, 8)] or [(0.0, chunk) for chunk in chunks[: max(limit * 2, 4)]]
        scored: list[tuple[float, SourceChunk]] = []
        for score, chunk in shortlisted:
            semantic = _cosine(query_vector, (chunk_vectors or {}).get(chunk.id)) * 4.0 if query_vector else 0.0
            total = score + semantic
            if total > 0:
                scored.append((total, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]] or chunks[:limit]

    def _normalize(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_title(self, payload: CaseIngestionInput, chunks: list[SourceChunk]) -> str:
        if payload.title_hint and payload.title_hint.strip():
            return payload.title_hint.strip()
        first_source_line = next((line.strip() for line in payload.source_text.splitlines() if line.strip()), "")
        if 8 <= len(first_source_line) <= 90 and not re.search(r"[.!?]$", first_source_line):
            return first_source_line
        source = "\n".join(chunk.text for chunk in chunks[:2])
        match = re.search(r"(?:case\s+title|title)\s*:?\s*(.+)", source, re.IGNORECASE)
        if match:
            return match.group(1).strip().splitlines()[0][:90]
        first_line = source.splitlines()[0].strip()
        if 8 <= len(first_line) <= 90:
            return first_line
        return "Generated Investigation File"

    def _extract_premise(self, chunks: list[SourceChunk]) -> str:
        sentences = self._chunk_sentences(chunks)
        selected = next((item for item in sentences if re.search(r"\b(dead|death|killed|murder|found|missing|incident)\b", item, re.IGNORECASE)), "")
        return selected or "A creator-authored mystery has been converted into an investigation draft."

    def _extract_victim(self, chunks: list[SourceChunk]) -> str:
        text = "\n".join(chunk.text for chunk in chunks)
        match = re.search(r"Victim\s*:?\s*(.+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip().splitlines()[0][:160]
        for sentence in _sentences(text):
            if re.search(r"\b(victim|dead|killed|found|murdered)\b", sentence, re.IGNORECASE):
                names = _entities(sentence)
                if names:
                    return names[0]
                return sentence[:160]
        return "The victim is not clearly named in the source."

    def _extract_setting(self, chunks: list[SourceChunk]) -> str:
        text = "\n".join(chunk.text for chunk in chunks)
        match = re.search(r"Setting\s*:?\s*(.+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip().splitlines()[0][:240]
        for sentence in _sentences(text):
            if re.search(r"\b(house|hall|hotel|office|room|street|building|estate|warehouse|club|restaurant|station|scene)\b", sentence, re.IGNORECASE):
                return sentence[:240]
        return chunks[0].text[:240]

    def _extract_suspects(self, chunks: list[SourceChunk], victim: str) -> list[ExtractedSuspectDraft]:
        text = "\n".join(chunk.text for chunk in chunks)
        candidates = []
        for name in _entities(text):
            if name.lower() in victim.lower() or name.lower() in {"case title", "hidden truth"}:
                continue
            if len(name.split()) >= 2:
                candidates.append(name)
        names = [name for name, _ in Counter(candidates).most_common(5)]
        suspects: list[ExtractedSuspectDraft] = []
        for name in names:
            related = [sentence for sentence in _sentences(text) if name in sentence][:4]
            hidden = [sentence for sentence in related if re.search(r"\b(secret|hid|lied|deleted|arranged|feared|motive|debt|affair|threat)\b", sentence, re.IGNORECASE)]
            role = self._infer_role(name, related)
            public_summary = related[0] if related else f"{name} is a person of interest connected to the case."
            suspects.append(
                ExtractedSuspectDraft(
                    name=name,
                    role=role,
                    public_summary=public_summary[:220],
                    hidden_facts=hidden[:2] or [f"{name} appears in source passages tied to unresolved case pressure."],
                    secrets=hidden[2:4] or [f"{name} is withholding the full reason they became involved."],
                    traits=self._infer_traits(" ".join(related)),
                    speaking_style=self._infer_speaking_style(" ".join(related)),
                    verbal_tells=["Narrows answers when asked for exact timing."],
                    outward_goal="Keep their version of events believable.",
                    protective_target=self._infer_protective_target(" ".join(hidden or related)),
                    protective_reason="The protected detail changes how their actions should be interpreted.",
                )
            )
        return suspects

    def _fallback_suspects(self, chunks: list[SourceChunk], victim: str, existing_count: int) -> list[ExtractedSuspectDraft]:
        fallback = []
        for index in range(existing_count + 1, 3):
            name = f"Person of Interest {index}"
            fallback.append(
                ExtractedSuspectDraft(
                    name=name,
                    role="Person of interest",
                    public_summary=f"{name} is connected to {victim} through the source material.",
                    hidden_facts=[chunks[0].text[:180]],
                    secrets=["Their full timeline needs author review."],
                    traits=["guarded", "careful"],
                    speaking_style="Careful, guarded, and selective.",
                    outward_goal="Avoid becoming the central suspect.",
                )
            )
        return fallback

    def _extract_evidence(self, chunks: list[SourceChunk], case_id: str) -> list[EvidenceDraft]:
        evidence: list[EvidenceDraft] = []
        evidence_words = r"(ledger|message|note|report|autopsy|forensic|receipt|call|email|camera|footage|key|transcript|record|log|letter)"
        seen: set[str] = set()
        for chunk in chunks:
            for sentence in _sentences(chunk.text):
                if not re.search(evidence_words, sentence, re.IGNORECASE):
                    continue
                noun_match = re.search(r"((?:[A-Z][a-z]+|deleted|recovered|forensic|security|phone|event|medical|ledger|message|call|email|note|report|record|log|receipt|footage)[\w\s-]{0,48}(?:ledger|message|note|report|receipt|call|email|camera|footage|key|transcript|record|log|letter))", sentence, re.IGNORECASE)
                title = noun_match.group(1).strip().title() if noun_match else f"Source Evidence {len(evidence) + 1}"
                title = re.sub(r"\s+", " ", title)[:72]
                if title.lower() in seen:
                    continue
                seen.add(title.lower())
                evidence.append(
                    EvidenceDraft(
                        title=title,
                        summary=sentence[:220],
                        details=[sentence, f"Source chunk: {chunk.id}"],
                        doc_type=self._infer_doc_type(title, sentence),
                        folder=self._infer_folder(title, sentence),
                        tags=list(dict.fromkeys(chunk.detected_entities[:3] + chunk.keywords[:3]))[:5],
                        hidden=bool(re.search(r"\b(hidden|secret|deleted|recovered|sealed|withheld)\b", sentence, re.IGNORECASE)),
                    )
                )
                if len(evidence) >= 6:
                    return evidence
        return evidence

    def _fallback_evidence(self, premise: str, setting: str, chunks: list[SourceChunk]) -> list[EvidenceDraft]:
        return [
            EvidenceDraft(
                title="Source Incident Notes",
                summary=premise[:180],
                details=[premise, chunks[0].text[:300] if chunks else setting],
                doc_type="police_report",
                folder="crime_scene",
                tags=_keywords(f"{premise} {setting}", 5),
            ),
            EvidenceDraft(
                title="Source Relationship Notes",
                summary="A generated relationship record based on the pasted source.",
                details=[chunk.text[:300] for chunk in chunks[:2]] or [setting],
                doc_type="memo",
                folder="witness_accounts",
                tags=_keywords(setting, 5),
            ),
        ]

    def _extract_timeline(self, chunks: list[SourceChunk]) -> list[str]:
        timeline: list[str] = []
        for sentence in self._chunk_sentences(chunks):
            if re.search(r"\b(before|after|then|later|around|at\s+\d|seen|arrived|left|found)\b", sentence, re.IGNORECASE):
                timeline.append(sentence[:220])
        return list(dict.fromkeys(timeline))[:6]

    def _extract_relationships(self, chunks: list[SourceChunk], suspects: list[ExtractedSuspectDraft]) -> list[str]:
        names = [suspect.name for suspect in suspects]
        relationships: list[str] = []
        for sentence in self._chunk_sentences(chunks):
            mentioned = [name for name in names if name in sentence]
            if len(mentioned) >= 2 or re.search(r"\b(friend|partner|rival|family|owed|worked|argued|protected|blackmail)\b", sentence, re.IGNORECASE):
                relationships.append(sentence[:220])
        return list(dict.fromkeys(relationships))[:5]

    def _extract_hidden_truth(self, chunks: list[SourceChunk]) -> list[str]:
        truth: list[str] = []
        for sentence in self._chunk_sentences(chunks):
            if re.search(r"\b(secret|hidden|truth|lied|deleted|covered|culprit|motive|killed|murdered|blackmail|debt|affair|threat)\b", sentence, re.IGNORECASE):
                truth.append(sentence[:220])
        return list(dict.fromkeys(truth))[:5]

    def _extract_solution(self, chunks: list[SourceChunk], suspects: list[ExtractedSuspectDraft]) -> tuple[str, str, str]:
        text = "\n".join(chunk.text for chunk in chunks)
        culprit = ""
        culprit_match = re.search(r"(?:culprit|killer|murderer)\s*(?:is|:)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", text, re.IGNORECASE)
        if culprit_match:
            culprit = culprit_match.group(1).strip()
        else:
            lower = text.lower()
            for suspect in suspects:
                if suspect.name.lower() in lower and re.search(rf"{re.escape(suspect.name.lower())}.{{0,120}}\b(killed|murdered|caused|covered|deleted|hid)\b", lower):
                    culprit = suspect.name
                    break

        motive = ""
        for sentence in _sentences(text):
            if re.search(r"\b(motive|because|feared|wanted|needed|debt|career|expose|blackmail)\b", sentence, re.IGNORECASE):
                motive = sentence[:240]
                break
        summary = text[:500]
        return culprit, motive, summary

    def _derive_contradictions(
        self,
        timeline: list[str],
        relationships: list[str],
        hidden_truth: list[str],
        evidence: list[EvidenceDraft],
    ) -> list[str]:
        contradictions = []
        if hidden_truth:
            contradictions.append(hidden_truth[0])
        if timeline:
            contradictions.append(f"The timeline needs pressure-testing around: {timeline[-1]}")
        if relationships:
            contradictions.append(f"A relationship is more important than it first appears: {relationships[0]}")
        if evidence:
            contradictions.append(f"{evidence[0].title} should be compared against witness statements.")
        return list(dict.fromkeys(contradictions))[:4]

    def _chunk_sentences(self, chunks: list[SourceChunk]) -> list[str]:
        return [sentence for chunk in chunks for sentence in _sentences(chunk.text)]

    def _confidence_for_method(self, method: str) -> str:
        return "high" if method == "ollama" else "fallback"

    def _extract_json(
        self,
        model_type: type[BaseModel],
        chunks: list[SourceChunk],
        instruction: str,
    ) -> BaseModel | None:
        if not chunks:
            return None
        payload = {
            "model": self.settings.ollama_chat_model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": "Return strict JSON only. Do not add markdown fences, commentary, or extra text.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": instruction,
                            "schema": model_type.model_json_schema(),
                            "source_chunks": [
                                {"id": chunk.id, "section_hint": chunk.section_hint, "text": chunk.text}
                                for chunk in chunks[:6]
                            ],
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
        }
        req = request.Request(
            f"{self.settings.ollama_base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.ollama_chat_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body.get("message", {}).get("content", "").strip()
            if not content:
                return None
            json_text = self._extract_json_object(content)
            if not json_text:
                return None
            return model_type.model_validate_json(json_text)
        except (error.URLError, TimeoutError, json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Source ingestion Ollama extraction failed; using heuristic fallback: %s", exc)
            return None

    def _extract_json_object(self, content: str) -> str | None:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE | re.DOTALL).strip()
        if stripped.startswith("{") or stripped.startswith("["):
            return stripped
        match = re.search(r"(\{.*\}|\[.*\])", stripped, re.DOTALL)
        return match.group(1) if match else None

    def _item_groundings(
        self,
        prefix: str,
        values: list[str],
        chunks: list[SourceChunk],
        method: str,
    ) -> list[SourceGrounding]:
        return [
            self._grounding(f"{prefix}_{index + 1}", value, self._supporting_chunks_for_value(chunks, value), self._confidence_for_method(method), method)
            for index, value in enumerate(values)
            if value.strip()
        ]

    def _supporting_chunks_for_value(self, chunks: list[SourceChunk], value: str) -> list[SourceChunk]:
        lowered = value.lower()
        matched = [chunk for chunk in chunks if lowered and lowered[:48] in chunk.text.lower()]
        return matched or chunks[:2]

    def _grounding(self, field: str, value: str, chunks: list[SourceChunk], confidence: str, method: str) -> SourceGrounding:
        preview = " ".join(chunk.text[:140] for chunk in chunks[:2]).strip()
        return SourceGrounding(
            generated_field=field,
            generated_value=value[:180],
            supporting_chunk_ids=[chunk.id for chunk in chunks[:4]],
            preview=preview[:300],
            confidence=confidence,
            method=method,
        )

    def _infer_role(self, name: str, related: list[str]) -> str:
        text = " ".join(related)
        match = re.search(rf"{re.escape(name)}\s*,\s*(?:the\s+)?([^,.]+)", text)
        if match and len(match.group(1).split()) <= 5:
            return match.group(1).strip().title()
        role_words = ["director", "assistant", "partner", "neighbor", "manager", "doctor", "officer", "organizer", "accountant", "lawyer", "friend"]
        for word in role_words:
            if re.search(rf"\b{word}\b", text, re.IGNORECASE):
                return word.title()
        return "Person of interest"

    def _infer_traits(self, text: str) -> list[str]:
        lowered = text.lower()
        traits = []
        if any(word in lowered for word in ("calm", "precise", "careful", "meticulous")):
            traits.append("controlled")
        if any(word in lowered for word in ("charming", "smooth", "persuasive")):
            traits.append("persuasive")
        if any(word in lowered for word in ("angry", "tense", "argument", "defensive")):
            traits.append("defensive")
        if any(word in lowered for word in ("secret", "hid", "deleted", "lied")):
            traits.append("guarded")
        return traits or ["guarded", "selective"]

    def _infer_speaking_style(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("charming", "persuasive", "smooth")):
            return "Polished and persuasive, but careful when timelines become specific."
        if any(word in lowered for word in ("angry", "argument", "defensive")):
            return "Tense and defensive, especially when their motives are questioned."
        if any(word in lowered for word in ("ledger", "record", "account", "precise")):
            return "Precise and restrained, leaning on records when pressured."
        return "Guarded, natural, and selective with details."

    def _infer_protective_target(self, text: str) -> str:
        lowered = text.lower()
        if "ledger" in lowered or "account" in lowered:
            return "the financial record"
        if "message" in lowered or "call" in lowered or "email" in lowered:
            return "the communication trail"
        if "meeting" in lowered or "timeline" in lowered:
            return "the private timeline"
        return "their hidden involvement"

    def _infer_doc_type(self, title: str, summary: str) -> str:
        text = f"{title} {summary}".lower()
        if any(word in text for word in ("autopsy", "forensic", "medical", "toxicology")):
            return "forensic_report"
        if any(word in text for word in ("call", "message", "email", "log", "transcript")):
            return "communications_log"
        if any(word in text for word in ("ledger", "receipt", "invoice", "bank", "payment")):
            return "financial_record"
        if any(word in text for word in ("witness", "statement", "interview")):
            return "witness_statement"
        return "memo"

    def _infer_folder(self, title: str, summary: str) -> str:
        doc_type = self._infer_doc_type(title, summary)
        if doc_type == "forensic_report":
            return "forensics"
        if doc_type == "communications_log":
            return "communications"
        if doc_type == "financial_record":
            return "financial"
        if doc_type == "witness_statement":
            return "witness_accounts"
        return "crime_scene"
