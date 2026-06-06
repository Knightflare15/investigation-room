import { createContext, type ReactNode, useContext, useReducer } from 'react';
import type {
  CaseDetailResponse,
  CaseDocument,
  CaseSummary,
  ClueCard,
  CommunityStatsResponse,
  ContradictionItem,
  ConversationState,
  ConversationTurn,
  PlayerCaseState,
  RescanResponse,
  SearchResult,
  SessionRole,
  Suspect,
} from '../types';

export type ViewMode = 'intake' | 'archive' | 'interrogation' | 'board' | 'submission' | 'community' | 'authoring';

type MediaPreview = { src: string; title: string; eyebrow: string; summary: string };

export type GameState = {
  isAuthenticated: boolean;
  alias: string;
  aliasDraft: string;
  sessionRole: SessionRole;
  cases: CaseSummary[];
  draftCases: CaseSummary[];
  pendingCases: CaseSummary[];
  caseSearchQuery: string;
  selectedCaseId: string;
  caseDetail: CaseDetailResponse | null;
  saveState: PlayerCaseState | null;
  conversations: Record<string, ConversationState>;
  selectedView: ViewMode;
  selectedSuspectId: string;
  selectedDocumentId: string;
  selectedLocationId: string;
  searchQuery: string;
  searchResults: SearchResult[];
  lastGroundingResults: SearchResult[];
  leadMessages: string[];
  rescanResults: RescanResponse | null;
  communityStats: CommunityStatsResponse | null;
  mediaPreview: MediaPreview | null;
  loading: boolean;
  error: string;
  // derived — kept in state so views don't recompute independently
  unlockedSuspects: Suspect[];
  pinnedDocuments: CaseDocument[];
  boardNodes: Array<{ id: string; label: string }>;
  folderCounts: Array<[string, number]>;
  contradictionItems: ContradictionItem[];
  clueCards: ClueCard[];
  followUpPrompts: string[];
  suspicionValue: number;
};

export type GameAction =
  | { type: 'SET_ALIAS_DRAFT'; payload: string }
  | { type: 'SET_AUTH_SESSION'; payload: { alias: string; role: SessionRole } }
  | { type: 'LOG_OUT' }
  | { type: 'SET_SESSION_ROLE'; payload: SessionRole }
  | { type: 'SET_VIEW'; payload: ViewMode }
  | { type: 'CLEAR_CASE_CONTEXT' }
  | { type: 'SET_SELECTED_CASE'; payload: string }
  | { type: 'SET_SELECTED_SUSPECT'; payload: string }
  | { type: 'SET_SELECTED_DOCUMENT'; payload: string }
  | { type: 'SET_SELECTED_LOCATION'; payload: string }
  | { type: 'SET_CASES'; payload: CaseSummary[] }
  | { type: 'SET_DRAFT_CASES'; payload: CaseSummary[] }
  | { type: 'SET_PENDING_CASES'; payload: CaseSummary[] }
  | { type: 'SET_CASE_SEARCH_QUERY'; payload: string }
  | { type: 'SET_CASE_DETAIL'; payload: CaseDetailResponse }
  | { type: 'SET_SAVE_STATE'; payload: PlayerCaseState }
  | { type: 'SET_CONVERSATIONS'; payload: Record<string, ConversationState> }
  | { type: 'UPDATE_CONVERSATION'; payload: ConversationState }
  | { type: 'SET_COMMUNITY_STATS'; payload: CommunityStatsResponse }
  | { type: 'SET_SEARCH_QUERY'; payload: string }
  | { type: 'SET_SEARCH_RESULTS'; payload: SearchResult[] }
  | { type: 'SET_LAST_GROUNDING_RESULTS'; payload: SearchResult[] }
  | { type: 'SET_LEAD_MESSAGES'; payload: string[] }
  | { type: 'SET_RESCAN_RESULTS'; payload: RescanResponse }
  | { type: 'CLEAR_RESCAN_RESULTS' }
  | { type: 'SET_MEDIA_PREVIEW'; payload: MediaPreview | null }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'APPEND_TRANSCRIPT_TURN'; payload: { suspectId: string; turn: ConversationTurn } }
  | { type: 'UPDATE_STREAMING_REPLY'; payload: { suspectId: string; text: string } };

const savedAlias = localStorage.getItem('investigation-room-alias') || '';

const initialState: GameState = {
  isAuthenticated: false,
  alias: savedAlias,
  aliasDraft: savedAlias,
  sessionRole: 'player',
  cases: [],
  draftCases: [],
  pendingCases: [],
  caseSearchQuery: '',
  selectedCaseId: '',
  caseDetail: null,
  saveState: null,
  conversations: {},
  selectedView: 'interrogation',
  selectedSuspectId: '',
  selectedDocumentId: '',
  selectedLocationId: '',
  searchQuery: '',
  searchResults: [],
  lastGroundingResults: [],
  leadMessages: [],
  rescanResults: null,
  communityStats: null,
  mediaPreview: null,
  loading: false,
  error: '',
  unlockedSuspects: [],
  pinnedDocuments: [],
  boardNodes: [],
  folderCounts: [],
  contradictionItems: [],
  clueCards: [],
  followUpPrompts: [],
  suspicionValue: 0,
};

