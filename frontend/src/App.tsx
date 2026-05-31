import { useEffect } from 'react';
import { Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import AuthoringStudio from './AuthoringStudio';
import { useGame } from './context/GameContext';
import { useGameActions } from './context/useGameActions';
import type { CaseDocument } from './types';
import { CrestMark, MediaPlate, PanelHeader, SuspicionMeter } from './ui';
import ArchiveView from './views/ArchiveView';
import BoardView from './views/BoardView';
import CommunityView from './views/CommunityView';
import IntakeView from './views/IntakeView';
import InterrogationView from './views/InterrogationView';
import SubmissionView from './views/SubmissionView';

type ViewId = 'intake' | 'archive' | 'interrogation' | 'board' | 'submission' | 'community' | 'authoring';

const tabs: Array<{ id: ViewId; label: string; glyph: string }> = [
  { id: 'intake', label: 'Intake', glyph: '⌘' },
  { id: 'archive', label: 'Archive', glyph: '▣' },
  { id: 'interrogation', label: 'Interrogation', glyph: '✦' },
  { id: 'board', label: 'Evidence Board', glyph: '⌗' },
  { id: 'submission', label: 'Submission', glyph: '✓' },
  { id: 'community', label: 'Community', glyph: '◌' },
  { id: 'authoring', label: 'Authoring', glyph: '✎' },
];

const overviewLinks: Array<{ label: string; view: ViewId }> = [
  { label: 'Case Brief', view: 'intake' },
  { label: 'Archive', view: 'archive' },
  { label: 'Interrogation', view: 'interrogation' },
  { label: 'Theory Board', view: 'board' },
  { label: 'Community', view: 'community' },
];

// Shell that reads caseId from the URL and loads the case
function CaseShell() {
  const { caseId = '', view = 'interrogation' } = useParams<{ caseId: string; view: string }>();
  const { state, dispatch } = useGame();
  const actions = useGameActions();
  const navigate = useNavigate();

  useEffect(() => {
    if (caseId && caseId !== state.selectedCaseId) {
      dispatch({ type: 'SET_SELECTED_CASE', payload: caseId });
      void actions.loadCase(caseId);
    }
  }, [caseId]);

  const { caseDetail, saveState, conversations, communityStats, unlockedSuspects } = state;
  const currentState = saveState ?? caseDetail?.state ?? null;
  const selectedSuspect =
    caseDetail?.suspects.find((s) => s.id === state.selectedSuspectId) ?? caseDetail?.suspects[0];
  const selectedDocument =
    caseDetail?.documents.find((d) => d.id === state.selectedDocumentId) ?? caseDetail?.documents[0];

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
        <Route
          path="intake"
          element={caseDetail ? <IntakeView caseDetail={caseDetail} /> : null}
        />
        <Route
          path="archive"
          element={
            caseDetail && currentState ? (
              <ArchiveView
                caseDetail={caseDetail}
                saveState={currentState}
                selectedDocumentId={state.selectedDocumentId}
                onSelectDocument={(id) => dispatch({ type: 'SET_SELECTED_DOCUMENT', payload: id })}
                onTogglePin={actions.handleTogglePin}
                onOpenAttachment={openDocumentAttachment}
                searchQuery={state.searchQuery}
                onSearchQueryChange={(q) => dispatch({ type: 'SET_SEARCH_QUERY', payload: q })}
                searchResults={state.searchResults}
                rescanResults={state.rescanResults}
                onSearch={async (e) => { e.preventDefault(); await actions.handleSearch(); }}
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
              />
            ) : null
          }
        />
        <Route
          path="community"
          element={
            communityStats ? (
              <CommunityView suspects={unlockedSuspects} communityStats={communityStats} />
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
  const navigate = useNavigate();

  useEffect(() => {
    void actions.loadCases();
  }, [state.alias]);

  const caseId = state.selectedCaseId;

  function navTo(view: ViewId) {
    if (caseId) navigate(`/${caseId}/${view}`);
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
          <strong>{caseDetail?.case.title ?? 'Awaiting Case'}</strong>
          <span className="command-meta">{caseId || 'No case id'}</span>
        </div>
        <div className="command-stat">
          <span className="command-label">Detective</span>
          <strong>{state.alias}</strong>
          <span className="command-meta">Consulting Detective</span>
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
          <button className="icon-button" type="button" aria-label="Search interface">⌕</button>
          <button className="icon-button" type="button" aria-label="Alerts">◌</button>
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
                    className={
                      state.selectedSuspectId === suspect.id ? 'suspect-list-card active' : 'suspect-list-card'
                    }
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

          <section className="rail-panel rail-identity">
            <label className="alias-box">
              Detective Alias
              <input
                value={state.aliasDraft}
                onChange={(e) => dispatch({ type: 'SET_ALIAS_DRAFT', payload: e.target.value })}
              />
            </label>
            <button
              className="dossier-button dossier-button-ghost"
              onClick={() => dispatch({ type: 'COMMIT_ALIAS' })}
            >
              Update Detective Identity
            </button>
          </section>
        </aside>

        <Routes>
          <Route path="/:caseId/*" element={<CaseShell />} />
          <Route
            path="/"
            element={
              state.cases[0] ? (
                <Navigate to={`/${state.cases[0].id}/interrogation`} replace />
              ) : (
                <main className="center-stage">
                  <div className="rail-panel loading-panel">
                    {state.loading ? 'Loading cases…' : 'No cases found.'}
                  </div>
                </main>
              )
            }
          />
        </Routes>

        <aside className="right-rail">
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
            <button className="dossier-button dossier-button-ghost" onClick={() => navTo('board')}>
              Open Theory Board
            </button>
          </section>

          <section className="rail-panel">
            <div className="rail-heading">
              <span>Current Objective</span>
              <strong>Live</strong>
            </div>
            <p className="objective-copy">{currentState?.current_objective ?? 'Loading objective...'}</p>
          </section>
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
            onClick={(e) => e.stopPropagation()}
          >
            <div className="document-toolbar">
              <span>{state.mediaPreview.eyebrow}</span>
              <button
                className="icon-button modal-close"
                type="button"
                onClick={() => dispatch({ type: 'SET_MEDIA_PREVIEW', payload: null })}
                aria-label="Close visual attachment"
              >
                ×
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
