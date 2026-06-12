import { API_BASE, api, authHeaders } from '../api';
import type { SubmitTheoryResponse } from '../types';
import { useGame } from './GameContext';

export function useGameActions() {
  const { state, dispatch } = useGame();

  function surfaceFeedback(leadMessages: string[] = [], deductionMessages: Array<{ title: string; message: string }> = []) {
    const messages = [...leadMessages, ...deductionMessages.map((deduction) => `${deduction.title}: ${deduction.message}`)];
    if (messages.length) {
      dispatch({ type: 'ADD_ACTIVITY_MESSAGES', payload: messages });
    }
  }

  async function restoreSession() {
    if (!state.aliasDraft.trim()) return false;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const session = await api.getSession(state.aliasDraft.trim());
      dispatch({ type: 'SET_AUTH_SESSION', payload: { alias: session.alias, role: session.role } });
      dispatch({ type: 'CLEAR_ERROR' });
      return true;
    } catch {
      return false;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }

  async function register(alias: string, password: string) {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const session = await api.register({ alias, password });
      dispatch({ type: 'SET_AUTH_SESSION', payload: { alias: session.alias, role: session.role } });
      dispatch({ type: 'CLEAR_ERROR' });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
      throw e;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }

  async function login(alias: string, password: string) {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const session = await api.login({ alias, password });
      dispatch({ type: 'SET_AUTH_SESSION', payload: { alias: session.alias, role: session.role } });
      dispatch({ type: 'CLEAR_ERROR' });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
      throw e;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }

  function logout() {
    if (state.alias) {
      api.logout(state.alias);
    }
    dispatch({ type: 'LOG_OUT' });
  }

  async function loadCases() {
    if (!state.isAuthenticated) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const session = await api.getSession(state.alias);
      dispatch({ type: 'SET_SESSION_ROLE', payload: session.role });
      const [cases, authoringCases, pendingCases] = await Promise.all([
        api.listCases(state.alias),
        api.listAuthoringCases(state.alias),
        session.role === 'admin' ? api.listPendingCases(state.alias) : Promise.resolve([]),
      ]);
      dispatch({ type: 'SET_CASES', payload: cases });
      dispatch({
        type: 'SET_DRAFT_CASES',
        payload: authoringCases
          .map((bundle) => bundle.case)
          .filter((caseSummary) => caseSummary.status === 'draft' && caseSummary.owner_alias === state.alias),
      });
      dispatch({ type: 'SET_PENDING_CASES', payload: pendingCases });
      dispatch({ type: 'CLEAR_ERROR' });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }

  async function loadCase(caseId: string) {
    if (!state.isAuthenticated) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const [detail, statePayload, community] = await Promise.all([
        api.getCase(caseId, state.alias),
        api.getSaveState(caseId, state.alias),
        api.getCommunity(caseId, state.alias),
      ]);
      dispatch({ type: 'SET_CASE_DETAIL', payload: detail });
      dispatch({ type: 'SET_SAVE_STATE', payload: statePayload.state });
      dispatch({
        type: 'SET_CONVERSATIONS',
        payload: Object.fromEntries(statePayload.conversations.map((c) => [c.suspect_id, c])),
      });
      dispatch({ type: 'SET_COMMUNITY_STATS', payload: community });
      dispatch({ type: 'CLEAR_ERROR' });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }

  async function refreshCaseState() {
    if (!state.isAuthenticated || !state.selectedCaseId) return;
    const [detail, statePayload] = await Promise.all([
      api.getCase(state.selectedCaseId, state.alias),
      api.getSaveState(state.selectedCaseId, state.alias),
    ]);
    dispatch({ type: 'SET_CASE_DETAIL', payload: detail });
    dispatch({ type: 'SET_SAVE_STATE', payload: statePayload.state });
    dispatch({
      type: 'SET_CONVERSATIONS',
      payload: Object.fromEntries(statePayload.conversations.map((c) => [c.suspect_id, c])),
    });
  }

  async function reloadPlayableCases(preferredCaseId?: string) {
    if (!state.isAuthenticated) return;
    const [session, nextCases, authoringCases] = await Promise.all([
      api.getSession(state.alias),
      api.listCases(state.alias),
      api.listAuthoringCases(state.alias),
    ]);
    const nextPending = session.role === 'admin' ? await api.listPendingCases(state.alias) : [];
    dispatch({ type: 'SET_SESSION_ROLE', payload: session.role });
    dispatch({ type: 'SET_CASES', payload: nextCases });
    dispatch({
      type: 'SET_DRAFT_CASES',
      payload: authoringCases
        .map((bundle) => bundle.case)
        .filter((caseSummary) => caseSummary.status === 'draft' && caseSummary.owner_alias === state.alias),
    });
    dispatch({ type: 'SET_PENDING_CASES', payload: nextPending });
    const nextId = preferredCaseId || state.selectedCaseId || nextCases[0]?.id || '';
    if (nextId) {
      dispatch({ type: 'SET_SELECTED_CASE', payload: nextId });
      await loadCase(nextId);
    }
  }

  async function handleSearch() {
    if (!state.isAuthenticated || !state.selectedCaseId || !state.searchQuery.trim()) return;
    try {
      const response = await api.search(state.selectedCaseId, state.alias, state.searchQuery);
      dispatch({ type: 'SET_SEARCH_RESULTS', payload: response.results });
      surfaceFeedback([], response.deduction_messages);
      if (response.results[0]) dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: response.results[0].document_id });
      await refreshCaseState();
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleRescan() {
    if (!state.isAuthenticated || !state.selectedCaseId || !state.rescanFocus.trim()) return;
    try {
      const response = await api.rescan(
        state.selectedCaseId,
        state.alias,
        state.rescanFocus,
        state.selectedLocationId,
      );
      dispatch({ type: 'SET_RESCAN_RESULTS', payload: response });
      const rescanLeads = [
        ...response.unlocked_documents.map((id) => {
          const title = state.caseDetail?.documents.find((document) => document.id === id)?.title ?? id;
          return `New record surfaced: ${title}.`;
        }),
        ...response.unlocked_suspects.map((id) => {
          const name = state.caseDetail?.suspects.find((suspect) => suspect.id === id)?.display_name ?? id;
          return `New person of interest: ${name}.`;
        }),
      ];
      surfaceFeedback(rescanLeads, response.deduction_messages);
      await refreshCaseState();
      if (response.unlocked_suspects[0]) dispatch({ type: 'SET_SELECTED_SUSPECT', payload: response.unlocked_suspects[0] });
      if (response.unlocked_documents[0]) dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: response.unlocked_documents[0] });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleTalk(message: string): Promise<void> {
    const suspectId = state.selectedSuspectId;
    if (!state.isAuthenticated || !state.selectedCaseId || !suspectId || !message.trim()) return;
    try {
      const response = await api.talk(state.selectedCaseId, suspectId, state.alias, message);
      dispatch({ type: 'UPDATE_CONVERSATION', payload: response.conversation });
      surfaceFeedback(response.lead_messages, response.deduction_messages);
      if (state.saveState) {
        dispatch({
          type: 'SET_SAVE_STATE',
          payload: { ...state.saveState, suspicion_level: response.suspicion_level },
        });
      }
      await refreshCaseState();
      if (response.unlocked_suspects[0]) dispatch({ type: 'SET_SELECTED_SUSPECT', payload: response.unlocked_suspects[0] });
      if (response.unlocked_documents[0]) dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: response.unlocked_documents[0] });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function beginInterrogationSession(suspectId: string): Promise<void> {
    if (!state.isAuthenticated || !state.selectedCaseId || !suspectId) return;
    try {
      const conversation = await api.beginInterrogationSession(state.selectedCaseId, suspectId, state.alias);
      dispatch({ type: 'UPDATE_CONVERSATION', payload: conversation });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleTalkStreaming(message: string): Promise<void> {
    const { selectedCaseId, selectedSuspectId, alias } = state;
    if (!state.isAuthenticated || !selectedCaseId || !selectedSuspectId || !message.trim()) return;
    // Optimistically show the detective's turn plus an empty suspect bubble to fill in.
    dispatch({ type: 'APPEND_TRANSCRIPT_TURN', payload: { suspectId: selectedSuspectId, turn: { speaker: 'detective', text: message } } });
    const suspectName = state.caseDetail?.suspects.find((s) => s.id === selectedSuspectId)?.display_name ?? 'Suspect';
    dispatch({ type: 'APPEND_TRANSCRIPT_TURN', payload: { suspectId: selectedSuspectId, turn: { speaker: suspectName, text: '' } } });

    let accumulated = '';
    try {
      const response = await fetch(`${API_BASE}/cases/${selectedCaseId}/suspects/${selectedSuspectId}/talk/stream`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(await authHeaders(alias)) },
        body: JSON.stringify({ message }),
      });
      if (!response.ok || !response.body) throw new Error('stream unavailable');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const event = JSON.parse(line.slice(6)) as {
            type: 'grounding' | 'token' | 'leads' | 'error' | 'done';
            text?: string;
            unlocked_documents?: string[];
            unlocked_suspects?: string[];
            lead_messages?: string[];
            deduction_messages?: Array<{ title: string; message: string }>;
          };
          if (event.type === 'leads') {
            surfaceFeedback(event.lead_messages, event.deduction_messages);
            if (event.unlocked_suspects?.[0]) dispatch({ type: 'SET_SELECTED_SUSPECT', payload: event.unlocked_suspects[0] });
            if (event.unlocked_documents?.[0]) dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: event.unlocked_documents[0] });
            continue;
          }
          if (event.type === 'token' && event.text) {
            accumulated += event.text;
            dispatch({ type: 'UPDATE_STREAMING_REPLY', payload: { suspectId: selectedSuspectId, text: accumulated } });
          }
        }
        if (done) break;
      }
      await refreshCaseState();
    } catch {
      // Streaming unavailable — fall back to the standard non-streaming talk flow.
      await handleTalk(message);
    }
  }

  async function handleConfront(evidenceId: string, message: string): Promise<void> {
    const suspectId = state.selectedSuspectId;
    if (!state.isAuthenticated || !state.selectedCaseId || !suspectId || !evidenceId) return;
    try {
      const response = await api.confront(state.selectedCaseId, suspectId, state.alias, evidenceId, message);
      dispatch({ type: 'UPDATE_CONVERSATION', payload: response.conversation });
      surfaceFeedback(response.lead_messages, response.deduction_messages);
      await refreshCaseState();
      if (response.unlocked_suspects[0]) dispatch({ type: 'SET_SELECTED_SUSPECT', payload: response.unlocked_suspects[0] });
      if (response.unlocked_documents[0]) dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: response.unlocked_documents[0] });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleSubmitTheory(culpritId: string, motive: string, timeline: string): Promise<SubmitTheoryResponse> {
    if (!state.isAuthenticated || !state.selectedCaseId || !state.saveState) throw new Error('No case loaded');
    const response = await api.submitTheory(
      state.selectedCaseId,
      state.alias,
      culpritId,
      motive,
      timeline,
      state.saveState.pinned_evidence_ids,
    );
    dispatch({ type: 'SET_COMMUNITY_STATS', payload: response.stats });
    dispatch({ type: 'SET_THEORY_SCORE', payload: response.score });
    await refreshCaseState();
    return response;
  }

  async function restartCase(): Promise<void> {
    if (!state.isAuthenticated || !state.selectedCaseId) return;
    const restarted = await api.restartCase(state.selectedCaseId, state.alias);
    dispatch({ type: 'SET_SAVE_STATE', payload: restarted.state });
    dispatch({ type: 'SET_SELECTED_SUSPECT', payload: restarted.state.unlocked_suspect_ids[0] ?? '' });
    dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: restarted.state.unlocked_document_ids[0] ?? '' });
    dispatch({ type: 'SET_SELECTED_LOCATION', payload: state.caseDetail?.location_dossiers[0]?.id ?? '' });
    dispatch({ type: 'SET_SEARCH_QUERY', payload: '' });
    dispatch({ type: 'SET_RESCAN_FOCUS', payload: '' });
    dispatch({ type: 'SET_SEARCH_RESULTS', payload: [] });
    dispatch({ type: 'SET_CONVERSATIONS', payload: {} });
    dispatch({ type: 'CLEAR_RESCAN_RESULTS' });
    dispatch({ type: 'SET_THEORY_SCORE', payload: null });
    dispatch({ type: 'CLEAR_ACTIVITY_MESSAGES' });
    await refreshCaseState();
  }

  async function deleteCase(caseId: string): Promise<void> {
    if (!state.isAuthenticated) return;
    try {
      await api.deleteAuthoringCase(caseId, state.alias);
      const session = await api.getSession(state.alias);
      const [cases, authoringCases, pendingCases] = await Promise.all([
        api.listCases(state.alias),
        api.listAuthoringCases(state.alias),
        session.role === 'admin' ? api.listPendingCases(state.alias) : Promise.resolve([]),
      ]);
      dispatch({ type: 'SET_SESSION_ROLE', payload: session.role });
      dispatch({ type: 'SET_CASES', payload: cases });
      dispatch({
        type: 'SET_DRAFT_CASES',
        payload: authoringCases
          .map((bundle) => bundle.case)
          .filter((caseSummary) => caseSummary.status === 'draft' && caseSummary.owner_alias === state.alias),
      });
      dispatch({ type: 'SET_PENDING_CASES', payload: pendingCases });
      dispatch({ type: 'CLEAR_ERROR' });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
      throw e;
    }
  }

  async function handleTogglePin(documentId: string): Promise<void> {
    if (!state.isAuthenticated || !state.selectedCaseId) return;
    try {
      const nextState = await api.togglePin(state.selectedCaseId, state.alias, documentId);
      dispatch({ type: 'SET_SAVE_STATE', payload: nextState });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  return {
    restoreSession,
    register,
    login,
    logout,
    loadCases,
    loadCase,
    refreshCaseState,
    reloadPlayableCases,
    handleSearch,
    handleRescan,
    beginInterrogationSession,
    handleTalk,
    handleTalkStreaming,
    handleConfront,
    handleSubmitTheory,
    restartCase,
    deleteCase,
    handleTogglePin,
  };
}