export function gameReducer(state: GameState, action: GameAction): GameState {
  switch (action.type) {
    case 'SET_ALIAS_DRAFT':
      return { ...state, aliasDraft: action.payload };
    case 'SET_AUTH_SESSION':
      localStorage.setItem('investigation-room-alias', action.payload.alias);
      return {
        ...state,
        isAuthenticated: true,
        alias: action.payload.alias,
        aliasDraft: action.payload.alias,
        sessionRole: action.payload.role,
      };
    case 'LOG_OUT':
      localStorage.removeItem('investigation-room-alias');
      return {
        ...initialState,
        alias: '',
        aliasDraft: '',
        error: '',
      };
    case 'SET_SESSION_ROLE':
      return { ...state, sessionRole: action.payload };
    case 'SET_VIEW':
      return { ...state, selectedView: action.payload };
    case 'CLEAR_CASE_CONTEXT':
      return {
        ...state,
        selectedCaseId: '',
        caseDetail: null,
        saveState: null,
        conversations: {},
        selectedSuspectId: '',
        selectedDocumentId: '',
        selectedLocationId: '',
        searchQuery: '',
        searchResults: [],
        lastGroundingResults: [],
        leadMessages: [],
        rescanResults: null,
        communityStats: null,
        unlockedSuspects: [],
        pinnedDocuments: [],
        boardNodes: [],
        folderCounts: [],
        contradictionItems: [],
        clueCards: [],
        followUpPrompts: [],
        suspicionValue: 0,
      };
    case 'SET_SELECTED_CASE':
      return {
        ...state,
        selectedCaseId: action.payload,
        selectedSuspectId: '',
        selectedDocumentId: '',
        selectedLocationId: '',
        leadMessages: [],
      };
    case 'SET_SELECTED_SUSPECT':
      return { ...state, selectedSuspectId: action.payload };
    case 'SET_SELECTED_DOCUMENT':
      return { ...state, selectedDocumentId: action.payload };
    case 'SET_SELECTED_LOCATION':
      return { ...state, selectedLocationId: action.payload };
    case 'SET_CASES':
      return { ...state, cases: action.payload };
    case 'SET_DRAFT_CASES':
      return { ...state, draftCases: action.payload };
    case 'SET_PENDING_CASES':
      return { ...state, pendingCases: action.payload };
    case 'SET_CASE_SEARCH_QUERY':
      return { ...state, caseSearchQuery: action.payload };
    case 'SET_CASE_DETAIL': {
      const detail = action.payload;
      const unlockedSuspects = detail.suspects;
      const selectedDocumentId = detail.documents.some((document) => document.id === state.selectedDocumentId)
        ? state.selectedDocumentId
        : detail.documents[0]?.id || '';
      const selectedLocationId = detail.location_dossiers.some((location) => location.id === state.selectedLocationId)
        ? state.selectedLocationId
        : detail.location_dossiers[0]?.id || '';
      const selectedSuspectId = detail.suspects.some((suspect) => suspect.id === state.selectedSuspectId)
        ? state.selectedSuspectId
        : detail.suspects[0]?.id || '';
      const boardNodes: Array<{ id: string; label: string }> = [
        { id: 'victim', label: 'Victim' },
        ...detail.suspects.map((s) => ({ id: s.id, label: s.display_name })),
        ...detail.documents.map((d) => ({ id: d.id, label: d.title })),
      ];
      const folderCounts: Array<[string, number]> = Array.from(
        detail.documents.reduce((acc, d) => {
          acc.set(d.folder, (acc.get(d.folder) ?? 0) + 1);
          return acc;
        }, new Map<string, number>()),
      );
      return {
        ...state,
        caseDetail: detail,
        lastGroundingResults: [],
        unlockedSuspects,
        boardNodes,
        folderCounts,
        selectedDocumentId,
        selectedLocationId,
        selectedSuspectId,
        suspicionValue: state.saveState?.suspicion_level ?? detail.state.suspicion_level,
      };
    }
    case 'SET_SAVE_STATE': {
      const ss = action.payload;
      const unlockedDocuments = state.caseDetail?.documents ?? [];
      const pinnedDocuments = unlockedDocuments.filter((d) => ss.pinned_evidence_ids.includes(d.id));
      const seeds = ss.discovered_contexts;
      const contradictionItems: ContradictionItem[] = seeds
        .slice(-4)
        .reverse()
        .map((context, index) => ({
          title:
            index === 0
              ? `Fresh inconsistency around ${context}`
              : index === 1
                ? `${context} keeps resurfacing in separate accounts`
                : `${context} may connect two statements that should not align`,
          severity: (index === 0 ? 'high' : index === 1 ? 'medium' : 'low') as ContradictionItem['severity'],
          source:
            index === 0
              ? 'Derived from interrogation and archive cross-checks'
              : 'Pulled from rescan context and evidence overlap',
        }));
      return {
        ...state,
        saveState: ss,
        suspicionValue: ss.suspicion_level,
        pinnedDocuments,
        contradictionItems,
      };
    }
    case 'SET_CONVERSATIONS': {
      const convs = action.payload;
      const selectedSuspect =
        state.caseDetail?.suspects.find((s) => s.id === state.selectedSuspectId) ??
        state.caseDetail?.suspects[0];
      const activeConversation = selectedSuspect ? convs[selectedSuspect.id] : undefined;
      const selectedDocument =
        state.caseDetail?.documents.find((d) => d.id === state.selectedDocumentId) ??
        state.caseDetail?.documents[0];
      const tagClues = (selectedDocument?.entity_tags ?? []).slice(0, 4).map((tag, index) => ({
        text:
          index === 0
            ? `${tag} appears central to the document's tension.`
            : index === 1
              ? `${tag} may suggest motive, location, or pressure.`
              : `${tag} should be tested against statements and ledgers.`,
        type: (index === 0 ? 'location' : index === 1 ? 'intent' : 'behavior') as ClueCard['type'],
      }));
      const revealed = (activeConversation?.revealed_fact_ids ?? []).slice(0, 2).map((factId) => ({
        text: `Conversation breakthrough recorded under ${factId}.`,
        type: 'mindset' as ClueCard['type'],
      }));
      const clueCards = [...tagClues, ...revealed].slice(0, 4);
      const base = selectedDocument?.entity_tags?.slice(0, 4) ?? [];
      const followUpPrompts = base.length
        ? base.map((tag) => `Ask about ${tag}`)
        : ['Press the timeline', 'Compare to evidence', 'Test the motive'];
      return { ...state, conversations: convs, clueCards, followUpPrompts };
    }
    case 'UPDATE_CONVERSATION': {
      const convs = { ...state.conversations, [action.payload.suspect_id]: action.payload };
      return gameReducer({ ...state }, { type: 'SET_CONVERSATIONS', payload: convs });
    }
    case 'SET_COMMUNITY_STATS':
      return { ...state, communityStats: action.payload };
    case 'SET_SEARCH_QUERY':
      return { ...state, searchQuery: action.payload };
    case 'SET_SEARCH_RESULTS':
      return { ...state, searchResults: action.payload };
    case 'SET_LAST_GROUNDING_RESULTS':
      return { ...state, lastGroundingResults: action.payload };
    case 'SET_LEAD_MESSAGES':
      return { ...state, leadMessages: action.payload };
    case 'SET_RESCAN_RESULTS':
      return { ...state, rescanResults: action.payload };
    case 'CLEAR_RESCAN_RESULTS':
      return { ...state, rescanResults: null };
    case 'SET_MEDIA_PREVIEW':
      return { ...state, mediaPreview: action.payload };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, loading: false };
    case 'CLEAR_ERROR':
      return { ...state, error: '' };
    case 'APPEND_TRANSCRIPT_TURN': {
      const { suspectId, turn } = action.payload;
      const existing: ConversationState = state.conversations[suspectId] ?? {
        suspect_id: suspectId,
        trust: 50,
        guardedness: 25,
        revealed_fact_ids: [],
        confronted_evidence_ids: [],
        memory_summary: '',
        transcript: [],
      };
      return {
        ...state,
        conversations: {
          ...state.conversations,
          [suspectId]: { ...existing, transcript: [...existing.transcript, turn] },
        },
      };
    }
    case 'UPDATE_STREAMING_REPLY': {
      const { suspectId, text } = action.payload;
      const existing = state.conversations[suspectId];
      if (!existing || !existing.transcript.length) return state;
      const transcript = [...existing.transcript];
      transcript[transcript.length - 1] = { ...transcript[transcript.length - 1], text };
      return {
        ...state,
        conversations: { ...state.conversations, [suspectId]: { ...existing, transcript } },
      };
    }
    default:
      return state;
  }
}

type GameContextValue = { state: GameState; dispatch: React.Dispatch<GameAction> };
const GameContext = createContext<GameContextValue | null>(null);

export function GameProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  return <GameContext.Provider value={{ state, dispatch }}>{children}</GameContext.Provider>;
}

export function useGame(): GameContextValue {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within a GameProvider');
  return ctx;
}
