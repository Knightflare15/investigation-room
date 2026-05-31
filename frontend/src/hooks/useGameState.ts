import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import type {
  BoardLinkResponse,
  CaseDetailResponse,
  CaseDocument,
  CaseSummary,
  CommunityStatsResponse,
  ConversationState,
  PlayerCaseState,
  RescanResponse,
  SearchResult,
  Suspect,
  SubmitTheoryResponse,
} from '../types';

export type ContradictionItem = {
  title: string;
  severity: 'high' | 'medium' | 'low';
  source: string;
};

export type ClueCard = {
  text: string;
  type: 'location' | 'intent' | 'behavior' | 'mindset';
};

export type GameStateHook = {
  // identity
  alias: string;
  aliasDraft: string;
  setAliasDraft: (v: string) => void;
  commitAlias: () => void;
  // case selection
  cases: CaseSummary[];
  selectedCaseId: string;
  setSelectedCaseId: (id: string) => void;
  // loaded data
  caseDetail: CaseDetailResponse | null;
  saveState: PlayerCaseState | null;
  conversations: Record<string, ConversationState>;
  communityStats: CommunityStatsResponse | null;
  setCommunityStats: (s: CommunityStatsResponse) => void;
  // selection
  selectedSuspectId: string;
  setSelectedSuspectId: (id: string) => void;
  selectedDocumentId: string;
  setSelectedDocumentId: (id: string) => void;
  // derived
  unlockedDocuments: CaseDocument[];
  unlockedSuspects: Suspect[];
  currentState: PlayerCaseState | null;
  selectedDocument: CaseDocument | undefined;
  selectedSuspect: Suspect | undefined;
  activeConversation: ConversationState | undefined;
  pinnedDocuments: CaseDocument[];
  boardNodes: Array<{ id: string; label: string }>;
  folderCounts: Array<[string, number]>;
  contradictionItems: ContradictionItem[];
  clueCards: ClueCard[];
  followUpPrompts: string[];
  selectedDocumentIsPinned: boolean;
  suspicionValue: number;
  // status
  loading: boolean;
  error: string;
  setError: (e: string) => void;
  // actions
  refreshCaseState: () => Promise<void>;
  reloadPlayableCases: (preferred?: string) => Promise<void>;
  handleTogglePin: (documentId: string) => Promise<void>;
  handleTalk: (message: string) => Promise<void>;
  handleConfront: (evidenceId: string, message: string) => Promise<void>;
  handleBoardLink: (source: string, target: string, linkType: string, notes: string) => Promise<BoardLinkResponse>;
  handleSubmitTheory: (culpritId: string, motive: string, timeline: string) => Promise<SubmitTheoryResponse>;
};

const defaultAlias = localStorage.getItem('investigation-room-alias') || 'Sherlock Holmes';

