import { useEffect, useRef } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import AuthoringStudio from './AuthoringStudio';
import { SESSION_EXPIRED_EVENT } from './api';
import { useGame } from './context/GameContext';
import { useGameActions } from './context/useGameActions';
import type { CaseDocument } from './types';
import { CrestMark, MediaPlate, SuspicionMeter } from './ui';
import ArchiveView from './views/ArchiveView';
import AuthView from './views/AuthView';
import CommunityView from './views/CommunityView';
import HomeView from './views/HomeView';
import IntakeView from './views/IntakeView';
import InterrogationView from './views/InterrogationView';
import SubmissionView from './views/SubmissionView';

type ViewId = 'intake' | 'archive' | 'interrogation' | 'submission' | 'community' | 'authoring';
type TabId = 'home' | ViewId;

const caseTabs: Array<{ id: ViewId; label: string; glyph: string }> = [
  { id: 'intake', label: 'Intake', glyph: 'IN' },
  { id: 'archive', label: 'Archive', glyph: 'AR' },
  { id: 'interrogation', label: 'Interrogation', glyph: 'IQ' },
  { id: 'submission', label: 'Accuse', glyph: 'AC' },
  { id: 'community', label: 'Community', glyph: 'CM' },
];

const overviewLinks: Array<{ label: string; view: Exclude<ViewId, 'authoring'> }> = [
  { label: 'Case Brief', view: 'intake' },
  { label: 'Archive', view: 'archive' },
  { label: 'Interrogation', view: 'interrogation' },
  { label: 'Accuse', view: 'submission' },
  { label: 'Community', view: 'community' },
];

