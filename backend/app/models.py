from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field


class StartState(BaseModel):
    initial_suspect_ids: list[str]
    initial_document_ids: list[str]
    initial_open_questions: list[str] = Field(default_factory=list)


class ArchiveDomain(BaseModel):
    id: str
    label: str
    image_path: str | None = None
    image_url: str | None = None
    summary: str = ""


class LocationDossier(BaseModel):
    id: str
    label: str
    summary: str
    image_path: str | None = None
    image_url: str | None = None
    linked_document_ids: list[str] = Field(default_factory=list)
    unlock_rule: str | None = None


class Trigger(BaseModel):
    type: str
    value: str
    location_id: str | None = None


class TriggerEffects(BaseModel):
    unlock_document_ids: list[str] = Field(default_factory=list)
    unlock_suspect_ids: list[str] = Field(default_factory=list)
    surface_document_ids: list[str] = Field(default_factory=list)


class RescanRule(BaseModel):
    id: str
    trigger: Trigger
    effects: TriggerEffects


class CanonicalTruth(BaseModel):
    culprit_id: str = ""
    motive_summary: str = ""
    timeline_summary: str = ""
    motive_concepts: list[str] = Field(default_factory=list)
    timeline_concepts: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class SubmissionConfig(BaseModel):
    required_fields: list[str]
    min_evidence_count: int = 1
    canonical_truth: CanonicalTruth = Field(default_factory=CanonicalTruth)


class BoardLinkDefinition(BaseModel):
    id: str
    source_id: str
    target_id: str
    link_type: str
    notes: str = ""


