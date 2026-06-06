import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';
import { api } from './api';
import type {
  ArchiveDomain,
  AssetEntry,
  AuthoringBundle,
  CaseBriefInput,
  AuthoringCaseConfig,
  CaseIngestionInput,
  AuthoringSuspect,
  CaseDocument,
  CreateCaseRequest,
  LocationDossier,
  SourceGrounding,
} from './types';
import { MediaPlate, PanelHeader } from './ui';

type Props = {
  alias: string;
  currentCaseId: string;
  onPlayableCasesChanged: (caseId?: string) => Promise<void> | void;
  onSelectCase: (caseId: string) => void;
  onDeleteCase?: (caseId: string) => Promise<void>;
};

const emptyCreateForm: CreateCaseRequest = {
  id: '',
  title: '',
  hook: '',
  difficulty: 'medium',
  estimated_minutes: 45,
};

const briefTemplate = `Case Title
The Glass Harbor Affair

Premise
A civic fundraiser ends in disaster when a key organizer is found dead after the guests are dismissed.

Victim
Nadia Vance, the fundraiser chair and public face of the harbor redevelopment campaign.

Setting
A restored waterfront customs house used for private events, with an upstairs records room, a service corridor, and a sealed balcony door facing the marina.

Suspects
Name: Elias Mercer
Role: Finance director
Public Summary: Calm and meticulous, responsible for the event accounts.
Hidden Facts: He discovered a payment discrepancy hours before the death.
Secrets: He moved one ledger page before the police arrived.
Traits: controlled, image-conscious
Speaking Style: Precise and restrained.
Catchphrase: Stick to the record.
Verbal Tells: Repeats exact times when nervous.
Outward Goal: Protect the campaign from scandal.
Protective Target: the event accounts
Protective Reason: A financial scandal would destroy his position.

Name: Priya Sen
Role: Campaign strategist
Public Summary: Charismatic and persuasive, often smoothing over conflicts.
Hidden Facts: She arranged a private meeting between Nadia and an unnamed donor.
Secrets: She deleted one voice note after the meeting.
Traits: charming, strategic
Speaking Style: Smooth and confident.
Catchphrase: Context matters.
Verbal Tells: Answers accusations with observations.
Outward Goal: Keep control of the campaign narrative.
Protective Target: the donor meeting
Protective Reason: If exposed, it ties her directly to the final argument.

Relationships
- Elias and Priya were aligned publicly but privately disagreed about hidden campaign debts.
- Nadia had been preparing to expose an internal betrayal after the fundraiser.

Timeline
- Nadia receives an urgent note during the closing toast.
- Priya is seen near the staircase shortly afterward.
- Elias enters the records room corridor before security loses sight of him.
- The victim is found after the guests are cleared.

Evidence
Title: Event Ledger Extract
Summary: Partial ledger showing a handwritten correction near a donor payment.
Type: financial_record
Tags: ledger, donor payment, accounts
Hidden: no

Title: Deleted Voice Note Transcript
Summary: Recovered transcript of a short message referencing the balcony door.
Type: communications_log
Tags: voice note, balcony door, donor
Hidden: yes

Hidden Truth
- Nadia discovered that someone had redirected redevelopment funds.
- The private donor meeting turned into a confrontation over exposure and control.

Solution
Culprit: Priya Sen
Motive: Priya believed Nadia would destroy the campaign and her own career if the donor arrangement became public.
Summary: Priya used the private meeting to corner Nadia, then relied on the commotion of the event shutdown to hide what happened.`;

const emptyBriefForm: CaseBriefInput = {
  case_id: '',
  brief: briefTemplate,
  difficulty: 'medium',
  estimated_minutes: 45,
};

const sourceTemplate = `The Glass Harbor Affair

Nadia Vance, chair of the harbor redevelopment fundraiser, is found dead inside the restored customs house after the final guests are dismissed. The building has an upstairs records room, a service corridor, and a balcony door facing the marina.

Elias Mercer, the finance director, is calm and meticulous. He was responsible for the event accounts and discovered a payment discrepancy before Nadia died. Elias moved one ledger page before police arrived because he feared the campaign would collapse if the donor irregularity became public.

Priya Sen, the campaign strategist, is charismatic and persuasive. She arranged a private meeting between Nadia and an unnamed donor, then deleted one voice note after the meeting. Priya wants to keep control of the campaign narrative and avoids direct answers about the balcony door.

Nadia received an urgent note during the closing toast. Priya was seen near the staircase shortly afterward. Elias entered the records room corridor before security lost sight of him. The victim was found after the guests were cleared.

Evidence includes an event ledger extract with a handwritten correction near a donor payment, a recovered deleted voice note mentioning the balcony door, and security notes showing a gap near the service corridor.

Hidden truth: Nadia discovered that redevelopment funds had been redirected. Priya confronted Nadia during the private meeting because she feared Nadia would expose the donor arrangement and destroy her career.`;

const emptySourceForm: CaseIngestionInput = {
  case_id: '',
  source_text: sourceTemplate,
  difficulty: 'medium',
  estimated_minutes: 45,
  title_hint: '',
  focus_section: null,
};

const sourceRefinementSections = ['all', 'suspects', 'evidence', 'locations'] as const;

function mergeFocusedSourceBundle(
  current: AuthoringBundle,
  incoming: AuthoringBundle,
  focusSection: (typeof sourceRefinementSections)[number],
): AuthoringBundle {
  if (focusSection === 'all') return incoming;
  if (focusSection === 'suspects') {
    return {
      ...current,
      suspects: incoming.suspects,
      prompts: incoming.prompts,
      case: {
        ...current.case,
        start_state: {
          ...current.case.start_state,
          initial_suspect_ids: incoming.case.start_state.initial_suspect_ids,
        },
      },
    };
  }
  if (focusSection === 'evidence') {
    return {
      ...current,
      documents: incoming.documents,
      prompts: incoming.prompts,
      case: {
        ...current.case,
        start_state: {
          ...current.case.start_state,
          initial_document_ids: incoming.case.start_state.initial_document_ids,
        },
      },
    };
  }
  if (focusSection === 'locations') {
    return {
      ...current,
      prompts: incoming.prompts,
      case: {
        ...current.case,
        archive_domains: incoming.case.archive_domains,
        location_dossiers: incoming.case.location_dossiers,
        cover_image_path: incoming.case.cover_image_path,
        cover_image_url: incoming.case.cover_image_url,
      },
    };
  }
  return incoming;
}

