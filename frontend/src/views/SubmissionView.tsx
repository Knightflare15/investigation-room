import { type FormEvent, useState } from 'react';
import type { CaseDocument, CaseDetailResponse, PlayerCaseState, SubmitTheoryResponse } from '../types';
import { MediaPlate, PanelHeader } from '../ui';

type Props = {
  caseDetail: CaseDetailResponse;
  saveState: PlayerCaseState;
  pinnedDocuments: CaseDocument[];
  onSubmitTheory: (culpritId: string, motive: string, timeline: string) => Promise<SubmitTheoryResponse>;
  onNavigateToCommunity: () => void;
  onRestartCase: () => Promise<void>;
};

export default function SubmissionView({
  caseDetail,
  saveState,
  pinnedDocuments,
  onSubmitTheory,
  onNavigateToCommunity,
  onRestartCase,
}: Props) {
  const [culpritId, setCulpritId] = useState(caseDetail.suspects[0]?.id ?? '');
  const [theoryMotive, setTheoryMotive] = useState('');
  const [theoryTimeline, setTheoryTimeline] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!culpritId) return;
    if (pinnedDocuments.length < 3 || theoryMotive.trim().length < 20 || theoryTimeline.trim().length < 20) {
      setError('Strengthen the accusation before submitting: pin at least three records and explain both motive and timeline.');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await onSubmitTheory(culpritId, theoryMotive, theoryTimeline);
      onNavigateToCommunity();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRestart() {
    if (
      !window.confirm(
        'Restart this case from the beginning? Your current progress will be cleared, but the submitted theory stays in community history.',
      )
    ) {
      return;
    }
    setError('');
    setRestarting(true);
    try {
      await onRestartCase();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRestarting(false);
    }
  }

  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Submission"
        title="Formal Accusation"
        subtitle="Name the culprit and state your case."
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="submission-layout">
        <form className="submission-form report-card" onSubmit={handleSubmit}>
          <label>
            Culprit
            <select value={culpritId} onChange={(e) => setCulpritId(e.target.value)}>
              {caseDetail.suspects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Motive
            <textarea value={theoryMotive} onChange={(e) => setTheoryMotive(e.target.value)} />
          </label>
          <label>
            Timeline
            <textarea value={theoryTimeline} onChange={(e) => setTheoryTimeline(e.target.value)} />
          </label>
          <div className="submission-actions">
            <button className="dossier-button dossier-button-accent" type="submit" disabled={submitting || restarting}>
              {submitting ? 'Submitting...' : 'Submit Accusation'}
            </button>
            <button
              className="dossier-button dossier-button-ghost"
              type="button"
              onClick={handleRestart}
              disabled={submitting || restarting}
            >
              {restarting ? 'Restarting...' : 'Restart Case'}
            </button>
          </div>
        </form>

        <aside className="intel-card">
          <div className="intel-card-header">
            <span>Pinned Evidence</span>
            <strong>{pinnedDocuments.length.toString().padStart(2, '0')}</strong>
          </div>
          <div className="pinned-grid">
            {pinnedDocuments.map((doc) => (
              <div key={doc.id} className="pinned-evidence-card">
                <MediaPlate src={doc.image_url} alt={doc.title} kind="evidence" label={doc.id.toUpperCase()} />
                <strong>{doc.title}</strong>
                <span>{doc.summary}</span>
              </div>
            ))}
          </div>
          <div className="submission-readiness">
            <p className="subheading">Case Readiness</p>
            <span>{pinnedDocuments.length >= 3 ? 'Ready' : 'Needs work'}: supporting evidence ({pinnedDocuments.length}/3)</span>
            <span>{theoryMotive.trim().length >= 20 ? 'Ready' : 'Needs work'}: motive explanation</span>
            <span>{theoryTimeline.trim().length >= 20 ? 'Ready' : 'Needs work'}: timeline explanation</span>
            <span>{saveState.completed_deduction_ids.length} confirmed deductions reached</span>
          </div>
        </aside>
      </div>
    </section>
  );
}