function CaseShell() {
  const { caseId = '' } = useParams<{ caseId: string }>();
  const { state, dispatch } = useGame();
  const actions = useGameActions();
  const navigate = useNavigate();

  async function handleDeleteCase(caseIdToDelete: string) {
    const summary = [...state.cases, ...state.draftCases, ...state.pendingCases].find(
      (caseSummary) => caseSummary.id === caseIdToDelete,
    );
    const label = summary?.status === 'approved' ? 'case' : 'draft';
    if (!window.confirm(`Delete ${label} "${summary?.title ?? caseIdToDelete}"? This cannot be undone.`)) return;
    await actions.deleteCase(caseIdToDelete);
    dispatch({ type: 'CLEAR_CASE_CONTEXT' });
    navigate('/');
  }

  useEffect(() => {
    if (caseId && (caseId !== state.selectedCaseId || state.caseDetail?.case.id !== caseId)) {
      dispatch({ type: 'SET_SELECTED_CASE', payload: caseId });
      void actions.loadCase(caseId);
    }
  }, [caseId]);

  const { caseDetail, saveState, conversations, communityStats, unlockedSuspects } = state;
  const currentState = saveState ?? caseDetail?.state ?? null;
  const selectedSuspect =
    caseDetail?.suspects.find((suspect) => suspect.id === state.selectedSuspectId) ?? caseDetail?.suspects[0];
  const selectedDocument =
    caseDetail?.documents.find((document) => document.id === state.selectedDocumentId) ?? caseDetail?.documents[0];

  function openDocumentAttachment(doc: CaseDocument | null) {
    if (!doc?.image_url) return;
    dispatch({
      type: 'SET_MEDIA_PREVIEW',
      payload: {
        src: doc.image_url,
        title: doc.id === 'doc_incident' ? 'Incident Board' : `${doc.title} Plate`,
        eyebrow: 'Visual Attachment',
        summary:
          doc.id === 'doc_incident'
            ? 'A stylized reference board attached to the police first-pass summary.'
            : `A reference image attached to this ${doc.doc_type.replace(/_/g, ' ')} record.`,
      },
    });
  }

  return (
    <main className="center-stage">
      {state.error ? <div className="error-banner">{state.error}</div> : null}
      {state.loading ? <div className="rail-panel loading-panel">Loading dossier...</div> : null}
      {state.activityMessages.length ? (
        <aside className="activity-toast-stack" aria-live="polite">
          {state.activityMessages.map((message) => (
            <div className="activity-toast" key={message}>
              <span>{message}</span>
              <button type="button" onClick={() => dispatch({ type: 'CLEAR_ACTIVITY_MESSAGES' })}>
                Dismiss
              </button>
            </div>
          ))}
        </aside>
      ) : null}

      <Routes>
        <Route path="intake" element={caseDetail ? <IntakeView caseDetail={caseDetail} /> : null} />
        <Route
          path="archive"
          element={
            caseDetail && currentState ? (
              <ArchiveView
                caseDetail={caseDetail}
                saveState={currentState}
                selectedDocumentId={state.selectedDocumentId}
                selectedLocationId={state.selectedLocationId}
                onSelectDocument={(id) => dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: id })}
                onSelectLocation={(id) => dispatch({ type: 'SET_SELECTED_LOCATION', payload: id })}
                onTogglePin={actions.handleTogglePin}
                onOpenAttachment={openDocumentAttachment}
                searchQuery={state.searchQuery}
                onSearchQueryChange={(query) => dispatch({ type: 'SET_SEARCH_QUERY', payload: query })}
                searchResults={state.searchResults}
                rescanFocus={state.rescanFocus}
                onRescanFocusChange={(focus) => dispatch({ type: 'SET_RESCAN_FOCUS', payload: focus })}
                rescanResults={state.rescanResults}
                onSearch={async (event) => {
                  event.preventDefault();
                  await actions.handleSearch();
                }}
                onRescan={actions.handleRescan}
              />
            ) : null
          }
        />
        <Route
          path="interrogation"
          element={
            caseDetail && currentState ? (
              <InterrogationView
                caseDetail={caseDetail}
                saveState={currentState}
                selectedSuspect={selectedSuspect}
                selectedDocument={selectedDocument}
                conversations={conversations}
                onTalk={actions.handleTalkStreaming}
                onConfront={actions.handleConfront}
                onBeginNewSession={() => selectedSuspect ? actions.beginInterrogationSession(selectedSuspect.id) : Promise.resolve()}
                onOpenAttachment={openDocumentAttachment}
              />
            ) : null
          }
        />
        <Route
          path="submission"
          element={
            caseDetail && currentState ? (
              <SubmissionView
                caseDetail={caseDetail}
                saveState={currentState}
                pinnedDocuments={state.pinnedDocuments}
                onSubmitTheory={actions.handleSubmitTheory}
                onNavigateToCommunity={() => navigate(`/${caseId}/community`)}
                onRestartCase={async () => {
                  await actions.restartCase();
                  navigate(`/${caseId}/interrogation`);
                }}
              />
            ) : null
          }
        />
        <Route
          path="community"
          element={
            communityStats ? (
              <CommunityView
                suspects={unlockedSuspects}
                communityStats={communityStats}
                theoryScore={state.theoryScore}
                onRestartCase={async () => {
                  await actions.restartCase();
                  navigate(`/${caseId}/interrogation`);
                }}
              />
            ) : null
          }
        />
        <Route
          path="authoring"
          element={
            <AuthoringStudio
              alias={state.alias}
              currentCaseId={state.selectedCaseId}
              role={state.sessionRole}
              onSelectCase={(id) => {
                dispatch({ type: 'SET_SELECTED_CASE', payload: id });
                navigate(`/${id}/interrogation`);
              }}
              onDeleteCase={handleDeleteCase}
              onPlayableCasesChanged={actions.reloadPlayableCases}
            />
          }
        />
        <Route path="*" element={<Navigate to="interrogation" replace />} />
      </Routes>
    </main>
  );
}

