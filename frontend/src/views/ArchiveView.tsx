import type { FormEvent } from 'react';
import type { CaseDetailResponse, CaseDocument, PlayerCaseState, RescanResponse, SearchResult } from '../types';
import { MediaPlate, PanelHeader } from '../ui';

type Props = {
  caseDetail: CaseDetailResponse;
  saveState: PlayerCaseState;
  selectedDocumentId: string;
  selectedLocationId: string;
  onSelectDocument: (id: string) => void;
  onSelectLocation: (id: string) => void;
  onTogglePin: (documentId: string) => Promise<void>;
  onOpenAttachment: (doc: CaseDocument | null) => void;
  searchQuery: string;
  onSearchQueryChange: (q: string) => void;
  searchResults: SearchResult[];
  rescanResults: RescanResponse | null;
  onSearch: (event: FormEvent) => Promise<void>;
  onRescan: () => Promise<void>;
};

function getDocumentAttachmentMeta(document?: CaseDocument | null) {
  if (!document) return null;
  if (document.id === 'doc_incident') {
    return {
      title: 'Incident Board',
      eyebrow: 'Visual Attachment',
      summary: 'A stylized reference board attached to the police first-pass summary.',
    };
  }
  return {
    title: `${document.title} Plate`,
    eyebrow: 'Visual Attachment',
    summary: `A reference image attached to this ${document.doc_type.replace(/_/g, ' ')} record.`,
  };
}

export default function ArchiveView({
  caseDetail,
  saveState,
  selectedDocumentId,
  selectedLocationId,
  onSelectDocument,
  onSelectLocation,
  onTogglePin,
  onOpenAttachment,
  searchQuery,
  onSearchQueryChange,
  searchResults,
  rescanResults,
  onSearch,
  onRescan,
}: Props) {
  const unlockedDocuments = caseDetail.documents;
  const selectedDocument = unlockedDocuments.find((d) => d.id === selectedDocumentId) ?? unlockedDocuments[0];
  const selectedLocation = caseDetail.location_dossiers.find((location) => location.id === selectedLocationId) ?? caseDetail.location_dossiers[0];
  const selectedDocumentIsPinned = Boolean(selectedDocument && saveState.pinned_evidence_ids.includes(selectedDocument.id));
  const selectedDocumentAttachment = getDocumentAttachmentMeta(selectedDocument);

  return (
    <section className="dossier-surface">
      <PanelHeader
        eyebrow="Archive"
        title={selectedDocument?.title ?? 'Case Archive'}
        subtitle="Search the file, then run focused rescans by applying a specific lead to a specific place."
        actions={
          <button className="dossier-button dossier-button-accent" onClick={onRescan}>
            Run Focused Rescan
          </button>
        }
      />
      <form className="utility-bar" onSubmit={onSearch}>
        <input
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          placeholder="Lead to test in this location: hidden door, Ashdown Suite, Lena Orlov..."
        />
        <button className="dossier-button dossier-button-ghost" type="submit">
          Search
        </button>
      </form>
      <div className="archive-layout">
        <article className="parchment-viewer">
          {selectedDocument ? (
            <>
              <div className="document-toolbar">
                <span>{selectedDocument.id}</span>
                <span>{selectedDocument.source_label}</span>
                <span>{selectedDocument.doc_type}</span>
              </div>
              <div className="document-reading-surface">
                <div className="document-image-strip">
                  <button className="media-trigger" type="button" onClick={() => onOpenAttachment(selectedDocument)}>
                    <MediaPlate
                      src={selectedDocument.image_url}
                      alt={selectedDocument.title}
                      kind="evidence"
                      label={selectedDocument.id.toUpperCase()}
                    />
                  </button>
                  <div className="note-card">
                    <strong>{selectedDocumentAttachment?.title ?? 'Visual Attachment'}</strong>
                    <span>{selectedDocumentAttachment?.summary ?? selectedDocument.folder.replace(/_/g, ' ')}</span>
                    {selectedDocument.image_url ? (
                      <button className="inline-link-button" type="button" onClick={() => onOpenAttachment(selectedDocument)}>
                        Open full plate
                      </button>
                    ) : null}
                  </div>
                </div>
                <div className="document-body">
                  <h3>{selectedDocument.title}</h3>
                  <p className="document-summary">{selectedDocument.summary}</p>
                  <div className="tag-row">
                    {selectedDocument.entity_tags.map((tag) => (
                      <span key={tag} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <pre>{selectedDocument.body}</pre>
                </div>
              </div>
              <div className="document-actions">
                <button
                  className={selectedDocumentIsPinned ? 'dossier-button dossier-button-accent' : 'dossier-button dossier-button-ghost'}
                  onClick={() => onTogglePin(selectedDocument.id)}
                >
                  {selectedDocumentIsPinned ? 'Pinned to Evidence Wall' : 'Pin Evidence'}
                </button>
              </div>
            </>
          ) : (
            <div className="empty-state">No archive document is currently selected.</div>
          )}
        </article>

        <div className="archive-intel-column">
          <section className="intel-card">
            <div className="intel-card-header">
              <span>Rescan Location</span>
              <strong>{caseDetail.location_dossiers.length.toString().padStart(2, '0')}</strong>
            </div>
            <select value={selectedLocation?.id ?? ''} onChange={(event) => onSelectLocation(event.target.value)}>
              {caseDetail.location_dossiers.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.label}
                </option>
              ))}
            </select>
            {selectedLocation ? <p className="document-summary">{selectedLocation.summary}</p> : null}
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Unlocked Documents</span>
              <strong>{unlockedDocuments.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="intel-list">
              {unlockedDocuments.map((document) => (
                <button
                  key={document.id}
                  className="intel-row"
                  onClick={() => onSelectDocument(document.id)}
                >
                  <strong>{document.title}</strong>
                  <span>{document.summary || document.folder.replace(/_/g, ' ')}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Search Results</span>
              <strong>{searchResults.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="intel-list">
              {searchResults.map((result) => (
                <button
                  key={`${result.document_id}-${result.score}`}
                  className="intel-row"
                  onClick={() => onSelectDocument(result.document_id)}
                >
                  <strong>{result.title}</strong>
                  <span>{result.snippet}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Rescan Outcome</span>
              <strong>{rescanResults ? 'Live' : 'Idle'}</strong>
            </div>
            <ul className="plain-list">
              <li>Location used: {caseDetail.location_dossiers.find((location) => location.id === rescanResults?.location_id)?.label || selectedLocation?.label || 'none yet'}</li>
              <li>Focus used: {rescanResults?.focus || 'none yet'}</li>
              <li>Unlocked documents: {rescanResults?.unlocked_documents.join(', ') || 'none'}</li>
              <li>Unlocked suspects: {rescanResults?.unlocked_suspects.join(', ') || 'none'}</li>
              <li>Recent contexts: {rescanResults?.discovered_contexts.slice(-3).join(', ') || 'none yet'}</li>
            </ul>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Domain Reference</span>
              <strong>{caseDetail.archive_domains.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="domain-grid">
              {caseDetail.archive_domains.map((domain) => (
                <div key={domain.id} className="domain-badge">
                  <span>{domain.label}</span>
                  <small>{domain.summary || 'Dossier domain'}</small>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
