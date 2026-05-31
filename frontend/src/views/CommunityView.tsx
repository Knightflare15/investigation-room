import type { CommunityStatsResponse, Suspect } from '../types';
import { PanelHeader, SuspicionMeter } from '../ui';

type Props = {
  suspects: Suspect[];
  communityStats: CommunityStatsResponse;
};

export default function CommunityView({ suspects, communityStats }: Props) {
  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Community"
        title="How Other Detectives Accused"
        subtitle="Compare your theory against the broader pattern of suspicion and reasoning."
      />
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
            <span>Theory Excerpts</span>
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
