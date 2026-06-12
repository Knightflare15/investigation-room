import type {
  AuthLoginRequest,
  AuthRegisterRequest,
  AssetEntry,
  AuthoringBundle,
  CaseBriefInput,
  CaseDetailResponse,
  CaseIngestionInput,
  CaseIngestionResponse,
  CaseSummary,
  CommunityStatsResponse,
  ConversationState,
  CreateCaseRequest,
  DialogueResponse,
  GenerateCaseDraftResponse,
  PlayerCaseState,
  RescanResponse,
  SaveStateResponse,
  SearchResponse,
  SessionInfo,
  SessionStatus,
  SubmitTheoryResponse,
} from './types';

const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');

// Keep local API calls on the same site as the page so SameSite session cookies
// work whether Vite was opened through localhost or 127.0.0.1. Production serves
// the built frontend from FastAPI, so relative URLs are the correct default.
export const API_BASE = configuredApiBase
  ?? (import.meta.env.DEV ? `${window.location.protocol}//${window.location.hostname}:8000` : '');

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

const sessionCache = new Map<string, SessionInfo>();
export const SESSION_EXPIRED_EVENT = 'investigation-room-session-expired';

function sessionStorageKey(alias: string) {
  return `investigation-room-session::${alias}`;
}

function cacheSession(session: SessionInfo): SessionInfo {
  sessionCache.set(session.alias, session);
  localStorage.setItem(sessionStorageKey(session.alias), JSON.stringify(session));
  return session;
}

function clearStoredSession(alias?: string) {
  if (alias) {
    sessionCache.delete(alias);
    localStorage.removeItem(sessionStorageKey(alias));
  } else {
    sessionCache.clear();
    for (let index = localStorage.length - 1; index >= 0; index -= 1) {
      const key = localStorage.key(index);
      if (key?.startsWith('investigation-room-session::')) {
        localStorage.removeItem(key);
      }
    }
  }
}

function expireSession(alias?: string) {
  clearStoredSession(alias);
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
}

async function fetchSessionStatus(): Promise<SessionStatus> {
  const response = await fetch(`${API_BASE}/session`, {
    credentials: 'include',
  });
  if (!response.ok) {
    if (response.status === 401) expireSession();
    throw new Error(`Session lookup failed: ${response.status}`);
  }
  return response.json() as Promise<SessionStatus>;
}

export async function restoreSession(alias: string): Promise<SessionInfo> {
  const storedSession = localStorage.getItem(sessionStorageKey(alias));
  if (storedSession) {
    try {
      const parsed = JSON.parse(storedSession) as SessionInfo;
      if (parsed.alias === alias && parsed.role) {
        const current = await fetchSessionStatus();
        return cacheSession({ alias: current.alias, role: current.role });
      }
    } catch {
      localStorage.removeItem(sessionStorageKey(alias));
    }
  }

  const current = await fetchSessionStatus();
  return cacheSession({ alias: current.alias, role: current.role });
}

async function submitAuth(path: '/auth/register' | '/auth/login', payload: AuthRegisterRequest | AuthLoginRequest) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    credentials: 'include',
  });
  if (!response.ok) {
    if (response.status === 401) expireSession(payload.alias);
    let detail = `Authentication failed: ${response.status}`;
    const fallbackText = await response.clone().text();
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
      detail = typeof body.detail === 'string'
        ? body.detail
        : body.detail?.[0]?.msg ?? detail;
    } catch {
      detail = fallbackText || detail;
    }
    throw new Error(detail);
  }
  const session = (await response.json()) as SessionStatus;
  return cacheSession({ alias: session.alias, role: session.role });
}

/** Confirm that the HttpOnly-cookie session is still valid. */
export async function ensureToken(alias: string): Promise<void> {
  await restoreSession(alias);
}

export async function authHeaders(alias: string): Promise<Record<string, string>> {
  await ensureToken(alias);
  return {};
}

