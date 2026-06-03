import type { CaseSummary, SessionRole } from '../types';
import { MediaPlate, PanelHeader } from '../ui';

type Props = {
  cases: CaseSummary[];
  pendingCases: CaseSummary[];
  role: SessionRole;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  onSelectCase: (caseId: string) => void;
  onReviewCase: (caseId: string) => void;
  onOpenAuthoring: () => void;
};

function matchesCase(caseSummary: CaseSummary, searchQuery: string) {
  const needle = searchQuery.trim().toLowerCase();
  if (!needle) return true;
  return [caseSummary.title, caseSummary.hook, caseSummary.difficulty, caseSummary.id]
    .filter(Boolean)
    .some((value) => value.toLowerCase().includes(needle));
}

export default function HomeView({
  cases,
  pendingCases,
  role,
  searchQuery,
  onSearchQueryChange,
  onSelectCase,
  onReviewCase,
  onOpenAuthoring,
}: Props) {
  const visibleCases = cases.filter((caseSummary) => matchesCase(caseSummary, searchQuery));
  const visiblePending = pendingCases.filter((caseSummary) => matchesCase(caseSummary, searchQuery));

  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Case Library"
        title="Search and launch investigation files"
        subtitle={
          role === 'admin'
            ? 'Browse public cases, create new drafts, and review or play pending submissions before they are approved.'
            : 'Browse the approved case catalog, search by title or theme, and open the authoring studio to build private draft cases.'
        }
        actions={
          <button className="dossier-button dossier-button-accent" type="button" onClick={onOpenAuthoring}>
            Open Authoring Studio
          </button>
        }
      />

      <section className="intel-card">
        <div className="library-topbar">
          <label className="library-search">
            <span>Search Cases</span>
            <input
              value={searchQuery}
              onChange={(event) => onSearchQueryChange(event.target.value)}
              placeholder="Search by title, hook, difficulty, or case id"
            />
          </label>
          <div className="status-chip">{visibleCases.length.toString().padStart(2, '0')} approved</div>
        </div>

        <div className="case-library-grid">
          {visibleCases.length ? (
            visibleCases.map((caseSummary) => (
              <article key={caseSummary.id} className="case-library-card">
                <MediaPlate
                  src={caseSummary.cover_image_url}
                  alt={caseSummary.title}
                  kind="cover"
                  label={caseSummary.difficulty}
                />
                <div className="case-library-copy">
                  <div className="case-library-meta">
                    <span className="card-chip">{caseSummary.id}</span>
                    <span className="card-chip">{caseSummary.estimated_minutes} min</span>
                  </div>
                  <h3>{caseSummary.title}</h3>
                  <p>{caseSummary.hook}</p>
                </div>
                <div className="case-library-actions">
                  <button className="dossier-button dossier-button-accent" type="button" onClick={() => onSelectCase(caseSummary.id)}>
                    Open Case
                  </button>
                </div>
              </article>
            ))
          ) : (
            <div className="empty-state">
              No approved cases matched that search. Try a broader title, theme, or difficulty keyword.
            </div>
          )}
        </div>
      </section>

      {role === 'admin' ? (
        <section className="intel-card">
          <PanelHeader
            eyebrow="Pending Review"
            title="Draft submissions awaiting approval"
            subtitle="Open the authoring editor to review structure, assets, and moderation details before publishing."
          />
          <div className="case-library-grid">
            {visiblePending.length ? (
              visiblePending.map((caseSummary) => (
                <article key={caseSummary.id} className="case-library-card pending-review-card">
                  <MediaPlate
                    src={caseSummary.cover_image_url}
                    alt={caseSummary.title}
                    kind="cover"
                    label={caseSummary.status}
                  />
                  <div className="case-library-copy">
                    <div className="case-library-meta">
                      <span className="card-chip">{caseSummary.id}</span>
                      <span className="card-chip">owner: {caseSummary.owner_alias ?? 'unknown'}</span>
                    </div>
                    <h3>{caseSummary.title}</h3>
                    <p>{caseSummary.hook}</p>
                  </div>
                  <div className="case-library-actions">
                    <button className="dossier-button dossier-button-accent" type="button" onClick={() => onReviewCase(caseSummary.id)}>
                      Review Draft
                    </button>
                    <button className="dossier-button dossier-button-ghost" type="button" onClick={() => onSelectCase(caseSummary.id)}>
                      Play Draft
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <div className="empty-state">
                No pending drafts matched that search. Once creators submit a case, it will appear here for approval.
              </div>
            )}
          </div>
        </section>
      ) : null}
    </section>
  );
}