export function useGameState(): GameStateHook {
  const [alias, setAlias] = useState(defaultAlias);
  const [aliasDraft, setAliasDraft] = useState(defaultAlias);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [caseDetail, setCaseDetail] = useState<CaseDetailResponse | null>(null);
  const [saveState, setSaveState] = useState<PlayerCaseState | null>(null);
  const [conversations, setConversations] = useState<Record<string, ConversationState>>({});
  const [selectedSuspectId, setSelectedSuspectId] = useState('');
  const [selectedDocumentId, setSelectedDocumentId] = useState('');
  const [communityStats, setCommunityStats] = useState<CommunityStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    void loadCases(alias);
  }, [alias]);

  useEffect(() => {
    if (cases.length && !selectedCaseId) {
      setSelectedCaseId(cases[0].id);
    }
  }, [cases, selectedCaseId]);

  useEffect(() => {
    if (selectedCaseId) {
      void loadCase(selectedCaseId, alias);
    }
  }, [selectedCaseId, alias]);

  async function loadCases(activeAlias: string) {
    try {
      const data = await api.listCases(activeAlias);
      setCases(data);
      setError('');
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function loadCase(caseId: string, activeAlias: string) {
    setLoading(true);
    try {
      const [detail, statePayload, community] = await Promise.all([
        api.getCase(caseId, activeAlias),
        api.getSaveState(caseId, activeAlias),
        api.getCommunity(caseId, activeAlias),
      ]);
      setCaseDetail(detail);
      setSaveState(statePayload.state);
      setConversations(Object.fromEntries(statePayload.conversations.map((c) => [c.suspect_id, c])));
      setCommunityStats(community);
      setError('');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshCaseState() {
    if (!selectedCaseId) return;
    const [detail, statePayload] = await Promise.all([
      api.getCase(selectedCaseId, alias),
      api.getSaveState(selectedCaseId, alias),
    ]);
    setCaseDetail(detail);
    setSaveState(statePayload.state);
    setConversations(Object.fromEntries(statePayload.conversations.map((c) => [c.suspect_id, c])));
  }

  async function reloadPlayableCases(preferredCaseId?: string) {
    const nextCases = await api.listCases(alias);
    setCases(nextCases);
    const nextId = preferredCaseId || selectedCaseId || nextCases[0]?.id || '';
    if (nextId) {
      setSelectedCaseId(nextId);
      await loadCase(nextId, alias);
    }
  }

  function commitAlias() {
    localStorage.setItem('investigation-room-alias', aliasDraft);
    setAlias(aliasDraft);
  }

  async function handleTogglePin(documentId: string) {
    if (!selectedCaseId) return;
    try {
      const nextState = await api.togglePin(selectedCaseId, alias, documentId);
      setSaveState(nextState);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleTalk(message: string) {
    if (!selectedCaseId || !selectedSuspect || !message.trim()) return;
    try {
      const response = await api.talk(selectedCaseId, selectedSuspect.id, alias, message);
      setConversations((current) => ({ ...current, [selectedSuspect.id]: response.conversation }));
      setSaveState((current) => (current ? { ...current, suspicion_level: response.suspicion_level } : current));
      await refreshCaseState();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleConfront(evidenceId: string, message: string) {
    if (!selectedCaseId || !selectedSuspect || !evidenceId) return;
    try {
      const response = await api.confront(selectedCaseId, selectedSuspect.id, alias, evidenceId, message);
      setConversations((current) => ({ ...current, [selectedSuspect.id]: response.conversation }));
      setSaveState((current) => (current ? { ...current, suspicion_level: response.suspicion_level } : current));
      await refreshCaseState();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleBoardLink(source: string, target: string, linkType: string, notes: string): Promise<BoardLinkResponse> {
    if (!selectedCaseId) throw new Error('No case selected');
    const response = await api.addBoardLink(selectedCaseId, alias, source, target, linkType, notes);
    await refreshCaseState();
    return response;
  }

  async function handleSubmitTheory(culpritId: string, motive: string, timeline: string): Promise<SubmitTheoryResponse> {
    if (!selectedCaseId || !currentState) throw new Error('No case loaded');
    const response = await api.submitTheory(selectedCaseId, alias, culpritId, motive, timeline, currentState.pinned_evidence_ids);
    setCommunityStats(response.stats);
    await refreshCaseState();
    return response;
  }

  // ---- derived state ------------------------------------------------ //

  const unlockedDocuments = caseDetail?.documents ?? [];
  const unlockedSuspects = caseDetail?.suspects ?? [];
  const currentState = saveState ?? caseDetail?.state ?? null;
  const selectedDocument = unlockedDocuments.find((d) => d.id === selectedDocumentId) ?? unlockedDocuments[0];
  const selectedSuspect = unlockedSuspects.find((s) => s.id === selectedSuspectId) ?? unlockedSuspects[0];
  const activeConversation = selectedSuspect ? conversations[selectedSuspect.id] : undefined;

  useEffect(() => {
    if (!selectedDocumentId && unlockedDocuments[0]) setSelectedDocumentId(unlockedDocuments[0].id);
    if (!selectedSuspectId && unlockedSuspects[0]) setSelectedSuspectId(unlockedSuspects[0].id);
  }, [selectedDocumentId, selectedSuspectId, unlockedDocuments, unlockedSuspects]);

  const pinnedDocuments = useMemo(
    () => (currentState ? unlockedDocuments.filter((d) => currentState.pinned_evidence_ids.includes(d.id)) : []),
    [currentState, unlockedDocuments],
  );

  const boardNodes = useMemo(
    () => [
      { id: 'victim', label: 'Victim' },
      ...unlockedSuspects.map((s) => ({ id: s.id, label: s.display_name })),
      ...unlockedDocuments.map((d) => ({ id: d.id, label: d.title })),
    ],
    [unlockedDocuments, unlockedSuspects],
  );

  const folderCounts = useMemo(() => {
    const counts = new Map<string, number>();
    unlockedDocuments.forEach((d) => counts.set(d.folder, (counts.get(d.folder) ?? 0) + 1));
    return Array.from(counts.entries());
  }, [unlockedDocuments]);

  const contradictionItems = useMemo<ContradictionItem[]>(() => {
    const seeds = currentState?.discovered_contexts ?? [];
    return seeds
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
  }, [currentState?.discovered_contexts]);

  const clueCards = useMemo<ClueCard[]>(() => {
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
    return [...tagClues, ...revealed].slice(0, 4);
  }, [selectedDocument?.entity_tags, activeConversation?.revealed_fact_ids]);

  const followUpPrompts = useMemo(() => {
    const base = selectedDocument?.entity_tags?.slice(0, 4) ?? [];
    return base.length ? base.map((tag) => `Ask about ${tag}`) : ['Press the timeline', 'Compare to evidence', 'Test the motive'];
  }, [selectedDocument?.entity_tags]);

  const selectedDocumentIsPinned = Boolean(selectedDocument && currentState?.pinned_evidence_ids.includes(selectedDocument.id));
  const suspicionValue = currentState?.suspicion_level ?? 0;

  return {
    alias,
    aliasDraft,
    setAliasDraft,
    commitAlias,
    cases,
    selectedCaseId,
    setSelectedCaseId,
    caseDetail,
    saveState,
    conversations,
    communityStats,
    setCommunityStats,
    selectedSuspectId,
    setSelectedSuspectId,
    selectedDocumentId,
    setSelectedDocumentId,
    unlockedDocuments,
    unlockedSuspects,
    currentState,
    selectedDocument,
    selectedSuspect,
    activeConversation,
    pinnedDocuments,
    boardNodes,
    folderCounts,
    contradictionItems,
    clueCards,
    followUpPrompts,
    selectedDocumentIsPinned,
    suspicionValue,
    loading,
    error,
    setError,
    refreshCaseState,
    reloadPlayableCases,
    handleTogglePin,
    handleTalk,
    handleConfront,
    handleBoardLink,
    handleSubmitTheory,
  };
}
