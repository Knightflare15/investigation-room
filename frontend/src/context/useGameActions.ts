import { API_BASE, api, authHeaders } from '../api';
import type { BoardLinkResponse, SubmitTheoryResponse } from '../types';
import { useGame } from './GameContext';

export function useGameActions() {
  const { state, dispatch } = useGame();

  async function loadCases() {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const cases = await api.listCases(state.alias);
      dispatch({ type: 'SET_CASES', payload: cases });
      if (!state.selectedCaseId && cases[0]) {
        dispatch({ type: 'SET_SELECTED_CASE', payload: cases[0].id });
      }
      dispatch({ type: 'CLEAR_ERROR' });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }

  async function loadCase(caseId: string) {
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
    if (!state.selectedCaseId) return;
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
    const nextCases = await api.listCases(state.alias);
    dispatch({ type: 'SET_CASES', payload: nextCases });
    const nextId = preferredCaseId || state.selectedCaseId || nextCases[0]?.id || '';
    if (nextId) {
      dispatch({ type: 'SET_SELECTED_CASE', payload: nextId });
      await loadCase(nextId);
    }
  }

  async function handleSearch() {
    if (!state.selectedCaseId || !state.searchQuery.trim()) return;
    try {
      const response = await api.search(state.selectedCaseId, state.alias, state.searchQuery);
      dispatch({ type: 'SET_SEARCH_RESULTS', payload: response.results });
      if (response.results[0]) dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: response.results[0].document_id });
      await refreshCaseState();
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleRescan() {
    if (!state.selectedCaseId) return;
    try {
      const response = await api.rescan(
        state.selectedCaseId,
        state.alias,
        state.searchQuery || 'Cross-check known contradictions',
      );
      dispatch({ type: 'SET_RESCAN_RESULTS', payload: response });
      await refreshCaseState();
      if (response.unlocked_suspects[0]) dispatch({ type: 'SET_SELECTED_SUSPECT', payload: response.unlocked_suspects[0] });
      if (response.unlocked_documents[0]) dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: response.unlocked_documents[0] });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleTalk(message: string): Promise<void> {
    const suspectId = state.selectedSuspectId;
    if (!state.selectedCaseId || !suspectId || !message.trim()) return;
    try {
      const response = await api.talk(state.selectedCaseId, suspectId, state.alias, message);
      dispatch({ type: 'UPDATE_CONVERSATION', payload: response.conversation });
      dispatch({
        type: 'SET_SAVE_STATE',
        payload: { ...(state.saveState ?? response.conversation), suspicion_level: response.suspicion_level } as never,
      });
      await refreshCaseState();
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleTalkStreaming(message: string): Promise<void> {
    const { selectedCaseId, selectedSuspectId, alias } = state;
    if (!selectedCaseId || !selectedSuspectId || !message.trim()) return;
    // Optimistically show the detective's turn plus an empty suspect bubble to fill in.
    dispatch({ type: 'APPEND_TRANSCRIPT_TURN', payload: { suspectId: selectedSuspectId, turn: { speaker: 'detective', text: message } } });
    const suspectName = state.caseDetail?.suspects.find((s) => s.id === selectedSuspectId)?.display_name ?? 'Suspect';
    dispatch({ type: 'APPEND_TRANSCRIPT_TURN', payload: { suspectId: selectedSuspectId, turn: { speaker: suspectName, text: '' } } });

    let accumulated = '';
    try {
      const response = await fetch(`${API_BASE}/cases/${selectedCaseId}/suspects/${selectedSuspectId}/talk/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(await authHeaders(alias)) },
        body: JSON.stringify({ message }),
      });
      if (!response.ok || !response.body) throw new Error('stream unavailable');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const line of decoder.decode(value, { stream: true }).split('\n')) {
          if (line.startsWith('data: ') && !line.includes('[DONE]') && !line.includes('[ERROR]')) {
            accumulated += line.slice(6);
            dispatch({ type: 'UPDATE_STREAMING_REPLY', payload: { suspectId: selectedSuspectId, text: accumulated } });
          }
        }
      }
      await refreshCaseState();
    } catch {
      // Streaming unavailable — fall back to the standard non-streaming talk flow.
      await handleTalk(message);
    }
  }

  async function handleConfront(evidenceId: string, message: string): Promise<void> {
    const suspectId = state.selectedSuspectId;
    if (!state.selectedCaseId || !suspectId || !evidenceId) return;
    try {
      const response = await api.confront(state.selectedCaseId, suspectId, state.alias, evidenceId, message);
      dispatch({ type: 'UPDATE_CONVERSATION', payload: response.conversation });
      await refreshCaseState();
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  async function handleBoardLink(source: string, target: string, linkType: string, notes: string): Promise<BoardLinkResponse> {
    if (!state.selectedCaseId) throw new Error('No case selected');
    const response = await api.addBoardLink(state.selectedCaseId, state.alias, source, target, linkType, notes);
    await refreshCaseState();
    return response;
  }

  async function handleSubmitTheory(culpritId: string, motive: string, timeline: string): Promise<SubmitTheoryResponse> {
    if (!state.selectedCaseId || !state.saveState) throw new Error('No case loaded');
    const response = await api.submitTheory(
      state.selectedCaseId,
      state.alias,
      culpritId,
      motive,
      timeline,
      state.saveState.pinned_evidence_ids,
    );
    dispatch({ type: 'SET_COMMUNITY_STATS', payload: response.stats });
    await refreshCaseState();
    return response;
  }

  async function handleTogglePin(documentId: string): Promise<void> {
    if (!state.selectedCaseId) return;
    try {
      const nextState = await api.togglePin(state.selectedCaseId, state.alias, documentId);
      dispatch({ type: 'SET_SAVE_STATE', payload: nextState });
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  }

  return {
    loadCases,
    loadCase,
    refreshCaseState,
    reloadPlayableCases,
    handleSearch,
    handleRescan,
    handleTalk,
    handleTalkStreaming,
    handleConfront,
    handleBoardLink,
    handleSubmitTheory,
    handleTogglePin,
  };
}