class DeductionRequirements(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    context_values: list[str] = Field(default_factory=list)
    board_link_ids: list[str] = Field(default_factory=list)
    suspect_ids: list[str] = Field(default_factory=list)
    revealed_fact_ids: list[str] = Field(default_factory=list)


class DeductionBeat(BaseModel):
    id: str
    title: str
    payoff: str
    requirements: DeductionRequirements = Field(default_factory=DeductionRequirements)
    effects: TriggerEffects = Field(default_factory=TriggerEffects)
    objective: str | None = None


class DeductionMessage(BaseModel):
    id: str
    title: str
    message: str
    objective: str | None = None
    unlocked_documents: list[str] = Field(default_factory=list)
    unlocked_suspects: list[str] = Field(default_factory=list)


class CaseConfig(BaseModel):
    id: str
    title: str
    hook: str
    difficulty: str
    estimated_minutes: int
    version: int
    status: str = "approved"
    owner_alias: str | None = None
    owner_user_id: str | None = None
    police_summary: str = ""
    cover_image_path: str | None = None
    cover_image_url: str | None = None
    start_state: StartState
    archive_domains: list[ArchiveDomain] = Field(default_factory=list)
    location_dossiers: list[LocationDossier] = Field(default_factory=list)
    rescan_rules: list[RescanRule] = Field(default_factory=list)
    submission: SubmissionConfig
    valid_board_links: list[BoardLinkDefinition] = Field(default_factory=list)
    deduction_beats: list[DeductionBeat] = Field(default_factory=list)


class PublicProfile(BaseModel):
    role: str
    summary: str


class PersonalityProfile(BaseModel):
    traits: list[str] = Field(default_factory=list)
    speaking_style: str = ""
    catchphrase: str = ""
    verbal_tells: list[str] = Field(default_factory=list)
    outward_goal: str = ""
    protective_target: str = ""
    protective_reason: str = ""


class PrivateTruth(BaseModel):
    facts_known: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    non_negotiables: list[str] = Field(default_factory=list)


class FactRevealRule(BaseModel):
    fact_id: str
    topics: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    min_trust: int = Field(default=0, ge=0, le=100)
    max_guardedness: int = Field(default=100, ge=0, le=100)


class DialogueRules(BaseModel):
    baseline_tone: str
    lie_strategy: str
    pressure_triggers: list[str] = Field(default_factory=list)
    fact_reveal_rules: list[FactRevealRule] = Field(default_factory=list)
    shut_down_threshold: int = 75


class MemoryRules(BaseModel):
    remember_topics: bool = True
    remember_confrontations: bool = True
    remember_detective_tone: bool = True


class SuspectConfig(BaseModel):
    id: str
    display_name: str
    unlock_rule: str | None = None
    public_profile: PublicProfile
    personality_profile: PersonalityProfile = Field(default_factory=PersonalityProfile)
    private_truth: PrivateTruth
    dialogue_rules: DialogueRules
    memory_rules: MemoryRules
    portrait_key: str | None = None
    image_path: str | None = None
    image_url: str | None = None


class PublicSuspect(BaseModel):
    id: str
    display_name: str
    unlock_rule: str | None = None
    public_profile: PublicProfile
    portrait_key: str | None = None
    image_path: str | None = None
    image_url: str | None = None


class SuspectFile(BaseModel):
    suspects: list[SuspectConfig]


class CaseDocument(BaseModel):
    id: str
    case_id: str
    title: str
    folder: str
    doc_type: str
    source_label: str
    unlock_rule: str | None = None
    entity_tags: list[str] = Field(default_factory=list)
    summary: str = ""
    body: str
    markdown_path: str
    image_path: str | None = None
    image_url: str | None = None


class PlayerCaseState(BaseModel):
    player_alias: str
    case_id: str
    suspicion_level: int = 0
    unlocked_document_ids: list[str] = Field(default_factory=list)
    unlocked_suspect_ids: list[str] = Field(default_factory=list)
    pinned_evidence_ids: list[str] = Field(default_factory=list)
    board_links: list[str] = Field(default_factory=list)
    completed_deduction_ids: list[str] = Field(default_factory=list)
    rescan_history: list[str] = Field(default_factory=list)
    discovered_contexts: list[str] = Field(default_factory=list)
    current_objective: str = "Review the police archive and find the missing pattern."


class ConversationTurn(BaseModel):
    speaker: str
    text: str
    citations: list[str] = Field(default_factory=list)


class ConversationState(BaseModel):
    suspect_id: str
    trust: int = 50
    guardedness: int = 25
    revealed_fact_ids: list[str] = Field(default_factory=list)
    confronted_evidence_ids: list[str] = Field(default_factory=list)
    memory_summary: str = ""
    transcript: list[ConversationTurn] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=6, ge=1, le=20)


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    folder: str
    snippet: str
    score: float
    matched_entity_tags: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    discovered_contexts: list[str] = Field(default_factory=list)
    deduction_messages: list[DeductionMessage] = Field(default_factory=list)


class RescanRequest(BaseModel):
    focus: str = Field(default="", max_length=500)
    location_id: str | None = Field(default=None, max_length=120)


class RescanResponse(BaseModel):
    focus: str
    location_id: str | None = None
    unlocked_documents: list[str] = Field(default_factory=list)
    unlocked_suspects: list[str] = Field(default_factory=list)
    surfaced_results: list[SearchResult] = Field(default_factory=list)
    discovered_contexts: list[str] = Field(default_factory=list)
    deduction_messages: list[DeductionMessage] = Field(default_factory=list)


class TalkRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class DialogueResponse(BaseModel):
    suspect_id: str
    reply: str
    new_context: list[str] = Field(default_factory=list)
    revealed_fact_ids: list[str] = Field(default_factory=list)
    grounding_results: list[SearchResult] = Field(default_factory=list)
    unlocked_documents: list[str] = Field(default_factory=list)
    unlocked_suspects: list[str] = Field(default_factory=list)
    lead_messages: list[str] = Field(default_factory=list)
    deduction_messages: list[DeductionMessage] = Field(default_factory=list)
    suspicion_level: int
    conversation: ConversationState


class ConfrontRequest(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=120)
    message: str = Field(default="", max_length=2000)


class BoardLinkRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=120)
    target_id: str = Field(min_length=1, max_length=120)
    link_type: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=1000)


class BoardLinkResponse(BaseModel):
    is_valid: bool
    link_id: str
    confirmed_note: str = ""
    unlocked_documents: list[str] = Field(default_factory=list)
    unlocked_suspects: list[str] = Field(default_factory=list)
    board_links: list[str] = Field(default_factory=list)
    deduction_messages: list[DeductionMessage] = Field(default_factory=list)


class TogglePinRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=120)


class SubmitTheoryRequest(BaseModel):
    culprit_id: str = Field(min_length=1, max_length=120)
    motive_text: str = Field(min_length=1, max_length=4000)
    timeline_text: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)


class CommunityExcerpt(BaseModel):
    player_alias: str
    excerpt: str


class CommunityStatsResponse(BaseModel):
    case_id: str
    culprit_counts: dict[str, int]
    evidence_counts: dict[str, int]
    excerpts: list[CommunityExcerpt]


class ScoreCategory(BaseModel):
    earned: int
    possible: int
    feedback: str


class TheoryScore(BaseModel):
    total: int
    possible: int = 100
    verdict: str
    culprit: ScoreCategory
    motive: ScoreCategory
    timeline: ScoreCategory
    evidence: ScoreCategory
    canonical_truth: CanonicalTruth


class SubmitTheoryResponse(BaseModel):
    saved: bool
    stats: CommunityStatsResponse
    score: TheoryScore


class CaseSummary(BaseModel):
    id: str
    title: str
    hook: str
    difficulty: str
    estimated_minutes: int
    version: int
    status: str = "approved"
    owner_alias: str | None = None
    cover_image_path: str | None = None
    cover_image_url: str | None = None


class CaseDetailResponse(BaseModel):
    case: CaseSummary
    police_summary: str
    open_questions: list[str]
    archive_domains: list[ArchiveDomain]
    location_dossiers: list[LocationDossier]
    suspects: list[PublicSuspect]
    documents: list[CaseDocument]
    state: PlayerCaseState
    completed_deductions: list[DeductionMessage] = Field(default_factory=list)


class AssetEntry(BaseModel):
    path: str
    url: str
    kind: str


class AuthoringBundle(BaseModel):
    case: CaseConfig
    suspects: list[SuspectConfig]
    documents: list[CaseDocument]
    prompts: dict[str, str]
    assets: list[AssetEntry] = Field(default_factory=list)


class CreateCaseRequest(BaseModel):
    id: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    title: str = Field(min_length=1, max_length=120)
    hook: str = Field(min_length=1, max_length=1000)
    difficulty: str = "medium"
    estimated_minutes: int = 45


class CaseBriefInput(BaseModel):
    case_id: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    brief: str = Field(min_length=1, max_length=50000)
    difficulty: str = "medium"
    estimated_minutes: int = 45


class CaseIngestionInput(BaseModel):
    case_id: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    source_text: str = Field(min_length=1, max_length=50000)
    difficulty: str = "medium"
    estimated_minutes: int = 45
    title_hint: str | None = None
    focus_section: str | None = None


class ParsedCaseBrief(BaseModel):
    case_id: str
    sections: dict[str, str]


class ExtractedSuspectDraft(BaseModel):
    name: str
    role: str
    public_summary: str
    hidden_facts: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    speaking_style: str = ""
    catchphrase: str = ""
    verbal_tells: list[str] = Field(default_factory=list)
    outward_goal: str = ""
    protective_target: str = ""
    protective_reason: str = ""


class EvidenceDraft(BaseModel):
    title: str
    summary: str
    details: list[str] = Field(default_factory=list)
    doc_type: str = "memo"
    folder: str = "crime_scene"
    tags: list[str] = Field(default_factory=list)
    hidden: bool = False