const briefHeadings = [
  'Case Title',
  'Premise',
  'Victim',
  'Setting',
  'Suspects',
  'Relationships',
  'Timeline',
  'Evidence',
  'Hidden Truth',
  'Solution',
] as const;

function parseStructuredSections(text: string): Map<string, string> {
  const sections = new Map<string, string>();
  const headingPattern = new RegExp(`^(?<heading>${briefHeadings.map((heading) => heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\s*:?\\s*$`, 'gim');
  const matches = Array.from(text.matchAll(headingPattern));
  for (let index = 0; index < matches.length; index += 1) {
    const heading = matches[index].groups?.heading ?? '';
    const start = (matches[index].index ?? 0) + matches[index][0].length;
    const end = index + 1 < matches.length ? (matches[index + 1].index ?? text.length) : text.length;
    sections.set(heading, text.slice(start, end).trim());
  }
  return sections;
}

function mergeBriefWithRefinement(brief: string, refinementPrompt: string): string {
  const baseSections = parseStructuredSections(brief);
  if (!baseSections.size) {
    return `${brief.trim()}\n\n${refinementPrompt.trim()}`;
  }

  const refinementSections = parseStructuredSections(refinementPrompt);
  if (!refinementSections.size) {
    const inferredSections = new Map<string, string[]>();
    for (const line of refinementPrompt.split('\n').map((value) => value.trim()).filter(Boolean)) {
      const lower = line.toLowerCase();
      const assign = (section: string, value: string) => {
        const existing = inferredSections.get(section) ?? [];
        existing.push(value);
        inferredSections.set(section, existing);
      };
      if (lower.startsWith('suspect') || lower.startsWith('add suspect')) assign('Suspects', line.replace(/^add\s+/i, ''));
      else if (lower.startsWith('evidence') || lower.startsWith('add evidence')) assign('Evidence', line.replace(/^add\s+/i, ''));
      else if (lower.startsWith('location') || lower.startsWith('add location')) assign('Setting', line.replace(/^add\s+/i, ''));
      else if (lower.startsWith('timeline')) assign('Timeline', line);
      else if (lower.startsWith('relationship')) assign('Relationships', line);
      else if (lower.startsWith('hidden truth')) assign('Hidden Truth', line);
      else if (lower.startsWith('solution') || lower.startsWith('culprit') || lower.startsWith('motive')) assign('Solution', line);
      else assign('Premise', line);
    }
    inferredSections.forEach((lines, section) => {
      refinementSections.set(section, lines.join('\n'));
    });
  }

  for (const heading of briefHeadings) {
    const addition = refinementSections.get(heading);
    if (!addition) continue;
    const current = baseSections.get(heading) ?? '';
    baseSections.set(heading, [current, addition].filter(Boolean).join('\n\n').trim());
  }

  return briefHeadings
    .map((heading) => `${heading}\n${baseSections.get(heading) ?? ''}`.trim())
    .join('\n\n');
}

function cloneBundle(bundle: AuthoringBundle): AuthoringBundle {
  return JSON.parse(JSON.stringify(bundle)) as AuthoringBundle;
}

function toOptions(assets: AssetEntry[], kind: string) {
  return assets.filter((asset) => asset.kind === kind);
}

