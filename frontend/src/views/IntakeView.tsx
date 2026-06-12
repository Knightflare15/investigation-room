import type { CaseDetailResponse } from '../types';
import { MediaPlate, PanelHeader } from '../ui';

type Props = {
  caseDetail: CaseDetailResponse;
};

export default function IntakeView({ caseDetail }: Props) {
  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Case Overview"
        title={caseDetail.case.hook}
        subtitle="Police first-pass briefing and location dossiers."
      />
      <div className="intake-grid">
        <div className="brief-card parchment-card">
          <span className="card-chip">Police Brief</span>
          <h3>{caseDetail.case.title}</h3>
          <p>{caseDetail.police_summary}</p>
        </div>
        <MediaPlate
          src={caseDetail.case.cover_image_url}
          alt={caseDetail.case.title}
          kind="cover"
          label="Case Cover"
          className="cover-plate"
        />
      </div>
      <div className="location-dossier-grid">
        {caseDetail.location_dossiers.map((location) => (
          <article key={location.id} className="location-card">
            <MediaPlate src={location.image_url} alt={location.label} kind="location" label="Location Dossier" />
            <div className="location-card-copy">
              <p className="subheading">{location.label}</p>
              <p>{location.summary}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
