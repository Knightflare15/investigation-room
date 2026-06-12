import type { CommunityStatsResponse, Suspect, TheoryScore } from '../types';
import { PanelHeader, SuspicionMeter } from '../ui';

type Props = {
  suspects: Suspect[];
  communityStats: CommunityStatsResponse;
  theoryScore: TheoryScore | null;
  onRestartCase: () => Promise<void>;
};

export default function CommunityView({ suspects, communityStats, theoryScore, onRestartCase }: Props) {
  const scoreCategories = theoryScore
    ? [
        ['Culprit', theoryScore.culprit],
        ['Motive', theoryScore.motive],
        ['Timeline', theoryScore.timeline],
        ['Evidence', theoryScore.evidence],
      ] as const
    : [];
  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Community"
        title="How Other Detectives Accused"
        subtitle="Compare your theory against the broader pattern of suspicion and reasoning."
      />
      <div className="community-actions">
        <button
          className="dossier-button dossier-button-ghost"
          type="button"
          onClick={() => {
            if (
              window.confirm(
                'Restart this case from the beginning? Your current progress will be cleared, but the submitted theory stays in community history.',
              )
            ) {
              void onRestartCase();
            }
          }}
        >
          Replay This Case
        </button>
      </div>
      {theoryScore ? (
        <section className="score-card">
          <div className="score-verdict">
            <div>
              <p className="eyebrow">Canonical Verdict</p>
              <h3>{theoryScore.verdict}</h3>
            </div>
            <strong>{theoryScore.total}/{theoryScore.possible}</strong>
          </div>
          <div className="score-breakdown">
            {scoreCategories.map(([label, category]) => (
              <article key={label} className="score-category">
                <div><strong>{label}</strong><span>{category.earned}/{category.possible}</span></div>
                <p>{category.feedback}</p>
              </article>
            ))}
          </div>
          <div className="canonical-truth">
            <p className="subheading">Canonical Truth</p>
            <h3>{suspects.find((suspect) => suspect.id === theoryScore.canonical_truth.culprit_id)?.display_name ?? theoryScore.canonical_truth.culprit_id}</h3>
            <p><strong>Motive:</strong> {theoryScore.canonical_truth.motive_summary}</p>
            <p><strong>Timeline:</strong> {theoryScore.canonical_truth.timeline_summary}</p>
          </div>
        </section>
      ) : null}
      <div className="community-grid">
        <section className="intel-card">
          <div className="intel-card-header">
            <span>Accusation Totals</span>
            <strong>{Object.keys(communityStats.culprit_counts).length.toString().padStart(2, '0')}</strong>
          </div>
          <div className="intel-list">
            {Object.entries(communityStats.culprit_counts).map(([suspectId, count]) => (
              <div key={suspectId} className="community-row">
                <div>
                  <strong>{suspects.find((s) => s.id === suspectId)?.display_name ?? suspectId}</strong>
                  <span>community accusation weight</span>
                </div>
                <SuspicionMeter value={Math.min(100, count * 18)} />
              </div>
            ))}
          </div>
        </section>
        <section className="intel-card">
          <div className="intel-card-header">
            <span>Accusation Excerpts</span>
            <strong>{communityStats.excerpts.length.toString().padStart(2, '0')}</strong>
          </div>
          <div className="excerpt-stack">
            {communityStats.excerpts.map((excerpt, index) => (
              <article key={`${excerpt.player_alias}-${index}`} className="excerpt-card">
                <strong>{excerpt.player_alias}</strong>
                <p>{excerpt.excerpt}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