function AppShell() {
  const { state, dispatch } = useGame();
  const actions = useGameActions();
  const location = useLocation();
  const navigate = useNavigate();

  async function handleDeleteCase(caseId: string) {
    const caseSummary = [...state.cases, ...state.draftCases, ...state.pendingCases].find((item) => item.id === caseId);
    if (!caseSummary) return;
    const label = caseSummary.status === 'approved' ? 'case' : 'draft';
    if (!window.confirm(`Delete ${label} "${caseSummary.title}"? This cannot be undone.`)) {
      return;
    }
    try {
      await actions.deleteCase(caseId);
      if (state.selectedCaseId === caseId) {
        dispatch({ type: 'CLEAR_CASE_CONTEXT' });
      }
      if (location.pathname !== '/') {
        navigate('/');
      }
    } catch {
      // useGameActions already surfaces the error banner
    }
  }

  useEffect(() => {
    if (!state.isAuthenticated && state.aliasDraft) {
      void actions.restoreSession();
    }
  }, []);

  useEffect(() => {
    function handleSessionExpired() {
      dispatch({ type: 'LOG_OUT' });
      dispatch({ type: 'SET_ERROR', payload: 'Your session expired or the local database was reset. Please register or sign in again.' });
      navigate('/');
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
  }, [dispatch, navigate]);

  useEffect(() => {
    if (state.isAuthenticated) {
      void actions.loadCases();
    }
  }, [state.isAuthenticated, state.alias]);

  if (!state.isAuthenticated) {
    return (
      <AuthView
        alias={state.aliasDraft}
        onAliasChange={(value) => dispatch({ type: 'SET_ALIAS_DRAFT', payload: value })}
        onRegister={actions.register}
        onLogin={actions.login}
        loading={state.loading}
        error={state.error}
      />
    );
  }

  const caseId = state.selectedCaseId;
  const isLibraryRoute = location.pathname === '/' || location.pathname === '/authoring';
  const tabs: Array<{ id: TabId; label: string; glyph: string }> = [
    { id: 'home', label: 'Home', glyph: 'HM' },
    ...caseTabs,
    { id: 'authoring', label: 'Authoring', glyph: 'AU' },
  ];

  function navTo(view: TabId) {
    if (view === 'home') {
      navigate('/');
      return;
    }
    if (view === 'authoring') {
      navigate(caseId ? `/${caseId}/authoring` : '/authoring');
      return;
    }
    if (caseId) {
      navigate(`/${caseId}/${view}`);
    }
  }

  const { caseDetail, conversations, unlockedSuspects } = state;

  return (
    <div className="app-shell">
      <header className="command-bar">
        <div className="brand-block">
          <CrestMark />
          <div>
            <p className="brand-title">Investigation Room</p>
            <p className="brand-subtitle">RAG Mystery Engine</p>
          </div>
        </div>
        <div className="command-stat">
          <span className="command-label">Case</span>
          <strong>{caseDetail?.case.title ?? 'Case Library'}</strong>
          <span className="command-meta">{caseId || 'Browse all cases'}</span>
        </div>
        <div className="command-stat">
          <span className="command-label">Detective</span>
          <strong>{state.alias}</strong>
          <span className="command-meta">{state.sessionRole === 'admin' ? 'Admin Review Access' : 'Player Access'}</span>
        </div>
        <div className="command-stat command-stat-wide">
          <span className="command-label">Suspicion Level</span>
          <div className="command-meter-row">
            <strong
              className={
                state.suspicionValue > 66 ? 'alert-high' : state.suspicionValue > 33 ? 'alert-medium' : 'alert-low'
              }
            >
              {state.suspicionValue > 66 ? 'High' : state.suspicionValue > 33 ? 'Guarded' : 'Low'}
            </strong>
            <SuspicionMeter value={state.suspicionValue} />
          </div>
        </div>
        <div className="command-icons">
          <div className="detective-badge">{state.alias.slice(0, 2).toUpperCase()}</div>
        </div>
      </header>

      <div className="tab-row">
        {tabs.map((tab) => (
          <button key={tab.id} className="dossier-tab" onClick={() => navTo(tab.id)}>
            <span>{tab.glyph}</span>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="workspace">
        <aside className="left-rail">
          {isLibraryRoute ? (
            <>
              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Library Status</span>
                  <strong>{state.cases.length.toString().padStart(2, '0')}</strong>
                </div>
                <div className="folder-list">
                  <div className="folder-row static-row">
                    <span>Approved Cases</span>
                    <strong>{state.cases.length}</strong>
                  </div>
                  <div className="folder-row static-row">
                    <span>Pending Review</span>
                    <strong>{state.pendingCases.length}</strong>
                  </div>
                </div>
              </section>

              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Quick Actions</span>
                  <strong>Launch</strong>
                </div>
                <div className="nav-list">
                  <button className="nav-link" onClick={() => navigate('/')}>
                    <span className="nav-bullet">•</span>
                    Case Library
                  </button>
                  <button className="nav-link" onClick={() => navigate('/authoring')}>
                    <span className="nav-bullet">•</span>
                    Authoring Studio
                  </button>
                </div>
              </section>
            </>
          ) : (
            <>
              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Case Navigation</span>
                  <strong>{caseDetail?.case.title ?? 'Case Overview'}</strong>
                </div>
                <div className="nav-list">
                  {overviewLinks.map((link) => (
                    <button key={link.label} className="nav-link" onClick={() => navTo(link.view)}>
                      <span className="nav-bullet">•</span>
                      {link.label}
                    </button>
                  ))}
                </div>
              </section>

              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Suspects</span>
                  <strong>{unlockedSuspects.length.toString().padStart(2, '0')}</strong>
                </div>
                <div className="suspect-stack">
                  {unlockedSuspects.map((suspect) => {
                    const suspectConvo = conversations[suspect.id];
                    const derivedHeat = suspectConvo
                      ? Math.min(100, suspectConvo.guardedness + (suspectConvo.trust < 40 ? 20 : 0))
                      : 0;
                    const suspicionLabel = derivedHeat >= 75 ? 'High' : derivedHeat >= 50 ? 'Medium' : 'Low';
                    return (
                      <button
                        key={suspect.id}
                        className={state.selectedSuspectId === suspect.id ? 'suspect-list-card active' : 'suspect-list-card'}
                        onClick={() => {
                          dispatch({ type: 'SET_SELECTED_SUSPECT', payload: suspect.id });
                          navTo('interrogation');
                        }}
                      >
                        <MediaPlate
                          src={suspect.image_url}
                          alt={suspect.display_name}
                          kind="suspect"
                          label={suspect.portrait_key ?? suspect.display_name.slice(0, 2)}
                          className="suspect-list-photo"
                        />
                        <div className="suspect-list-copy">
                          <strong>{suspect.display_name}</strong>
                          <span>{suspect.public_profile.role}</span>
                          <div className="mini-suspicion-row">
                            <span>Suspicion</span>
                            <strong className={`severity-pill severity-${suspicionLabel.toLowerCase()}`}>
                              {suspicionLabel}
                            </strong>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>

              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Archive Folders</span>
                  <strong>{state.folderCounts.length.toString().padStart(2, '0')}</strong>
                </div>
                <div className="folder-list">
                  {state.folderCounts.map(([folder, count]) => (
                    <button key={folder} className="folder-row" onClick={() => navTo('archive')}>
                      <span>{folder.replace(/_/g, ' ')}</span>
                      <strong>{count}</strong>
                    </button>
                  ))}
                </div>
              </section>
            </>
          )}

          <section className="rail-panel rail-identity">
            <div className="rail-heading">
              <span>Session</span>
              <strong>{state.sessionRole.toUpperCase()}</strong>
            </div>
            <p className="objective-copy">Signed in as {state.alias}.</p>
            <button className="dossier-button dossier-button-ghost" onClick={actions.logout}>
              Logout
            </button>
          </section>
        </aside>

        <Routes>
          <Route
            path="/"
            element={
              <HomeView
                cases={state.cases}
                draftCases={state.draftCases}
                pendingCases={state.pendingCases}
                role={state.sessionRole}
                searchQuery={state.caseSearchQuery}
                onSearchQueryChange={(value) => dispatch({ type: 'SET_CASE_SEARCH_QUERY', payload: value })}
                onSelectCase={(id) => {
                  dispatch({ type: 'SET_SELECTED_CASE', payload: id });
                  navigate(`/${id}/interrogation`);
                }}
                onReviewCase={(id) => {
                  dispatch({ type: 'SET_SELECTED_CASE', payload: id });
                  navigate(`/${id}/authoring`);
                }}
                onDeleteCase={handleDeleteCase}
                onOpenAuthoring={() => navigate('/authoring')}
              />
            }
          />
          <Route
            path="/authoring"
            element={
              <AuthoringStudio
                alias={state.alias}
                currentCaseId={state.selectedCaseId}
                role={state.sessionRole}
                onSelectCase={(id) => {
                  dispatch({ type: 'SET_SELECTED_CASE', payload: id });
                  navigate(`/${id}/interrogation`);
                }}
                onDeleteCase={handleDeleteCase}
                onPlayableCasesChanged={actions.reloadPlayableCases}
              />
            }
          />
          <Route path="/:caseId/*" element={<CaseShell />} />
        </Routes>

      </div>

      {state.mediaPreview ? (
        <div
          className="modal-backdrop"
          onClick={() => dispatch({ type: 'SET_MEDIA_PREVIEW', payload: null })}
          role="presentation"
        >
          <div
            className="media-modal"
            role="dialog"
            aria-modal="true"
            aria-label={state.mediaPreview.title}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="document-toolbar">
              <span>{state.mediaPreview.eyebrow}</span>
              <button
                className="icon-button modal-close"
                type="button"
                onClick={() => dispatch({ type: 'SET_MEDIA_PREVIEW', payload: null })}
                aria-label="Close visual attachment"
              >
                x
              </button>
            </div>
            <div className="media-modal-body">
              <div className="media-modal-figure">
                <MediaPlate
                  src={state.mediaPreview.src}
                  alt={state.mediaPreview.title}
                  kind="evidence"
                  label={state.mediaPreview.title}
                  className="media-modal-plate"
                />
              </div>
              <div className="media-modal-copy">
                <p className="eyebrow">{state.mediaPreview.eyebrow}</p>
                <h3>{state.mediaPreview.title}</h3>
                <p>{state.mediaPreview.summary}</p>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function App() {
  return <AppShell />;
}

