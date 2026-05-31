import type {
  AssetEntry,
  AuthoringBundle,
  BoardLinkResponse,
  CaseDetailResponse,
  CaseSummary,
  CommunityStatsResponse,
  CreateCaseRequest,
  DialogueResponse,
  PlayerCaseState,
  RescanResponse,
  SaveStateResponse,
  SearchResponse,
  SubmitTheoryResponse,
} from './types';

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

function resolveApiUrl(path?: string | null) {
  if (!path) return path ?? null;
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

function normalizeCaseSummary(caseSummary: CaseSummary): CaseSummary {
  return {
    ...caseSummary,
    cover_image_url: resolveApiUrl(caseSummary.cover_image_url),
  };
}

function normalizeCaseDetail(detail: CaseDetailResponse): CaseDetailResponse {
  return {
    ...detail,
    case: normalizeCaseSummary(detail.case),
    archive_domains: detail.archive_domains.map((domain) => ({
      ...domain,
      image_url: resolveApiUrl(domain.image_url),
    })),
    location_dossiers: detail.location_dossiers.map((dossier) => ({
      ...dossier,
      image_url: resolveApiUrl(dossier.image_url),
    })),
    suspects: detail.suspects.map((suspect) => ({
      ...suspect,
      image_url: resolveApiUrl(suspect.image_url),
    })),
    documents: detail.documents.map((document) => ({
      ...document,
      image_url: resolveApiUrl(document.image_url),
    })),
  };
}

function normalizeAuthoringBundle(bundle: AuthoringBundle): AuthoringBundle {
  return {
    ...bundle,
    case: {
      ...bundle.case,
      cover_image_url: resolveApiUrl(bundle.case.cover_image_url),
      archive_domains: bundle.case.archive_domains.map((domain) => ({
        ...domain,
        image_url: resolveApiUrl(domain.image_url),
      })),
      location_dossiers: bundle.case.location_dossiers.map((dossier) => ({
        ...dossier,
        image_url: resolveApiUrl(dossier.image_url),
      })),
    },
    suspects: bundle.suspects.map((suspect) => ({
      ...suspect,
      image_url: resolveApiUrl(suspect.image_url),
    })),
    documents: bundle.documents.map((document) => ({
      ...document,
      image_url: resolveApiUrl(document.image_url),
    })),
    assets: bundle.assets.map((asset) => ({
      ...asset,
      url: resolveApiUrl(asset.url) ?? asset.url,
    })),
  };
}

// alias -> signed bearer token. Persisted to localStorage so a reload skips the handshake.
const tokenCache = new Map<string, string>();

function tokenStorageKey(alias: string) {
  return `investigation-room-token::${alias}`;
}

/** Return a signed session token for the alias, registering one via POST /session if needed. */
export async function ensureToken(alias: string): Promise<string> {
  const cached = tokenCache.get(alias) ?? localStorage.getItem(tokenStorageKey(alias)) ?? undefined;
  if (cached) {
    tokenCache.set(alias, cached);
    return cached;
  }
  const response = await fetch(`${API_BASE}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alias }),
  });
  if (!response.ok) {
    throw new Error(`Session registration failed: ${response.status}`);
  }
  const { token } = (await response.json()) as { token: string; alias: string };
  tokenCache.set(alias, token);
  localStorage.setItem(tokenStorageKey(alias), token);
  return token;
}

export async function authHeaders(alias: string): Promise<Record<string, string>> {
  return { Authorization: `Bearer ${await ensureToken(alias)}` };
}

async function request<T>(path: string, alias: string, init?: RequestInit): Promise<T> {
  const token = await ensureToken(alias);
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  async listCases(alias: string) {
    const cases = await request<CaseSummary[]>('/cases', alias);
    return cases.map(normalizeCaseSummary);
  },
  async getCase(caseId: string, alias: string) {
    const detail = await request<CaseDetailResponse>(`/cases/${caseId}`, alias);
    return normalizeCaseDetail(detail);
  },
  getSaveState(caseId: string, alias: string) {
    return request<SaveStateResponse>(`/cases/${caseId}/save-state`, alias);
  },
  search(caseId: string, alias: string, query: string) {
    return request<SearchResponse>(`/cases/${caseId}/search`, alias, {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  },
  rescan(caseId: string, alias: string, focus: string) {
    return request<RescanResponse>(`/cases/${caseId}/rescan`, alias, {
      method: 'POST',
      body: JSON.stringify({ focus }),
    });
  },
  talk(caseId: string, suspectId: string, alias: string, message: string) {
    return request<DialogueResponse>(`/cases/${caseId}/suspects/${suspectId}/talk`, alias, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },
  confront(caseId: string, suspectId: string, alias: string, evidenceId: string, message: string) {
    return request<DialogueResponse>(`/cases/${caseId}/suspects/${suspectId}/confront`, alias, {
      method: 'POST',
      body: JSON.stringify({ evidence_id: evidenceId, message }),
    });
  },
  addBoardLink(caseId: string, alias: string, sourceId: string, targetId: string, linkType: string, notes: string) {
    return request<BoardLinkResponse>(`/cases/${caseId}/board/link`, alias, {
      method: 'POST',
      body: JSON.stringify({
        source_id: sourceId,
        target_id: targetId,
        link_type: linkType,
        notes,
      }),
    });
  },
  togglePin(caseId: string, alias: string, documentId: string) {
    return request<PlayerCaseState>(`/cases/${caseId}/pin-evidence`, alias, {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId }),
    });
  },
  submitTheory(
    caseId: string,
    alias: string,
    culpritId: string,
    motiveText: string,
    timelineText: string,
    evidenceIds: string[],
  ) {
    return request<SubmitTheoryResponse>(`/cases/${caseId}/submit-theory`, alias, {
      method: 'POST',
      body: JSON.stringify({
        culprit_id: culpritId,
        motive_text: motiveText,
        timeline_text: timelineText,
        evidence_ids: evidenceIds,
      }),
    });
  },
  getCommunity(caseId: string, alias: string) {
    return request<CommunityStatsResponse>(`/cases/${caseId}/community-stats`, alias);
  },
  async listAuthoringCases(alias: string) {
    const bundles = await request<AuthoringBundle[]>('/authoring/cases', alias);
    return bundles.map(normalizeAuthoringBundle);
  },
  async createAuthoringCase(alias: string, payload: CreateCaseRequest) {
    const bundle = await request<AuthoringBundle>('/authoring/cases', alias, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return normalizeAuthoringBundle(bundle);
  },
  async getAuthoringCase(caseId: string, alias: string) {
    const bundle = await request<AuthoringBundle>(`/authoring/cases/${caseId}`, alias);
    return normalizeAuthoringBundle(bundle);
  },
  async saveAuthoringCase(caseId: string, alias: string, payload: AuthoringBundle) {
    const bundle = await request<AuthoringBundle>(`/authoring/cases/${caseId}`, alias, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return normalizeAuthoringBundle(bundle);
  },
  async uploadAuthoringAsset(caseId: string, alias: string, folder: string, file: File) {
    const formData = new FormData();
    formData.append('folder', folder);
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/authoring/cases/${caseId}/assets`, {
      method: 'POST',
      headers: await authHeaders(alias),
      body: formData,
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Request failed: ${response.status}`);
    }
    const asset = (await response.json()) as AssetEntry;
    return {
      ...asset,
      url: resolveApiUrl(asset.url) ?? asset.url,
    };
  },
};
