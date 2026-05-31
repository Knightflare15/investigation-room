from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


class TriggerEffects(BaseModel):
    unlock_document_ids: list[str] = Field(default_factory=list)
    unlock_suspect_ids: list[str] = Field(default_factory=list)
    surface_document_ids: list[str] = Field(default_factory=list)


class RescanRule(BaseModel):
    id: str
    trigger: Trigger
    effects: TriggerEffects


class SubmissionConfig(BaseModel):
    required_fields: list[str]
    min_evidence_count: int = 1


class BoardLinkDefinition(BaseModel):
    id: str
    source_id: str
    target_id: str
    link_type: str
    notes: str = ""


class CaseConfig(BaseModel):
    id: str
    title: str
    hook: str
    difficulty: str
    estimated_minutes: int
    version: int
    police_summary: str = ""
    cover_image_path: str | None = None
    cover_image_url: str | None = None
    start_state: StartState
    archive_domains: list[ArchiveDomain] = Field(default_factory=list)
    location_dossiers: list[LocationDossier] = Field(default_factory=list)
    rescan_rules: list[RescanRule] = Field(default_factory=list)
    submission: SubmissionConfig
    valid_board_links: list[BoardLinkDefinition] = Field(default_factory=list)


class PublicProfile(BaseModel):
    role: str
    summary: str


class PrivateTruth(BaseModel):
    facts_known: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    non_negotiables: list[str] = Field(default_factory=list)


class DialogueRules(BaseModel):
    baseline_tone: str
    lie_strategy: str
    pressure_triggers: list[str] = Field(default_factory=list)
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
    rescan_history: list[str] = Field(default_factory=list)
    discovered_contexts: list[str] = Field(default_factory=list)
    current_objective: str = "Review the police archive and find the missing pattern."


class ConversationTurn(BaseModel):
    speaker: str
    text: str


class ConversationState(BaseModel):
    suspect_id: str
    trust: int = 50
    guardedness: int = 25
    revealed_fact_ids: list[str] = Field(default_factory=list)
    confronted_evidence_ids: list[str] = Field(default_factory=list)
    memory_summary: str = ""
    transcript: list[ConversationTurn] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    limit: int = 6


class SearchResult(BaseModel):
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


class RescanRequest(BaseModel):
    focus: str = ""


class RescanResponse(BaseModel):
    focus: str
    unlocked_documents: list[str] = Field(default_factory=list)
    unlocked_suspects: list[str] = Field(default_factory=list)
    surfaced_results: list[SearchResult] = Field(default_factory=list)
    discovered_contexts: list[str] = Field(default_factory=list)


class TalkRequest(BaseModel):
    message: str


class DialogueResponse(BaseModel):
    suspect_id: str
    reply: str
    new_context: list[str] = Field(default_factory=list)
    revealed_fact_ids: list[str] = Field(default_factory=list)
    suspicion_level: int
    conversation: ConversationState


class ConfrontRequest(BaseModel):
    evidence_id: str
    message: str = ""


class BoardLinkRequest(BaseModel):
    source_id: str
    target_id: str
    link_type: str
    notes: str = ""


class BoardLinkResponse(BaseModel):
    is_valid: bool
    link_id: str
    unlocked_documents: list[str] = Field(default_factory=list)
    unlocked_suspects: list[str] = Field(default_factory=list)
    board_links: list[str] = Field(default_factory=list)


class TogglePinRequest(BaseModel):
    document_id: str


class SubmitTheoryRequest(BaseModel):
    culprit_id: str
    motive_text: str
    timeline_text: str
    evidence_ids: list[str] = Field(default_factory=list)


class CommunityExcerpt(BaseModel):
    player_alias: str
    excerpt: str


class CommunityStatsResponse(BaseModel):
    case_id: str
    culprit_counts: dict[str, int]
    evidence_counts: dict[str, int]
    excerpts: list[CommunityExcerpt]


class SubmitTheoryResponse(BaseModel):
    saved: bool
    stats: CommunityStatsResponse


class CaseSummary(BaseModel):
    id: str
    title: str
    hook: str
    difficulty: str
    estimated_minutes: int
    version: int
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
    id: str
    title: str
    hook: str
    difficulty: str = "medium"
    estimated_minutes: int = 45


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
        return CaseDetailResponse(
            case=self.summary(),
            police_summary=self.config.police_summary,
            open_questions=self.config.start_state.initial_open_questions,
            archive_domains=self.config.archive_domains,
            location_dossiers=self.config.location_dossiers,
            suspects=suspects,
            documents=documents,
            state=state,
        )


def jsonable_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