async function request<T>(path: string, alias: string, init?: RequestInit): Promise<T> {
  await ensureToken(alias);
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    if (response.status === 401) expireSession(alias);
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getSession(alias: string) {
    return restoreSession(alias);
  },
  register(payload: AuthRegisterRequest) {
    return submitAuth('/auth/register', payload);
  },
  login(payload: AuthLoginRequest) {
    return submitAuth('/auth/login', payload);
  },
  logout(alias: string) {
    clearStoredSession(alias);
    void fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
  },
  async listCases(alias: string) {
    const cases = await request<CaseSummary[]>('/cases', alias);
    return cases.map(normalizeCaseSummary);
  },
  async listPendingCases(alias: string) {
    const cases = await request<CaseSummary[]>('/cases/pending', alias);
    return cases.map(normalizeCaseSummary);
  },
  async getCase(caseId: string, alias: string) {
    const detail = await request<CaseDetailResponse>(`/cases/${caseId}`, alias);
    return normalizeCaseDetail(detail);
  },
  getSaveState(caseId: string, alias: string) {
    return request<SaveStateResponse>(`/cases/${caseId}/save-state`, alias);
  },
  restartCase(caseId: string, alias: string) {
    return request<SaveStateResponse>(`/cases/${caseId}/restart`, alias, {
      method: 'POST',
    });
  },
  search(caseId: string, alias: string, query: string) {
    return request<SearchResponse>(`/cases/${caseId}/search`, alias, {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  },
  rescan(caseId: string, alias: string, focus: string, locationId?: string) {
    return request<RescanResponse>(`/cases/${caseId}/rescan`, alias, {
      method: 'POST',
      body: JSON.stringify({ focus, location_id: locationId ?? null }),
    });
  },
  talk(caseId: string, suspectId: string, alias: string, message: string) {
    return request<DialogueResponse>(`/cases/${caseId}/suspects/${suspectId}/talk`, alias, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },
  beginInterrogationSession(caseId: string, suspectId: string, alias: string) {
    return request<ConversationState>(`/cases/${caseId}/suspects/${suspectId}/begin-session`, alias, {
      method: 'POST',
    });
  },
  confront(caseId: string, suspectId: string, alias: string, evidenceId: string, message: string) {
    return request<DialogueResponse>(`/cases/${caseId}/suspects/${suspectId}/confront`, alias, {
      method: 'POST',
      body: JSON.stringify({ evidence_id: evidenceId, message }),
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
  async generateAuthoringCase(alias: string, payload: CaseBriefInput) {
    const response = await request<GenerateCaseDraftResponse>('/authoring/cases/generate', alias, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return {
      warnings: response.warnings,
      bundle: normalizeAuthoringBundle(response.bundle),
    };
  },
  async ingestAuthoringCase(alias: string, payload: CaseIngestionInput) {
    const response = await request<CaseIngestionResponse>('/authoring/cases/ingest', alias, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return {
      warnings: response.warnings,
      groundings: response.groundings,
      bundle: normalizeAuthoringBundle(response.bundle),
    };
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
  async approveAuthoringCase(caseId: string, alias: string) {
    const bundle = await request<AuthoringBundle>(`/authoring/cases/${caseId}/approve`, alias, {
      method: 'POST',
    });
    return normalizeAuthoringBundle(bundle);
  },
  deleteAuthoringCase(caseId: string, alias: string) {
    return request<{ deleted: boolean; case_id: string }>(`/authoring/cases/${caseId}`, alias, {
      method: 'DELETE',
    });
  },
  async uploadAuthoringAsset(caseId: string, alias: string, folder: string, file: File) {
    const formData = new FormData();
    formData.append('folder', folder);
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/authoring/cases/${caseId}/assets`, {
      method: 'POST',
      credentials: 'include',
      headers: await authHeaders(alias),
      body: formData,
    });
    if (!response.ok) {
      if (response.status === 401) expireSession(alias);
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
