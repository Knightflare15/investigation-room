import { type FormEvent, useState } from 'react';
import type { CaseDetailResponse, CaseDocument, ClueCard, ConversationState, PlayerCaseState, Suspect } from '../types';
import { MediaPlate, PanelHeader } from '../ui';

type Props = {
  caseDetail: CaseDetailResponse;
  saveState: PlayerCaseState;
  selectedSuspect: Suspect | undefined;
  selectedDocument: CaseDocument | undefined;
  conversations: Record<string, ConversationState>;
  clueCards: ClueCard[];
  followUpPrompts: string[];
  onTalk: (message: string) => Promise<void>;
  onConfront: (evidenceId: string, message: string) => Promise<void>;
  onOpenAttachment: (doc: CaseDocument | null) => void;
};

export default function InterrogationView({
  caseDetail,
  selectedSuspect,
  selectedDocument,
  conversations,
  clueCards,
  followUpPrompts,
  onTalk,
  onConfront,
  onOpenAttachment,
}: Props) {
  const [messageDraft, setMessageDraft] = useState('');
  const [confrontEvidenceId, setConfrontEvidenceId] = useState('');

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
    await onConfront(confrontEvidenceId, `Explain this evidence: ${confrontEvidenceId}`);
  }

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
              <div className="tag-row">
                {(selectedDocument?.entity_tags ?? []).map((tag) => (
                  <span key={tag} className="tag">
                    {tag}
                  </span>
                ))}
              </div>
              <pre>{selectedDocument?.body ?? 'No evidence text loaded.'}</pre>
            </div>
          </div>
        </article>

        <aside className="interrogation-sidebar">
          <section className="intel-card">
            <div className="intel-card-header">
              <span>Interrogation Workspace</span>
              <strong>Live</strong>
            </div>
            <div className="workspace-question">
              <p className="subheading">Focus Question</p>
              <p>
                {selectedDocument
                  ? `What is the significance of "${selectedDocument.entity_tags[0] ?? selectedDocument.title}" in this record?`
                  : 'What is the suspect trying to avoid?'}
              </p>
            </div>
            <div className="clue-card-stack">
              {clueCards.map((clue, index) => (
                <div key={`${clue.text}-${index}`} className={`clue-card clue-${clue.type.toLowerCase()}`}>
                  <span>{clue.text}</span>
                  <strong>{clue.type}</strong>
                </div>
              ))}
            </div>
            <div className="prompt-chip-row">
              {followUpPrompts.map((prompt) => (
                <button key={prompt} className="prompt-chip" onClick={() => setMessageDraft(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Interrogation Tools</span>
              <strong>
                {activeConversation?.trust ?? 50}/{activeConversation?.guardedness ?? 25}
              </strong>
            </div>
            <div className="tool-list">
              <button
                className="tool-row"
                type="button"
                onClick={() => setMessageDraft('Summarize what you have told me so far.')}
              >
                Summarize Statement
              </button>
              <button
                className="tool-row"
                type="button"
                onClick={() =>
                  setMessageDraft("Your account doesn't align with the evidence. Walk me through the timeline again.")
                }
              >
                Check Consistency
              </button>
              <button
                className="tool-row"
                type="button"
                onClick={() =>
                  setMessageDraft(
                    `Compare your statement to ${selectedDocument?.title ?? 'this record'} — there is a discrepancy.`,
                  )
                }
              >
                Compare to Evidence
              </button>
              <button
                className="tool-row"
                type="button"
                onClick={() => setMessageDraft(followUpPrompts[0] ?? 'Press the timeline')}
              >
                Generate Follow-up
              </button>
            </div>
          </section>
        </aside>

        <article className="conversation-docket">
          <div className="conversation-titlebar">
            <div>
              <strong>Interrogation: {selectedSuspect.display_name}</strong>
              <span>Session file recorded against the current case state</span>
            </div>
            <div className="conversation-metrics">
              <div className="metric-chip">Trust {activeConversation?.trust ?? 50}</div>
              <div className="metric-chip">Guardedness {activeConversation?.guardedness ?? 25}</div>
            </div>
          </div>
          <div className="conversation-log">
            {(
              activeConversation?.transcript.length
                ? activeConversation.transcript
                : [{ speaker: 'System', text: 'Begin the interrogation and press for the hidden inconsistency.' }]
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
              placeholder="Ask about the deed, the ledger, the hidden meeting, the office call, or any contradiction you have uncovered."
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