class ExtractedCaseDraft(BaseModel):
    case_id: str
    title: str
    premise: str
    setting: str
    victim: str
    relationships: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    hidden_truth: list[str] = Field(default_factory=list)
    solution_summary: str = ""
    culprit_name: str = ""
    motive: str = ""
    contradictions: list[str] = Field(default_factory=list)
    suspects: list[ExtractedSuspectDraft] = Field(default_factory=list)
    evidence: list[EvidenceDraft] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GenerateCaseDraftResponse(BaseModel):
    bundle: AuthoringBundle
    warnings: list[str] = Field(default_factory=list)


class SourceChunk(BaseModel):
    id: str
    text: str
    detected_entities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    section_hint: str = "source"


class SourceGrounding(BaseModel):
    generated_field: str
    generated_value: str = ""
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    preview: str
    confidence: Literal["high", "medium", "fallback"] = "medium"
    method: Literal["gemini", "ollama", "heuristic"] = "heuristic"


class CaseIngestionResponse(BaseModel):
    bundle: AuthoringBundle
    warnings: list[str] = Field(default_factory=list)
    groundings: list[SourceGrounding] = Field(default_factory=list)


SessionRole = Literal["player", "admin"]


class SessionPrincipal(BaseModel):
    user_id: str = ""
    alias: str
    role: SessionRole


class AuthRegisterRequest(BaseModel):
    alias: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=10, max_length=256)


class AuthLoginRequest(BaseModel):
    alias: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    token: str
    alias: str
    role: SessionRole


class SessionStatusResponse(BaseModel):
    alias: str
    role: SessionRole


class AuthUserRecord(BaseModel):
    id: str = ""
    alias: str
    password_hash: str
    role: SessionRole = "player"


class SessionRecord(BaseModel):
    token_hash: str
    user_id: str
    alias: str
    role: SessionRole
    expires_at: int


class UploadAssetResponse(BaseModel):
    path: str
    url: str
    kind: str


class SaveStateResponse(BaseModel):
    state: PlayerCaseState
    conversations: list[ConversationState]


@dataclass
class LoadedCase:
    config: CaseConfig
    suspects: dict[str, SuspectConfig]
    documents: dict[str, CaseDocument]
    prompts: dict[str, str]

    def summary(self) -> CaseSummary:
        return CaseSummary(
            id=self.config.id,
            title=self.config.title,
            hook=self.config.hook,
            difficulty=self.config.difficulty,
            estimated_minutes=self.config.estimated_minutes,
            version=self.config.version,
            status=self.config.status,
            owner_alias=self.config.owner_alias,
            cover_image_path=self.config.cover_image_path,
            cover_image_url=self.config.cover_image_url,
        )

    def to_detail(self, state: PlayerCaseState) -> CaseDetailResponse:
        suspects = [
            PublicSuspect(
                id=self.suspects[sid].id,
                display_name=self.suspects[sid].display_name,
                unlock_rule=self.suspects[sid].unlock_rule,
                public_profile=self.suspects[sid].public_profile,
                portrait_key=self.suspects[sid].portrait_key,
                image_path=self.suspects[sid].image_path,
                image_url=self.suspects[sid].image_url,
            )
            for sid in state.unlocked_suspect_ids
            if sid in self.suspects
        ]
        documents = [self.documents[did] for did in state.unlocked_document_ids if did in self.documents]
        completed_deductions = [
            DeductionMessage(
                id=beat.id,
                title=beat.title,
                message=beat.payoff,
                objective=beat.objective,
            )
            for beat in self.config.deduction_beats
            if beat.id in state.completed_deduction_ids
        ]
        return CaseDetailResponse(
            case=self.summary(),
            police_summary=self.config.police_summary,
            open_questions=self.config.start_state.initial_open_questions,
            archive_domains=self.config.archive_domains,
            location_dossiers=self.config.location_dossiers,
            suspects=suspects,
            documents=documents,
            state=state,
            completed_deductions=completed_deductions,
        )


def jsonable_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