function AuthoringStudio({ alias, currentCaseId, onPlayableCasesChanged, onSelectCase, onDeleteCase }: Props) {
  const [bundles, setBundles] = useState<AuthoringBundle[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState(currentCaseId);
  const [draft, setDraft] = useState<AuthoringBundle | null>(null);
  const [createForm, setCreateForm] = useState<CreateCaseRequest>(emptyCreateForm);
  const [briefForm, setBriefForm] = useState<CaseBriefInput>(emptyBriefForm);
  const [sourceForm, setSourceForm] = useState<CaseIngestionInput>(emptySourceForm);
  const [importMode, setImportMode] = useState<'brief' | 'source'>('brief');
  const [uploadFolder, setUploadFolder] = useState('suspects');
  const [status, setStatus] = useState('');
  const [generationWarnings, setGenerationWarnings] = useState<string[]>([]);
  const [sourceGroundings, setSourceGroundings] = useState<SourceGrounding[]>([]);
  const [advancedRescanRules, setAdvancedRescanRules] = useState('[]');
  const [advancedBoardLinks, setAdvancedBoardLinks] = useState('[]');
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewPrompt, setReviewPrompt] = useState('');
  const [reviewRegenerating, setReviewRegenerating] = useState(false);
  const [lastGeneratedMode, setLastGeneratedMode] = useState<'brief' | 'source' | null>(null);
  const [reviewFocusSection, setReviewFocusSection] = useState<(typeof sourceRefinementSections)[number]>('all');

  useEffect(() => {
    void loadAuthoringCases();
  }, [alias]);

  useEffect(() => {
    if (currentCaseId) {
      setSelectedCaseId(currentCaseId);
    }
  }, [currentCaseId]);

  useEffect(() => {
    if (!selectedCaseId && bundles[0]) {
      setSelectedCaseId(bundles[0].case.id);
    }
  }, [bundles, selectedCaseId]);

  useEffect(() => {
    if (selectedCaseId) {
      void loadBundle(selectedCaseId);
    }
  }, [selectedCaseId, alias]);

  async function loadAuthoringCases() {
    const result = await api.listAuthoringCases(alias);
    setBundles(result);
  }

  async function loadBundle(caseId: string) {
    const bundle = await api.getAuthoringCase(caseId, alias);
    setDraft(bundle);
    setGenerationWarnings([]);
    setSourceGroundings([]);
    setReviewModalOpen(false);
    setAdvancedRescanRules(JSON.stringify(bundle.case.rescan_rules, null, 2));
    setAdvancedBoardLinks(JSON.stringify(bundle.case.valid_board_links, null, 2));
  }

  function updateDraft(next: AuthoringBundle) {
    setDraft(next);
  }

  function updateCase(mutator: (value: AuthoringCaseConfig) => void) {
    if (!draft) return;
    const next = cloneBundle(draft);
    mutator(next.case);
    updateDraft(next);
  }

  function updateSuspects(mutator: (suspects: AuthoringSuspect[]) => void) {
    if (!draft) return;
    const next = cloneBundle(draft);
    mutator(next.suspects);
    updateDraft(next);
  }

  function updateDocuments(mutator: (documents: CaseDocument[]) => void) {
    if (!draft) return;
    const next = cloneBundle(draft);
    mutator(next.documents);
    updateDraft(next);
  }

  function updateDomains(mutator: (domains: ArchiveDomain[]) => void) {
    if (!draft) return;
    const next = cloneBundle(draft);
    mutator(next.case.archive_domains);
    updateDraft(next);
  }

  function updateLocations(mutator: (locations: LocationDossier[]) => void) {
    if (!draft) return;
    const next = cloneBundle(draft);
    mutator(next.case.location_dossiers);
    updateDraft(next);
  }

  const suspectAssets = useMemo(() => toOptions(draft?.assets ?? [], 'suspects'), [draft]);
  const evidenceAssets = useMemo(() => toOptions(draft?.assets ?? [], 'evidence'), [draft]);
  const locationAssets = useMemo(() => toOptions(draft?.assets ?? [], 'locations'), [draft]);

  async function handleCreateCase(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await api.createAuthoringCase(alias, createForm);
      setStatus(`Created case ${created.case.title}.`);
      await loadAuthoringCases();
      setSelectedCaseId(created.case.id);
      await onPlayableCasesChanged(created.case.id);
      setCreateForm(emptyCreateForm);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  async function handleGenerateCase(event: FormEvent) {
    event.preventDefault();
    try {
      const generated = await api.generateAuthoringCase(alias, briefForm);
      setDraft(generated.bundle);
      setGenerationWarnings(generated.warnings);
      setSourceGroundings([]);
      setLastGeneratedMode('brief');
      setReviewPrompt('');
      setReviewModalOpen(true);
      setStatus(`Generated draft case ${generated.bundle.case.title}.`);
      await loadAuthoringCases();
      setSelectedCaseId(generated.bundle.case.id);
      await onPlayableCasesChanged(generated.bundle.case.id);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  async function handleIngestCase(event: FormEvent) {
    event.preventDefault();
    try {
      const generated = await api.ingestAuthoringCase(alias, sourceForm);
      setDraft(generated.bundle);
      setGenerationWarnings(generated.warnings);
      setSourceGroundings(generated.groundings);
      setLastGeneratedMode('source');
      setReviewFocusSection('all');
      setReviewPrompt('');
      setReviewModalOpen(true);
      setStatus(`Ingested draft case ${generated.bundle.case.title}.`);
      await loadAuthoringCases();
      setSelectedCaseId(generated.bundle.case.id);
      await onPlayableCasesChanged(generated.bundle.case.id);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  async function persistDraft(next: AuthoringBundle, notice: string) {
    try {
      next.case.rescan_rules = JSON.parse(advancedRescanRules);
      next.case.valid_board_links = JSON.parse(advancedBoardLinks);
      const saved = await api.saveAuthoringCase(next.case.id, alias, next);
      setDraft(saved);
      setGenerationWarnings([]);
      setStatus(notice.replace('{title}', saved.case.title));
      await loadAuthoringCases();
      await onPlayableCasesChanged(saved.case.id);
      return saved;
    } catch (error) {
      setStatus((error as Error).message);
      throw error;
    }
  }

  async function handleSave() {
    if (!draft) return;
    const next = cloneBundle(draft);
    try {
      await persistDraft(next, 'Saved {title}.');
    } catch {
      // persistDraft already updates the status message for the user.
    }
  }

  async function handleApproveCase() {
    if (!draft) return;
    try {
      const approved = await api.approveAuthoringCase(draft.case.id, alias);
      setDraft(approved);
      setStatus(`Approved ${approved.case.title}.`);
      await loadAuthoringCases();
      await onPlayableCasesChanged(approved.case.id);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  async function handleUploadAsset(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !draft) return;
    try {
      await uploadAssetToFolder(uploadFolder, file);
    } catch (error) {
      setStatus((error as Error).message);
    }
    event.target.value = '';
  }

  async function uploadAssetToFolder(folder: string, file: File) {
    if (!draft) return;
    const uploaded = await api.uploadAuthoringAsset(draft.case.id, alias, folder, file);
    setDraft((current) => (current ? { ...current, assets: [...current.assets, uploaded] } : current));
    setStatus(`Uploaded ${uploaded.path}.`);
  }

  async function handleReviewUpload(folder: string, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      await uploadAssetToFolder(folder, file);
    } catch (error) {
      setStatus((error as Error).message);
    }
    event.target.value = '';
  }

  async function handleRegenerateWithReviewPrompt() {
    if (!reviewPrompt.trim()) return;
    setReviewRegenerating(true);
    try {
      if (lastGeneratedMode === 'brief') {
        const mergedBrief = mergeBriefWithRefinement(briefForm.brief, reviewPrompt);
        const nextBriefForm = { ...briefForm, brief: mergedBrief };
        const generated = await api.generateAuthoringCase(alias, nextBriefForm);
        setBriefForm(nextBriefForm);
        setDraft(generated.bundle);
        setGenerationWarnings(generated.warnings);
        setSourceGroundings([]);
      } else {
        const mergedSource = `${sourceForm.source_text.trim()}\n\nRefinement Notes\n${reviewPrompt.trim()}`;
        const nextSourceForm = {
          ...sourceForm,
          source_text: mergedSource,
          focus_section: reviewFocusSection === 'all' ? null : reviewFocusSection,
        };
        const generated = await api.ingestAuthoringCase(alias, nextSourceForm);
        setSourceForm(nextSourceForm);
        setDraft((current) =>
          current ? mergeFocusedSourceBundle(current, generated.bundle, reviewFocusSection) : generated.bundle,
        );
        setGenerationWarnings(generated.warnings);
        setSourceGroundings(generated.groundings);
      }
      setStatus('Regenerated the draft with your structured follow-up notes.');
      setReviewPrompt('');
      await loadAuthoringCases();
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setReviewRegenerating(false);
    }
  }

  async function handleSendToReview() {
    if (!draft) return;
    const next = cloneBundle(draft);
    try {
      await persistDraft(next, 'Sent {title} to admin review. It remains private until approved.');
      setReviewModalOpen(false);
    } catch {
      // persistDraft already updates the status message for the user.
    }
  }

  async function handleDeleteCurrentDraft() {
    if (!draft || draft.case.status !== 'draft' || !onDeleteCase) return;
    try {
      await onDeleteCase(draft.case.id);
      setDraft(null);
      setSelectedCaseId('');
      setReviewModalOpen(false);
      setStatus(`Deleted draft ${draft.case.title}.`);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  return (
    <section className="dossier-surface authoring-surface">
      <PanelHeader
        eyebrow="Authoring Studio"
        title="Build and curate your own mystery files"
        subtitle="Edit case structure, drop assets into the case folders, and keep the dossier presentation coherent."
        actions={
          <div className="authoring-header-actions">
            {lastGeneratedMode && draft ? (
              <button className="dossier-button dossier-button-ghost" type="button" onClick={() => setReviewModalOpen(true)}>
                Review Extraction
              </button>
            ) : null}
            {draft?.case.status === 'draft' && onDeleteCase ? (
              <button className="dossier-button dossier-button-ghost" type="button" onClick={() => void handleDeleteCurrentDraft()}>
                Delete Draft
              </button>
            ) : null}
            {status ? <div className="status-chip">{status}</div> : null}
          </div>
        }
      />

      <div className="authoring-intro-grid">
        <form className="intel-card" onSubmit={handleCreateCase}>
          <div className="intel-card-header">
            <span>Create New Case</span>
            <strong>Scaffold</strong>
          </div>
          <label>
            Case ID (Optional)
            <input
              value={createForm.id}
              onChange={(event) => setCreateForm({ ...createForm, id: event.target.value })}
              placeholder="Auto-generate a unique draft ID"
            />
          </label>
          <label>
            Title
            <input value={createForm.title} onChange={(event) => setCreateForm({ ...createForm, title: event.target.value })} />
          </label>
          <label>
            Hook
            <textarea value={createForm.hook} onChange={(event) => setCreateForm({ ...createForm, hook: event.target.value })} />
          </label>
          <button className="dossier-button dossier-button-accent" type="submit">
            Create Case Scaffold
          </button>
        </form>

        <form className="intel-card" onSubmit={importMode === 'brief' ? handleGenerateCase : handleIngestCase}>
          <div className="intel-card-header">
            <span>{importMode === 'brief' ? 'Import From Case Brief' : 'Import From Raw Source'}</span>
            <strong>{importMode === 'brief' ? 'Draft Generator' : 'RAG Ingestion'}</strong>
          </div>
          <div className="prompt-chip-row">
            <button className={`prompt-chip ${importMode === 'brief' ? 'active' : ''}`} type="button" onClick={() => setImportMode('brief')}>
              Structured Brief
            </button>
            <button className={`prompt-chip ${importMode === 'source' ? 'active' : ''}`} type="button" onClick={() => setImportMode('source')}>
              Raw Source Packet
            </button>
          </div>
          {importMode === 'brief' ? (
            <>
              <label>
                Draft Case ID (Optional)
                <input
                  value={briefForm.case_id}
                  onChange={(event) => setBriefForm({ ...briefForm, case_id: event.target.value })}
                  placeholder="Leave blank to auto-generate"
                />
              </label>
              <label>
                Case Brief
                <textarea value={briefForm.brief} onChange={(event) => setBriefForm({ ...briefForm, brief: event.target.value })} rows={18} />
              </label>
              <div className="asset-folder-note">
                <strong>Required headings</strong>
                <span>`Case Title`, `Premise`, `Victim`, `Setting`, `Suspects`, `Relationships`, `Timeline`, `Evidence`, `Hidden Truth`, `Solution`</span>
              </div>
            </>
          ) : (
            <>
              <label>
                Draft Case ID (Optional)
                <input
                  value={sourceForm.case_id}
                  onChange={(event) => setSourceForm({ ...sourceForm, case_id: event.target.value })}
                  placeholder="Leave blank to auto-generate"
                />
              </label>
              <label>
                Optional Title Hint
                <input value={sourceForm.title_hint ?? ''} onChange={(event) => setSourceForm({ ...sourceForm, title_hint: event.target.value })} />
              </label>
              <label>
                Raw Source Packet
                <textarea
                  value={sourceForm.source_text}
                  onChange={(event) => setSourceForm({ ...sourceForm, source_text: event.target.value })}
                  rows={18}
                />
              </label>
              <div className="asset-folder-note">
                <strong>Paste-only v1</strong>
                <span>Use creator-authored story notes, bios, evidence notes, timelines, and solution details. The backend chunks, retrieves, extracts, and returns citations for review.</span>
              </div>
            </>
          )}
          <button className="dossier-button dossier-button-accent" type="submit">
            {importMode === 'brief' ? 'Generate Draft Case' : 'Ingest Source Into Draft'}
          </button>
        </form>

        <section className="intel-card">
          <div className="intel-card-header">
            <span>Current Cases</span>
            <strong>{bundles.length.toString().padStart(2, '0')}</strong>
          </div>
          <select value={selectedCaseId} onChange={(event) => setSelectedCaseId(event.target.value)}>
            <option value="">Select a case</option>
            {bundles.map((bundle) => (
              <option key={bundle.case.id} value={bundle.case.id}>
                {bundle.case.title}
              </option>
            ))}
          </select>
          <div className="asset-folder-note">
            <strong>Asset folders</strong>
            <span>`cases/&lt;case-id&gt;/assets/suspects/`</span>
            <span>`cases/&lt;case-id&gt;/assets/evidence/`</span>
            <span>`cases/&lt;case-id&gt;/assets/locations/`</span>
          </div>
        </section>
      </div>

      {draft ? (
        <>
          <div className="authoring-showcase-grid">
            <section className="parchment-viewer">
              <div className="document-toolbar">
                <span>Case Cover</span>
                <span>{draft.case.id}</span>
              </div>
              <div className="authoring-cover">
                <MediaPlate src={draft.case.cover_image_url} alt={draft.case.title} kind="cover" label="Case Cover" className="authoring-cover-media" />
                <div className="authoring-cover-copy">
                  <h3>{draft.case.title}</h3>
                  <p>{draft.case.hook}</p>
                  <p className="eyebrow">Status: {draft.case.status}</p>
                  <label>
                    Cover Image
                    <select
                      value={draft.case.cover_image_path ?? ''}
                      onChange={(event) => updateCase((value) => { value.cover_image_path = event.target.value || null; })}
                    >
                      <option value="">None</option>
                      {locationAssets.map((asset) => (
                        <option key={asset.path} value={asset.path}>
                          {asset.path}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Police Summary
                    <textarea value={draft.case.police_summary} onChange={(event) => updateCase((value) => { value.police_summary = event.target.value; })} />
                  </label>
                </div>
              </div>
            </section>

            <section className="intel-card">
              <div className="intel-card-header">
                <span>Asset Curator</span>
                <strong>{draft.assets.length.toString().padStart(2, '0')}</strong>
              </div>
              <label>
                Upload Bucket
                <select value={uploadFolder} onChange={(event) => setUploadFolder(event.target.value)}>
                  <option value="suspects">Suspects</option>
                  <option value="evidence">Evidence</option>
                  <option value="locations">Locations</option>
                </select>
              </label>
              <input type="file" accept="image/*,.svg" onChange={handleUploadAsset} />
              <div className="asset-gallery">
                {draft.assets.map((asset) => (
                  <div key={asset.path} className="asset-card">
                    <MediaPlate src={asset.url} alt={asset.path} kind={asset.kind === 'suspects' ? 'suspect' : asset.kind === 'locations' ? 'location' : 'evidence'} label={asset.kind} />
                    <strong>{asset.path}</strong>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Case Metadata</span>
              <strong>Overview</strong>
            </div>
            <div className="authoring-grid">
              <label className="editor-card">
                <span>Status</span>
                <input value={draft.case.status} readOnly />
              </label>
              <label className="editor-card">
                <span>Owner Alias</span>
                <input value={draft.case.owner_alias ?? ''} readOnly />
              </label>
              <label className="editor-card">
                <span>Title</span>
                <input value={draft.case.title} onChange={(event) => updateCase((value) => { value.title = event.target.value; })} />
              </label>
              <label className="editor-card">
                <span>Hook</span>
                <textarea value={draft.case.hook} onChange={(event) => updateCase((value) => { value.hook = event.target.value; })} />
              </label>
              <label className="editor-card">
                <span>Initial Questions</span>
                <textarea
                  value={draft.case.start_state.initial_open_questions.join('\n')}
                  onChange={(event) =>
                    updateCase((value) => {
                      value.start_state.initial_open_questions = event.target.value.split('\n').map((line) => line.trim()).filter(Boolean);
                    })
                  }
                />
              </label>
            </div>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Archive Domains</span>
              <strong>{draft.case.archive_domains.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="authoring-grid">
              {draft.case.archive_domains.map((domain, index) => (
                <div key={domain.id} className="editor-card">
                  <input value={domain.id} onChange={(event) => updateDomains((domains) => { domains[index].id = event.target.value; })} placeholder="domain id" />
                  <input value={domain.label} onChange={(event) => updateDomains((domains) => { domains[index].label = event.target.value; })} placeholder="domain label" />
                  <textarea value={domain.summary} onChange={(event) => updateDomains((domains) => { domains[index].summary = event.target.value; })} placeholder="domain summary" />
                  <select
                    value={domain.image_path ?? ''}
                    onChange={(event) => updateDomains((domains) => { domains[index].image_path = event.target.value || null; })}
                  >
                    <option value="">No image</option>
                    {locationAssets.concat(evidenceAssets).map((asset) => (
                      <option key={asset.path} value={asset.path}>
                        {asset.path}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <button
              className="dossier-button dossier-button-ghost"
              type="button"
              onClick={() =>
                updateDomains((domains) => {
                  domains.push({ id: `domain_${domains.length + 1}`, label: 'New Domain', summary: '', image_path: null, image_url: null });
                })
              }
            >
              Add Domain
            </button>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Location Dossiers</span>
              <strong>{draft.case.location_dossiers.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="authoring-grid">
              {draft.case.location_dossiers.map((location, index) => (
                <div key={location.id} className="editor-card">
                  <MediaPlate src={location.image_url} alt={location.label} kind="location" label="Location" />
                  <input value={location.id} onChange={(event) => updateLocations((locations) => { locations[index].id = event.target.value; })} placeholder="location id" />
                  <input value={location.label} onChange={(event) => updateLocations((locations) => { locations[index].label = event.target.value; })} placeholder="location label" />
                  <textarea value={location.summary} onChange={(event) => updateLocations((locations) => { locations[index].summary = event.target.value; })} placeholder="location summary" />
                  <label>
                    Linked Document IDs
                    <input
                      value={location.linked_document_ids.join(', ')}
                      onChange={(event) =>
                        updateLocations((locations) => {
                          locations[index].linked_document_ids = event.target.value.split(',').map((value) => value.trim()).filter(Boolean);
                        })
                      }
                    />
                  </label>
                  <select
                    value={location.image_path ?? ''}
                    onChange={(event) => updateLocations((locations) => { locations[index].image_path = event.target.value || null; })}
                  >
                    <option value="">No image</option>
                    {locationAssets.map((asset) => (
                      <option key={asset.path} value={asset.path}>
                        {asset.path}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <button
              className="dossier-button dossier-button-ghost"
              type="button"
              onClick={() =>
                updateLocations((locations) => {
                  locations.push({
                    id: `loc_${locations.length + 1}`,
                    label: 'New Location Dossier',
                    summary: '',
                    image_path: null,
                    image_url: null,
                    linked_document_ids: [],
                    unlock_rule: null,
                  });
                })
              }
            >
              Add Location Dossier
            </button>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Suspects</span>
              <strong>{draft.suspects.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="authoring-grid">
              {draft.suspects.map((suspect, index) => (
                <div key={suspect.id} className="editor-card">
                  <MediaPlate src={suspect.image_url} alt={suspect.display_name} kind="suspect" label={suspect.portrait_key ?? suspect.display_name.slice(0, 2)} />
                  <input value={suspect.id} onChange={(event) => updateSuspects((suspects) => { suspects[index].id = event.target.value; })} placeholder="suspect id" />
                  <input value={suspect.display_name} onChange={(event) => updateSuspects((suspects) => { suspects[index].display_name = event.target.value; })} placeholder="display name" />
                  <input value={suspect.public_profile.role} onChange={(event) => updateSuspects((suspects) => { suspects[index].public_profile.role = event.target.value; })} placeholder="role" />
                  <textarea value={suspect.public_profile.summary} onChange={(event) => updateSuspects((suspects) => { suspects[index].public_profile.summary = event.target.value; })} placeholder="public summary" />
                  <textarea
                    value={suspect.personality_profile.traits.join('\n')}
                    onChange={(event) =>
                      updateSuspects((suspects) => {
                        suspects[index].personality_profile.traits = event.target.value.split('\n').map((value) => value.trim()).filter(Boolean);
                      })
                    }
                    placeholder="personality traits"
                  />
                  <input
                    value={suspect.personality_profile.speaking_style}
                    onChange={(event) => updateSuspects((suspects) => { suspects[index].personality_profile.speaking_style = event.target.value; })}
                    placeholder="speaking style"
                  />
                  <input
                    value={suspect.personality_profile.catchphrase}
                    onChange={(event) => updateSuspects((suspects) => { suspects[index].personality_profile.catchphrase = event.target.value; })}
                    placeholder="catchphrase"
                  />
                  <textarea
                    value={suspect.personality_profile.verbal_tells.join('\n')}
                    onChange={(event) =>
                      updateSuspects((suspects) => {
                        suspects[index].personality_profile.verbal_tells = event.target.value.split('\n').map((value) => value.trim()).filter(Boolean);
                      })
                    }
                    placeholder="verbal tells"
                  />
                  <input
                    value={suspect.personality_profile.outward_goal}
                    onChange={(event) => updateSuspects((suspects) => { suspects[index].personality_profile.outward_goal = event.target.value; })}
                    placeholder="outward goal"
                  />
                  <input
                    value={suspect.personality_profile.protective_target}
                    onChange={(event) => updateSuspects((suspects) => { suspects[index].personality_profile.protective_target = event.target.value; })}
                    placeholder="protective target"
                  />
                  <textarea
                    value={suspect.personality_profile.protective_reason}
                    onChange={(event) => updateSuspects((suspects) => { suspects[index].personality_profile.protective_reason = event.target.value; })}
                    placeholder="protective reason"
                  />
                  <textarea
                    value={suspect.private_truth.facts_known.join('\n')}
                    onChange={(event) =>
                      updateSuspects((suspects) => {
                        suspects[index].private_truth.facts_known = event.target.value.split('\n').filter(Boolean);
                      })
                    }
                    placeholder="facts known"
                  />
                  <textarea
                    value={suspect.private_truth.secrets.join('\n')}
                    onChange={(event) =>
                      updateSuspects((suspects) => {
                        suspects[index].private_truth.secrets = event.target.value.split('\n').filter(Boolean);
                      })
                    }
                    placeholder="secrets"
                  />
                  <select
                    value={suspect.image_path ?? ''}
                    onChange={(event) => updateSuspects((suspects) => { suspects[index].image_path = event.target.value || null; })}
                  >
                    <option value="">No photo</option>
                    {suspectAssets.map((asset) => (
                      <option key={asset.path} value={asset.path}>
                        {asset.path}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <button
              className="dossier-button dossier-button-ghost"
              type="button"
              onClick={() =>
                updateSuspects((suspects) => {
                  suspects.push({
                    id: `sus_${suspects.length + 1}`,
                    display_name: 'New Suspect',
                    unlock_rule: null,
                    portrait_key: 'NS',
                    image_path: null,
                    image_url: null,
                    public_profile: { role: 'Role', summary: 'Public summary' },
                    personality_profile: {
                      traits: [],
                      speaking_style: 'Guarded and deliberate.',
                      catchphrase: '',
                      verbal_tells: [],
                      outward_goal: '',
                      protective_target: '',
                      protective_reason: '',
                    },
                    private_truth: { facts_known: [], secrets: [], non_negotiables: [] },
                    dialogue_rules: {
                      baseline_tone: 'guarded',
                      lie_strategy: 'evade until confronted',
                      pressure_triggers: [],
                      shut_down_threshold: 75,
                    },
                    memory_rules: {
                      remember_topics: true,
                      remember_confrontations: true,
                      remember_detective_tone: true,
                    },
                  });
                })
              }
            >
              Add Suspect
            </button>
          </section>

          <section className="intel-card">
            <div className="intel-card-header">
              <span>Evidence Documents</span>
              <strong>{draft.documents.length.toString().padStart(2, '0')}</strong>
            </div>
            <div className="authoring-grid">
              {draft.documents.map((document, index) => (
                <div key={document.id} className="editor-card editor-card-wide">
                  <MediaPlate src={document.image_url} alt={document.title} kind="evidence" label={document.id.toUpperCase()} />
                  <input value={document.id} onChange={(event) => updateDocuments((documents) => { documents[index].id = event.target.value; })} placeholder="document id" />
                  <input value={document.title} onChange={(event) => updateDocuments((documents) => { documents[index].title = event.target.value; })} placeholder="title" />
                  <div className="utility-bar compact">
                    <input value={document.folder} onChange={(event) => updateDocuments((documents) => { documents[index].folder = event.target.value; })} placeholder="folder" />
                    <input value={document.doc_type} onChange={(event) => updateDocuments((documents) => { documents[index].doc_type = event.target.value; })} placeholder="doc type" />
                  </div>
                  <textarea value={document.summary} onChange={(event) => updateDocuments((documents) => { documents[index].summary = event.target.value; })} placeholder="summary" />
                  <input
                    value={document.entity_tags.join(', ')}
                    onChange={(event) =>
                      updateDocuments((documents) => {
                        documents[index].entity_tags = event.target.value.split(',').map((value) => value.trim()).filter(Boolean);
                      })
                    }
                    placeholder="entity tags"
                  />
                  <select
                    value={document.image_path ?? ''}
                    onChange={(event) => updateDocuments((documents) => { documents[index].image_path = event.target.value || null; })}
                  >
                    <option value="">No image</option>
                    {evidenceAssets.concat(locationAssets).map((asset) => (
                      <option key={asset.path} value={asset.path}>
                        {asset.path}
                      </option>
                    ))}
                  </select>
                  <textarea value={document.body} onChange={(event) => updateDocuments((documents) => { documents[index].body = event.target.value; })} placeholder="document body" />
                </div>
              ))}
            </div>
            <button
              className="dossier-button dossier-button-ghost"
              type="button"
              onClick={() =>
                updateDocuments((documents) => {
                  documents.push({
                    id: `doc_${documents.length + 1}`,
                    case_id: draft.case.id,
                    title: 'New Evidence',
                    folder: draft.case.archive_domains[0]?.id ?? 'crime_scene',
                    doc_type: 'memo',
                    source_label: 'Authoring Studio',
                    summary: '',
                    body: '',
                    markdown_path: '',
                    entity_tags: [],
                    image_path: null,
                    image_url: null,
                    unlock_rule: null,
                  });
                })
              }
            >
              Add Evidence Document
            </button>
          </section>

          <div className="authoring-advanced-grid">
            <section className="intel-card">
              <div className="intel-card-header">
                <span>Prompt Sheets</span>
                <strong>{Object.keys(draft.prompts).length.toString().padStart(2, '0')}</strong>
              </div>
              {Object.entries(draft.prompts).map(([key, value]) => (
                <label key={key}>
                  {key}
                  <textarea
                    value={value}
                    onChange={(event) =>
                      updateDraft({
                        ...draft,
                        prompts: {
                          ...draft.prompts,
                          [key]: event.target.value,
                        },
                      })
                    }
                  />
                </label>
              ))}
            </section>

            <section className="intel-card">
              <div className="intel-card-header">
                <span>Advanced Rules</span>
                <strong>JSON</strong>
              </div>
              <label>
                Rescan Rules JSON
                <textarea value={advancedRescanRules} onChange={(event) => setAdvancedRescanRules(event.target.value)} />
              </label>
              <label>
                Valid Board Links JSON
                <textarea value={advancedBoardLinks} onChange={(event) => setAdvancedBoardLinks(event.target.value)} />
              </label>
            </section>
          </div>

          <div className="authoring-actions">
            <button className="dossier-button dossier-button-accent" type="button" onClick={handleSave}>
              Save Authoring Bundle
            </button>
            {draft.case.status !== 'approved' ? (
              <button className="dossier-button dossier-button-ghost" type="button" onClick={handleApproveCase}>
                Approve Case
              </button>
            ) : null}
          </div>
          {generationWarnings.length ? (
            <section className="intel-card">
              <div className="intel-card-header">
                <span>Generation Warnings</span>
                <strong>{generationWarnings.length.toString().padStart(2, '0')}</strong>
              </div>
              <ul className="plain-list">
                {generationWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {sourceGroundings.length ? (
            <section className="intel-card">
              <div className="intel-card-header">
                <span>Source Grounding</span>
                <strong>{sourceGroundings.length.toString().padStart(2, '0')}</strong>
              </div>
              <div className="intel-list">
                {sourceGroundings.map((grounding) => (
                  <div key={grounding.generated_field} className="intel-row">
                    <strong>{grounding.generated_field.replace(/_/g, ' ')}</strong>
                    <span>{grounding.method} / {grounding.confidence}</span>
                    <span>{grounding.supporting_chunk_ids.join(', ')}</span>
                    <span>{grounding.generated_value || grounding.preview}</span>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : (
        <div className="intel-card">
          <p>Select or create a case to open the authoring studio.</p>
        </div>
      )}
      {reviewModalOpen && draft ? (
        <div className="modal-backdrop" onClick={() => setReviewModalOpen(false)}>
          <section
            className="media-modal review-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Generated draft review"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="document-toolbar">
              <span>Generated Draft Review</span>
              <button className="icon-button modal-close" type="button" onClick={() => setReviewModalOpen(false)}>
                Close
              </button>
            </div>
            <div className="review-modal-body">
              <section className="intel-card review-visual-assignment">
                <div className="intel-card-header">
                  <span>Detected Structure</span>
                  <strong>{draft.case.status}</strong>
                </div>
                <div className="review-summary-grid">
                  <div className="editor-card">
                    <strong>Case</strong>
                    <span>{draft.case.title}</span>
                    <span>{draft.case.hook}</span>
                  </div>
                  <div className="editor-card">
                    <strong>Suspects</strong>
                    <span>{draft.suspects.length}</span>
                    <span>{draft.suspects.map((suspect) => suspect.display_name).join(', ') || 'None detected'}</span>
                  </div>
                  <div className="editor-card">
                    <strong>Evidence</strong>
                    <span>{draft.documents.length}</span>
                    <span>{draft.documents.slice(0, 4).map((document) => document.title).join(', ') || 'None detected'}</span>
                  </div>
                  <div className="editor-card">
                    <strong>Locations</strong>
                    <span>{draft.case.location_dossiers.length}</span>
                    <span>{draft.case.location_dossiers.map((location) => location.label).join(', ') || 'None detected'}</span>
                  </div>
                </div>
                {generationWarnings.length ? (
                  <div className="asset-folder-note">
                    <strong>Warnings</strong>
                    <span>{generationWarnings.join(' | ')}</span>
                  </div>
                ) : null}
                {sourceGroundings.length ? (
                  <div className="intel-list">
                    {sourceGroundings.slice(0, 6).map((grounding) => (
                      <div key={grounding.generated_field} className="intel-row">
                        <strong>{grounding.generated_field.replace(/_/g, ' ')}</strong>
                        <span>{grounding.method} / {grounding.confidence}</span>
                        <span>{grounding.supporting_chunk_ids.join(', ')}</span>
                        <span>{grounding.generated_value || grounding.preview}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>

              <section className="intel-card">
                <div className="intel-card-header">
                  <span>Refine Missing Details</span>
                  <strong>{reviewRegenerating ? 'Running' : 'Optional'}</strong>
                </div>
                <label>
                  Structured Follow-up Prompt
                  <textarea
                    value={reviewPrompt}
                    onChange={(event) => setReviewPrompt(event.target.value)}
                    rows={8}
                    placeholder={
                      importMode === 'brief'
                        ? 'Use headings when possible, for example:\nSuspects\nName: Vera Cole\nRole: Hotel Manager\nPublic Summary: ...\n\nEvidence\nTitle: Service Key Log\nSummary: ...'
                        : 'Describe what is missing more structurally, for example:\nAdd suspect: Vera Cole, hotel manager hiding access logs.\nAdd location: Harbor Office, records annex behind the reception wall.\nAdd evidence: Service Key Log showing after-hours access.'
                    }
                  />
                </label>
                <div className="asset-folder-note">
                  <strong>How this works</strong>
                  <span>
                    Use this when the auto-detected suspects, evidence, or locations are incomplete. We will regenerate the same draft using your follow-up note and keep the case private.
                  </span>
                </div>
                {lastGeneratedMode === 'source' ? (
                  <label>
                    Regenerate Section
                    <select
                      value={reviewFocusSection}
                      onChange={(event) => setReviewFocusSection(event.target.value as (typeof sourceRefinementSections)[number])}
                    >
                      <option value="all">All extracted sections</option>
                      <option value="suspects">Suspects only</option>
                      <option value="evidence">Evidence only</option>
                      <option value="locations">Locations only</option>
                    </select>
                  </label>
                ) : null}
                <button
                  className="dossier-button dossier-button-accent"
                  type="button"
                  disabled={!reviewPrompt.trim() || reviewRegenerating}
                  onClick={handleRegenerateWithReviewPrompt}
                >
                  {reviewRegenerating ? 'Regenerating...' : 'Regenerate With Notes'}
                </button>
              </section>

              <section className="intel-card review-visual-assignment">
                <div className="intel-card-header">
                  <span>Quick Visual Assignment</span>
                  <strong>{draft.assets.length.toString().padStart(2, '0')}</strong>
                </div>
                <div className="review-visual-scroll">
                  <div className="review-asset-upload-row">
                    <label className="dossier-button dossier-button-ghost">
                      Upload Suspect Image
                      <input type="file" accept="image/*,.svg" hidden onChange={(event) => void handleReviewUpload('suspects', event)} />
                    </label>
                    <label className="dossier-button dossier-button-ghost">
                      Upload Evidence Image
                      <input type="file" accept="image/*,.svg" hidden onChange={(event) => void handleReviewUpload('evidence', event)} />
                    </label>
                    <label className="dossier-button dossier-button-ghost">
                      Upload Location Image
                      <input type="file" accept="image/*,.svg" hidden onChange={(event) => void handleReviewUpload('locations', event)} />
                    </label>
                  </div>
                  <div className="authoring-grid">
                    {draft.suspects.map((suspect, index) => (
                      <div key={`review-suspect-${suspect.id}`} className="editor-card">
                        <MediaPlate src={suspect.image_url} alt={suspect.display_name} kind="suspect" label={suspect.portrait_key ?? suspect.display_name.slice(0, 2)} />
                        <strong>{suspect.display_name}</strong>
                        <select
                          value={suspect.image_path ?? ''}
                          onChange={(event) => updateSuspects((suspects) => { suspects[index].image_path = event.target.value || null; })}
                        >
                          <option value="">Default / None</option>
                          {suspectAssets.map((asset) => (
                            <option key={asset.path} value={asset.path}>
                              {asset.path}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                    {draft.documents.slice(0, 6).map((document, index) => (
                      <div key={`review-document-${document.id}`} className="editor-card">
                        <MediaPlate src={document.image_url} alt={document.title} kind="evidence" label={document.id.toUpperCase()} />
                        <strong>{document.title}</strong>
                        <select
                          value={document.image_path ?? ''}
                          onChange={(event) => updateDocuments((documents) => { documents[index].image_path = event.target.value || null; })}
                        >
                          <option value="">Default / None</option>
                          {evidenceAssets.concat(locationAssets).map((asset) => (
                            <option key={asset.path} value={asset.path}>
                              {asset.path}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                    {draft.case.location_dossiers.map((location, index) => (
                      <div key={`review-location-${location.id}`} className="editor-card">
                        <MediaPlate src={location.image_url} alt={location.label} kind="location" label="Location" />
                        <strong>{location.label}</strong>
                        <select
                          value={location.image_path ?? ''}
                          onChange={(event) => updateLocations((locations) => { locations[index].image_path = event.target.value || null; })}
                        >
                          <option value="">Default / None</option>
                          {locationAssets.map((asset) => (
                            <option key={asset.path} value={asset.path}>
                              {asset.path}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <div className="authoring-actions review-actions">
                <button className="dossier-button dossier-button-ghost" type="button" onClick={() => setReviewModalOpen(false)}>
                  Continue Editing
                </button>
                <button className="dossier-button dossier-button-accent" type="button" onClick={() => void handleSendToReview()}>
                  Send Draft To Review
                </button>
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}

export default AuthoringStudio;
