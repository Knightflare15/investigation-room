export type ArchiveDomain = {
  id: string;
  label: string;
  image_path?: string | null;
  image_url?: string | null;
  summary: string;
};

export type LocationDossier = {
  id: string;
  label: string;
  summary: string;
  image_path?: string | null;
  image_url?: string | null;
  linked_document_ids: string[];
  unlock_rule?: string | null;
};

export type CaseSummary = {
  id: string;
  title: string;
  hook: string;
  difficulty: string;
  estimated_minutes: number;
  version: number;
  status: string;
  owner_alias?: string | null;
  owner_user_id?: string | null;
  cover_image_path?: string | null;
  cover_image_url?: string | null;
};

export type SessionRole = 'player' | 'admin';

export type SessionInfo = {
  alias: string;
  role: SessionRole;
};

export type SessionStatus = {
  alias: string;
  role: SessionRole;
};

export type AuthRegisterRequest = {
  alias: string;
  password: string;
};

export type AuthLoginRequest = {
  alias: string;
  password: string;
};

export type PublicProfile = {
  role: string;
  summary: string;
};

export type PersonalityProfile = {
  traits: string[];
  speaking_style: string;
  catchphrase: string;
  verbal_tells: string[];
  outward_goal: string;
  protective_target: string;
  protective_reason: string;
};

export type Suspect = {
  id: string;
  display_name: string;
  unlock_rule: string | null;
  portrait_key?: string | null;
  image_path?: string | null;
  image_url?: string | null;
  public_profile: PublicProfile;
};

export type CaseDocument = {
  id: string;
  case_id: string;
  title: string;
  folder: string;
  doc_type: string;
  source_label: string;
  unlock_rule?: string | null;
  entity_tags: string[];
  summary: string;
  body: string;
  markdown_path: string;
  image_path?: string | null;
  image_url?: string | null;
};

export type PlayerCaseState = {
  player_alias: string;
  case_id: string;
  suspicion_level: number;
  unlocked_document_ids: string[];
  unlocked_suspect_ids: string[];
  pinned_evidence_ids: string[];
  board_links: string[];
  completed_deduction_ids: string[];
  rescan_history: string[];
  discovered_contexts: string[];
  current_objective: string;
};

export type DeductionMessage = {
  id: string;
  title: string;
  message: string;
  objective?: string | null;
  unlocked_documents: string[];
  unlocked_suspects: string[];
};

export type ConversationTurn = {
  speaker: string;
  text: string;
  citations?: string[];
};

export type ConversationState = {
  suspect_id: string;
  trust: number;
  guardedness: number;
  revealed_fact_ids: string[];
  confronted_evidence_ids: string[];
  memory_summary: string;
  transcript: ConversationTurn[];
};

export type CaseDetailResponse = {
  case: CaseSummary;
  police_summary: string;
  open_questions: string[];
  archive_domains: ArchiveDomain[];
  location_dossiers: LocationDossier[];
  suspects: Suspect[];
  documents: CaseDocument[];
  state: PlayerCaseState;
  completed_deductions: DeductionMessage[];
};

export type SaveStateResponse = {
  state: PlayerCaseState;
  conversations: ConversationState[];
};

export type SearchResult = {
  chunk_id: string;
  document_id: string;
  title: string;
  folder: string;
  snippet: string;
  score: number;
  matched_entity_tags: string[];
};

export type SearchResponse = {
  query: string;
  results: SearchResult[];
  discovered_contexts: string[];
  deduction_messages: DeductionMessage[];
};

export type RescanResponse = {
  focus: string;
  location_id?: string | null;
  unlocked_documents: string[];
  unlocked_suspects: string[];
  surfaced_results: SearchResult[];
  discovered_contexts: string[];
  deduction_messages: DeductionMessage[];
};

export type DialogueResponse = {
  suspect_id: string;
  reply: string;
  new_context: string[];
  revealed_fact_ids: string[];
  grounding_results: SearchResult[];
  unlocked_documents: string[];
  unlocked_suspects: string[];
  lead_messages: string[];
  deduction_messages: DeductionMessage[];
  suspicion_level: number;
  conversation: ConversationState;
};

export type CommunityExcerpt = {
  player_alias: string;
  excerpt: string;
};

export type CommunityStatsResponse = {
  case_id: string;
  culprit_counts: Record<string, number>;
  evidence_counts: Record<string, number>;
  excerpts: CommunityExcerpt[];
};

