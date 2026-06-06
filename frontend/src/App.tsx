import { useEffect, useRef } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import AuthoringStudio from './AuthoringStudio';
import { useGame } from './context/GameContext';
import { useGameActions } from './context/useGameActions';
import type { CaseDocument } from './types';
import { CrestMark, MediaPlate, SuspicionMeter } from './ui';
import ArchiveView from './views/ArchiveView';
import AuthView from './views/AuthView';
import BoardView from './views/BoardView';
import CommunityView from './views/CommunityView';
import HomeView from './views/HomeView';
import IntakeView from './views/IntakeView';
import InterrogationView from './views/InterrogationView';
import SubmissionView from './views/SubmissionView';

type ViewId = 'intake' | 'archive' | 'interrogation' | 'board' | 'submission' | 'community' | 'authoring';
type TabId = 'home' | ViewId;

const caseTabs: Array<{ id: ViewId; label: string; glyph: string }> = [
  { id: 'intake', label: 'Intake', glyph: 'IN' },
  { id: 'archive', label: 'Archive', glyph: 'AR' },
  { id: 'interrogation', label: 'Interrogation', glyph: 'IQ' },
  { id: 'board', label: 'Evidence Board', glyph: 'BD' },
  { id: 'submission', label: 'Submission', glyph: 'SB' },
  { id: 'community', label: 'Community', glyph: 'CM' },
];

const overviewLinks: Array<{ label: string; view: Exclude<ViewId, 'authoring'> }> = [
  { label: 'Case Brief', view: 'intake' },
  { label: 'Archive', view: 'archive' },
  { label: 'Interrogation', view: 'interrogation' },
  { label: 'Theory Board', view: 'board' },
  { label: 'Community', view: 'community' },
];

function CaseShell() {
  const { caseId = '' } = useParams<{ caseId: string }>();
  const { state, dispatch } = useGame();
  const actions = useGameActions();
  const navigate = useNavigate();
  const location = useLocation();
  const lastSessionSuspectRef = useRef('');

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

  useEffect(() => {
    if (!location.pathname.endsWith('/interrogation')) {
      lastSessionSuspectRef.current = '';
      return;
    }
    if (!state.isAuthenticated || !selectedSuspect?.id) return;
    if (lastSessionSuspectRef.current === selectedSuspect.id) return;
    lastSessionSuspectRef.current = selectedSuspect.id;
    void actions.beginInterrogationSession(selectedSuspect.id);
  }, [location.pathname, selectedSuspect?.id, state.isAuthenticated]);

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
                clueCards={state.clueCards}
                groundingResults={state.lastGroundingResults}
                leadMessages={state.leadMessages}
                followUpPrompts={state.followUpPrompts}
                onTalk={actions.handleTalkStreaming}
                onConfront={actions.handleConfront}
                onOpenAttachment={openDocumentAttachment}
              />
            ) : null
          }
        />
        <Route
          path="board"
          element={
            caseDetail && currentState ? (
              <BoardView
                caseDetail={caseDetail}
                saveState={currentState}
                boardNodes={state.boardNodes}
                onBoardLink={actions.handleBoardLink}
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
              onSelectCase={(id) => {
                dispatch({ type: 'SET_SELECTED_CASE', payload: id });
                navigate(`/${id}/interrogation`);
              }}
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

  useEffect(() => {
    if (!state.isAuthenticated && state.aliasDraft) {
      void actions.restoreSession();
    }
  }, []);

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

  const { caseDetail, saveState, conversations, unlockedSuspects } = state;
  const currentState = saveState ?? caseDetail?.state ?? null;

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
                onSelectCase={(id) => {
                  dispatch({ type: 'SET_SELECTED_CASE', payload: id });
                  navigate(`/${id}/interrogation`);
                }}
                onPlayableCasesChanged={actions.reloadPlayableCases}
              />
            }
          />
          <Route path="/:caseId/*" element={<CaseShell />} />
        </Routes>

        <aside className="right-rail">
          {isLibraryRoute ? (
            <>
              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Library Guide</span>
                  <strong>Flow</strong>
                </div>
                <p className="objective-copy">
                  Search approved cases from the home screen, open one from the library, and return here whenever you
                  want to switch investigations.
                </p>
              </section>

              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Access Level</span>
                  <strong>{state.sessionRole.toUpperCase()}</strong>
                </div>
                <p className="objective-copy">
                  {state.sessionRole === 'admin'
                    ? 'Admin accounts can browse public cases, review pending drafts, and approve cases after moderation.'
                    : 'Player accounts can browse, search, play approved cases, and create private drafts in the authoring studio.'}
                </p>
              </section>
            </>
          ) : (
            <>
              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Pinned Evidence</span>
                  <strong>{state.pinnedDocuments.length.toString().padStart(2, '0')}</strong>
                </div>
                <div className="pinboard-grid">
                  {state.pinnedDocuments.slice(0, 4).map((doc) => (
                    <button
                      key={doc.id}
                      className="pinboard-card"
                      onClick={() => dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: doc.id })}
                    >
                      <MediaPlate
                        src={doc.image_url}
                        alt={doc.title}
                        kind="evidence"
                        label={doc.id.toUpperCase()}
                        className="pinboard-media"
                      />
                      <strong>{doc.title}</strong>
                    </button>
                  ))}
                </div>
              </section>

              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Contradiction Log</span>
                  <strong>{state.contradictionItems.length.toString().padStart(2, '0')}</strong>
                </div>
                <div className="contradiction-stack">
                  {state.contradictionItems.length ? (
                    state.contradictionItems.map((item) => (
                      <article key={item.title} className={`contradiction-card ${item.severity}`}>
                        <div className="contradiction-topline">
                          <span>{item.severity}</span>
                          <strong>{item.title}</strong>
                        </div>
                        <p>{item.source}</p>
                      </article>
                    ))
                  ) : (
                    <div className="empty-state compact">
                      No contradictions logged yet. Interrogate, search, and rescan to create pressure points.
                    </div>
                  )}
                </div>
              </section>

              <section className="rail-panel theory-rail">
                <div className="rail-heading">
                  <span>Theory Board Progress</span>
                  <strong>{Math.min(100, 18 + (currentState?.board_links.length ?? 0) * 12)}%</strong>
                </div>
                <div className="rail-theory-widget">
                  <div className="rail-theory-node">Motive</div>
                  <div className="rail-theory-node center">Truth</div>
                  <div className="rail-theory-node">Means</div>
                </div>
              </section>

              <section className="rail-panel">
                <div className="rail-heading">
                  <span>Current Objective</span>
                  <strong>Live</strong>
                </div>
                <p className="objective-copy">{currentState?.current_objective ?? 'Loading objective...'}</p>
              </section>
            </>
          )}
        </aside>
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

