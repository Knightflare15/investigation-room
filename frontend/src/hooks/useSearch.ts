import { type FormEvent, useState } from 'react';
import { api } from '../api';
import type { RescanResponse, SearchResult } from '../types';

export type SearchHook = {
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  searchResults: SearchResult[];
  rescanResults: RescanResponse | null;
  handleSearch: (event: FormEvent) => Promise<void>;
  handleRescan: () => Promise<void>;
};

export function useSearch(
  selectedCaseId: string,
  alias: string,
  onDocumentUnlocked: (id: string) => void,
  onSuspectUnlocked: (id: string) => void,
  onStateRefresh: () => Promise<void>,
  onError: (message: string) => void,
): SearchHook {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [rescanResults, setRescanResults] = useState<RescanResponse | null>(null);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!selectedCaseId || !searchQuery.trim()) return;
    try {
      const response = await api.search(selectedCaseId, alias, searchQuery);
      setSearchResults(response.results);
      if (response.results[0]) onDocumentUnlocked(response.results[0].document_id);
      await onStateRefresh();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function handleRescan() {
    if (!selectedCaseId) return;
    try {
      const response = await api.rescan(selectedCaseId, alias, searchQuery || 'Cross-check known contradictions');
      setRescanResults(response);
      await onStateRefresh();
      if (response.unlocked_suspects[0]) onSuspectUnlocked(response.unlocked_suspects[0]);
      if (response.unlocked_documents[0]) onDocumentUnlocked(response.unlocked_documents[0]);
    } catch (e) {
      onError((e as Error).message);
    }
  }

  return { searchQuery, setSearchQuery, searchResults, rescanResults, handleSearch, handleRescan };
}
