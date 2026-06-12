import { type FormEvent, useState } from 'react';
import type { CaseDetailResponse, CaseDocument, ConversationState, PlayerCaseState, Suspect } from '../types';
import { MediaPlate, PanelHeader } from '../ui';

type Props = {
  caseDetail: CaseDetailResponse;
  saveState: PlayerCaseState;
  selectedSuspect: Suspect | undefined;
  selectedDocument: CaseDocument | undefined;
  conversations: Record<string, ConversationState>;
  onTalk: (message: string) => Promise<void>;
  onConfront: (evidenceId: string, message: string) => Promise<void>;
  onBeginNewSession: () => Promise<void>;
  onOpenAttachment: (doc: CaseDocument | null) => void;
};

export default function InterrogationView({
  caseDetail,
  selectedSuspect,
  selectedDocument,
  conversations,
  onTalk,
  onConfront,
  onBeginNewSession,
  onOpenAttachment,
}: Props) {
  const [messageDraft, setMessageDraft] = useState('');
  const [confrontEvidenceId, setConfrontEvidenceId] = useState('');
  const [confrontDraft, setConfrontDraft] = useState('');

  const activeConversation = selectedSuspect ? conversations[selectedSuspect.id] : undefined;

  async function handleTalk(event: FormEvent) {
    event.preventDefault();
    if (!selectedSuspect || !messageDraft.trim()) return;
    const msg = messageDraft;
    setMessageDraft('');
    // onTalk is wired to the streaming action; the live reply renders from the transcript.
    await onTalk(msg);
  }

  async function handleConfront() {
    if (!selectedSuspect || !confrontEvidenceId) return;
    const evidence = caseDetail.documents.find((document) => document.id === confrontEvidenceId);
    const question = confrontDraft.trim() || `What does ${evidence?.title ?? 'this evidence'} tell me that you haven't?`;
    setConfrontDraft('');
    await onConfront(confrontEvidenceId, question);
  }

  async function handleBeginNewSession() {
    if (activeConversation?.transcript.length && !window.confirm('Start a new session? The current transcript will be compacted into memory.')) {
      return;
    }
    await onBeginNewSession();
  }

  const posture =
    (activeConversation?.guardedness ?? 25) >= 70
      ? 'Shutting Down'
      : (activeConversation?.guardedness ?? 25) >= 45
        ? 'Defensive'
        : (activeConversation?.trust ?? 50) >= 60
          ? 'Cooperative'
          : 'Careful';
  const confrontedEvidence = caseDetail.documents.filter((document) =>
    activeConversation?.confronted_evidence_ids.includes(document.id),
  );

  if (!selectedSuspect) {
    return (
      <section className="dossier-surface">
        <div className="empty-state">No suspect selected. Use the left rail to select a suspect.</div>
      </section>
    );
  }

  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Interrogation"
        title={selectedSuspect.display_name}
        subtitle={selectedSuspect.public_profile.summary}
      />
      <div className="interrogation-layout">
        <article className="parchment-viewer interrogation-document">
          <div className="document-toolbar">
            <span>Document Under Review</span>
            <span>{selectedDocument?.title ?? 'No active evidence'}</span>
          </div>
          <div className="document-reading-surface">
            <div className="document-image-strip">
              <button
                className="media-trigger"
                type="button"
                onClick={() => onOpenAttachment(selectedDocument ?? null)}
                disabled={!selectedDocument?.image_url}
              >
                <MediaPlate
                  src={selectedDocument?.image_url}
                  alt={selectedDocument?.title ?? 'Evidence'}
                  kind="evidence"
                  label={selectedDocument?.id?.toUpperCase() ?? 'EV'}
                />
              </button>
              <div className="suspect-docket">
                <MediaPlate
                  src={selectedSuspect.image_url}
                  alt={selectedSuspect.display_name}
                  kind="suspect"
                  label={selectedSuspect.portrait_key ?? selectedSuspect.display_name.slice(0, 2)}
                  className="docket-portrait"
                />
                <div>
                  <strong>{selectedSuspect.display_name}</strong>
                  <span>{selectedSuspect.public_profile.role}</span>
                </div>
              </div>
            </div>
            <div className="document-body">
              <h3>{selectedDocument?.title ?? 'Select evidence from the archive'}</h3>
              <p className="document-summary">
                {selectedDocument?.summary ?? 'Use the archive and pinned wall to focus the interrogation.'}
              </p>
              <pre>{selectedDocument?.body ?? 'No evidence text loaded.'}</pre>
            </div>
          </div>
        </article>

        <article className="conversation-docket">
          <div className="conversation-titlebar">
            <div>
              <strong>Interrogation: {selectedSuspect.display_name}</strong>
              <span>Session file recorded against the current case state</span>
            </div>
            <div className="conversation-metrics">
              <div className="metric-chip">{posture}</div>
              <button className="dossier-button dossier-button-ghost" type="button" onClick={() => void handleBeginNewSession()}>
                Start New Session
              </button>
            </div>
          </div>
          {confrontedEvidence.length ? (
            <div className="confronted-evidence-strip">
              <strong>Evidence confronted:</strong>
              <span>{confrontedEvidence.map((document) => document.title).join(', ')}</span>
            </div>
          ) : null}
          <div className="conversation-log">
            {(
              activeConversation?.transcript.length
                ? activeConversation.transcript
                : [
                    {
                      speaker: 'System',
                      text: 'Begin the interrogation.',
                    },
                  ]
            ).map((turn, index) => (
              <div key={`${turn.speaker}-${index}`} className={turn.speaker === 'detective' ? 'bubble player' : 'bubble suspect'}>
                <strong>{turn.speaker}</strong>
                <p>{turn.text}</p>
              </div>
            ))}
          </div>
          <form className="conversation-form" onSubmit={handleTalk}>
            <textarea
              value={messageDraft}
              onChange={(e) => setMessageDraft(e.target.value)}
              placeholder="Question the suspect..."
            />
            <div className="conversation-actions">
              <button className="dossier-button dossier-button-accent" type="submit">
                Question Suspect
              </button>
              <select value={confrontEvidenceId} onChange={(e) => setConfrontEvidenceId(e.target.value)}>
                <option value="">Select evidence to confront</option>
                {caseDetail.documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title}
                  </option>
                ))}
              </select>
              <input
                value={confrontDraft}
                onChange={(event) => setConfrontDraft(event.target.value)}
                placeholder="Ask a specific question about the evidence..."
              />
              <button className="dossier-button dossier-button-ghost" type="button" onClick={handleConfront}>
                Confront with Evidence
              </button>
            </div>
          </form>
        </article>
      </div>
    </section>
  );
}
