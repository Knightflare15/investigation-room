import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';
import { api } from './api';
import type {
  ArchiveDomain,
  AssetEntry,
  AuthoringBundle,
  AuthoringCaseConfig,
  AuthoringSuspect,
  CaseDocument,
  CreateCaseRequest,
  LocationDossier,
} from './types';
import { MediaPlate, PanelHeader } from './ui';

type Props = {
  alias: string;
  currentCaseId: string;
  onPlayableCasesChanged: (caseId?: string) => Promise<void> | void;
  onSelectCase: (caseId: string) => void;
};

const emptyCreateForm: CreateCaseRequest = {
  id: '',
  title: '',
  hook: '',
  difficulty: 'medium',
  estimated_minutes: 45,
};

function cloneBundle(bundle: AuthoringBundle): AuthoringBundle {
  return JSON.parse(JSON.stringify(bundle)) as AuthoringBundle;
}

function toOptions(assets: AssetEntry[], kind: string) {
  return assets.filter((asset) => asset.kind === kind);
}

function AuthoringStudio({ alias, currentCaseId, onPlayableCasesChanged, onSelectCase }: Props) {
  const [bundles, setBundles] = useState<AuthoringBundle[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState(currentCaseId);
  const [draft, setDraft] = useState<AuthoringBundle | null>(null);
  const [createForm, setCreateForm] = useState<CreateCaseRequest>(emptyCreateForm);
  const [uploadFolder, setUploadFolder] = useState('suspects');
  const [status, setStatus] = useState('');
  const [advancedRescanRules, setAdvancedRescanRules] = useState('[]');
  const [advancedBoardLinks, setAdvancedBoardLinks] = useState('[]');

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
      onSelectCase(created.case.id);
      await onPlayableCasesChanged(created.case.id);
      setCreateForm(emptyCreateForm);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  async function handleSave() {
    if (!draft) return;
    try {
      const next = cloneBundle(draft);
      next.case.rescan_rules = JSON.parse(advancedRescanRules);
      next.case.valid_board_links = JSON.parse(advancedBoardLinks);
      const saved = await api.saveAuthoringCase(next.case.id, alias, next);
      setDraft(saved);
      setStatus(`Saved ${saved.case.title}.`);
      await loadAuthoringCases();
      onSelectCase(saved.case.id);
      await onPlayableCasesChanged(saved.case.id);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  async function handleUploadAsset(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !draft) return;
    try {
      const uploaded = await api.uploadAuthoringAsset(draft.case.id, alias, uploadFolder, file);
      setDraft((current) => (current ? { ...current, assets: [...current.assets, uploaded] } : current));
      setStatus(`Uploaded ${uploaded.path}.`);
    } catch (error) {
      setStatus((error as Error).message);
    }
    event.target.value = '';
  }

  return (
    <section className="dossier-surface authoring-surface">
      <PanelHeader
        eyebrow="Authoring Studio"
        title="Build and curate your own mystery files"
        subtitle="Edit case structure, drop assets into the case folders, and keep the dossier presentation coherent."
        actions={status ? <div className="status-chip">{status}</div> : null}
      />

      <div className="authoring-intro-grid">
        <form className="intel-card" onSubmit={handleCreateCase}>
          <div className="intel-card-header">
            <span>Create New Case</span>
            <strong>Scaffold</strong>
          </div>
          <label>
            Case ID
            <input value={createForm.id} onChange={(event) => setCreateForm({ ...createForm, id: event.target.value })} />
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
          </div>
        </>
      ) : (
        <div className="intel-card">
          <p>Select or create a case to open the authoring studio.</p>
        </div>
      )}
    </section>
  );
}

export default AuthoringStudio;