export type SubmitTheoryResponse = {
  saved: boolean;
  stats: CommunityStatsResponse;
  score: TheoryScore;
};

export type CanonicalTruth = {
  culprit_id: string;
  motive_summary: string;
  timeline_summary: string;
  motive_concepts: string[];
  timeline_concepts: string[];
  evidence_ids: string[];
};

export type ScoreCategory = {
  earned: number;
  possible: number;
  feedback: string;
};

export type TheoryScore = {
  total: number;
  possible: number;
  verdict: string;
  culprit: ScoreCategory;
  motive: ScoreCategory;
  timeline: ScoreCategory;
  evidence: ScoreCategory;
  canonical_truth: CanonicalTruth;
};

export type RescanRule = {
  id: string;
  trigger: { type: string; value: string };
  effects: {
    unlock_document_ids: string[];
    unlock_suspect_ids: string[];
    surface_document_ids: string[];
  };
};

export type SubmissionConfig = {
  required_fields: string[];
  min_evidence_count: number;
  canonical_truth: CanonicalTruth;
};

export type BoardLinkDefinition = {
  id: string;
  source_id: string;
  target_id: string;
  link_type: string;
  notes: string;
};

export type DeductionRequirements = {
  document_ids: string[];
  context_values: string[];
  board_link_ids: string[];
  suspect_ids: string[];
  revealed_fact_ids: string[];
};

export type DeductionBeat = {
  id: string;
  title: string;
  payoff: string;
  requirements: DeductionRequirements;
  effects: {
    unlock_document_ids: string[];
    unlock_suspect_ids: string[];
    surface_document_ids: string[];
  };
  objective?: string | null;
};

export type PrivateTruth = {
  facts_known: string[];
  secrets: string[];
  non_negotiables: string[];
};

export type DialogueRules = {
  baseline_tone: string;
  lie_strategy: string;
  pressure_triggers: string[];
  fact_reveal_rules: Array<{
    fact_id: string;
    topics: string[];
    evidence_ids: string[];
    min_trust: number;
    max_guardedness: number;
  }>;
  shut_down_threshold: number;
};

export type MemoryRules = {
  remember_topics: boolean;
  remember_confrontations: boolean;
  remember_detective_tone: boolean;
};

export type AuthoringSuspect = Suspect & {
  personality_profile: PersonalityProfile;
  private_truth: PrivateTruth;
  dialogue_rules: DialogueRules;
  memory_rules: MemoryRules;
};

export type AuthoringCaseConfig = {
  id: string;
  title: string;
  hook: string;
  difficulty: string;
  estimated_minutes: number;
  version: number;
  status: string;
  owner_alias?: string | null;
  police_summary: string;
  cover_image_path?: string | null;
  cover_image_url?: string | null;
  start_state: {
    initial_suspect_ids: string[];
    initial_document_ids: string[];
    initial_open_questions: string[];
  };
  archive_domains: ArchiveDomain[];
  location_dossiers: LocationDossier[];
  rescan_rules: RescanRule[];
  submission: SubmissionConfig;
  valid_board_links: BoardLinkDefinition[];
  deduction_beats: DeductionBeat[];
};

export type AssetEntry = {
  path: string;
  url: string;
  kind: string;
};

export type AuthoringBundle = {
  case: AuthoringCaseConfig;
  suspects: AuthoringSuspect[];
  documents: CaseDocument[];
  prompts: Record<string, string>;
  assets: AssetEntry[];
};

export type CreateCaseRequest = {
  id: string;
  title: string;
  hook: string;
  difficulty: string;
  estimated_minutes: number;
};

export type CaseBriefInput = {
  case_id: string;
  brief: string;
  difficulty: string;
  estimated_minutes: number;
};

export type CaseIngestionInput = {
  case_id: string;
  source_text: string;
  difficulty: string;
  estimated_minutes: number;
  title_hint?: string | null;
  focus_section?: string | null;
};

export type SourceGrounding = {
  generated_field: string;
  generated_value: string;
  supporting_chunk_ids: string[];
  preview: string;
  confidence: 'high' | 'medium' | 'fallback';
  method: 'gemini' | 'ollama' | 'heuristic';
};

export type GenerateCaseDraftResponse = {
  bundle: AuthoringBundle;
  warnings: string[];
};

export type CaseIngestionResponse = GenerateCaseDraftResponse & {
  groundings: SourceGrounding[];
};
