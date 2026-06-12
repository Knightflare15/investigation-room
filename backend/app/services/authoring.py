from __future__ import annotations

import json
import re
import shutil
from functools import lru_cache
from pathlib import Path

import yaml

from ..case_loader import list_case_assets, load_authoring_bundle
from ..config import settings
from ..database import create_database
from ..models import (
    ArchiveDomain,
    AssetEntry,
    AuthoringBundle,
    CaseBriefInput,
    CaseIngestionInput,
    CaseIngestionResponse,
    CaseConfig,
    CaseDocument,
    CanonicalTruth,
    CreateCaseRequest,
    GenerateCaseDraftResponse,
    LocationDossier,
    StartState,
    SubmissionConfig,
    SuspectConfig,
)
from .brief_generator import BriefGenerationService
from .source_ingestion import SourceIngestionService
from .storage import AssetStorage
from .retrieval import RetrievalService


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def _valid_image_signature(content: bytes, content_type: str) -> bool:
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


class AuthoringService:
    def __init__(self, cases_root: Path) -> None:
        self.cases_root = cases_root
        self.cases_root.mkdir(parents=True, exist_ok=True)
        self.generator = BriefGenerationService()
        self.source_ingestion = SourceIngestionService(settings)
        try:
            uses_configured_root = cases_root.resolve() == settings.cases_path.resolve()
        except FileNotFoundError:
            uses_configured_root = cases_root == settings.cases_path
        self.db = create_database(
            settings.database_url if uses_configured_root else None,
            settings.db_path if uses_configured_root else cases_root / ".authoring.db",
        )
        self.storage = AssetStorage(settings, cases_root)
        self.retrieval = RetrievalService(settings)

    def case_dir(self, case_id: str) -> Path:
        return self.cases_root / case_id

    def _requested_case_id(self, requested_id: str | None) -> str | None:
        if requested_id is None:
            return None
        normalized = _slugify(requested_id.strip())
        return normalized if requested_id.strip() else None

    def _allocate_draft_case_id(self, title_hint: str) -> str:
        base_slug = _slugify(title_hint.strip())[:48] if title_hint.strip() else "case"
        candidate = f"draft-{base_slug}"
        suffix = 2
        while self.case_dir(candidate).exists() or self.db.load_case_bundle(candidate) is not None:
            candidate = f"draft-{base_slug}-{suffix}"
            suffix += 1
        return candidate

    def _resolve_case_id(self, requested_id: str | None, title_hint: str) -> str:
        return self._requested_case_id(requested_id) or self._allocate_draft_case_id(title_hint)

    def is_admin(self, alias: str) -> bool:
        return alias in (settings.bootstrap_admin_aliases or settings.admin_aliases)

    def _can_access_case(self, case_id: str, alias: str) -> bool:
        bundle = self._load_stored_bundle(case_id)
        return bundle.case.status == "approved" or bundle.case.owner_alias == alias or self.is_admin(alias)

    def _load_stored_bundle(self, case_id: str) -> AuthoringBundle:
        stored = self.db.load_case_bundle(case_id)
        if stored is not None:
            return stored
        return load_authoring_bundle(self.case_dir(case_id))

    def _prepare_generated_case_dir(self, case_id: str, actor_alias: str) -> Path:
        case_dir = self.case_dir(case_id)
        stored = self.db.load_case_bundle(case_id)
        if case_dir.exists() or stored is not None:
            bundle = stored or load_authoring_bundle(case_dir)
            if bundle.case.status == "approved":
                raise ValueError(f"Case '{case_id}' is already approved and cannot be regenerated in place")
            if not (self.is_admin(actor_alias) or bundle.case.owner_alias == actor_alias):
                raise ValueError("You do not have permission to regenerate this draft case")
        else:
            (case_dir / "archive").mkdir(parents=True, exist_ok=True)
            (case_dir / "prompts").mkdir(parents=True, exist_ok=True)
        self._ensure_template_assets(case_dir)
        return case_dir

    def create_case(self, payload: CreateCaseRequest, owner_alias: str, owner_user_id: str | None = None) -> AuthoringBundle:
        self._enforce_draft_quota(owner_alias)
        case_id = self._resolve_case_id(payload.id, payload.title)
        case_dir = self.case_dir(case_id)
        if case_dir.exists() or self.db.load_case_bundle(case_id) is not None:
            raise ValueError(f"Case '{case_id}' already exists")

        (case_dir / "archive").mkdir(parents=True, exist_ok=True)
        (case_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (case_dir / "assets" / "suspects").mkdir(parents=True, exist_ok=True)
        (case_dir / "assets" / "evidence").mkdir(parents=True, exist_ok=True)
        (case_dir / "assets" / "locations").mkdir(parents=True, exist_ok=True)

        case_config = CaseConfig(
            id=case_id,
            title=payload.title,
            hook=payload.hook,
            difficulty=payload.difficulty,
            estimated_minutes=payload.estimated_minutes,
            version=1,
            status="draft",
            owner_alias=owner_alias,
            owner_user_id=owner_user_id,
            police_summary="Replace this with the police first-pass intake for your mystery.",
            cover_image_path="locations/template-cover.svg",
            start_state=StartState(
                initial_suspect_ids=["sus_primary"],
                initial_document_ids=["doc_incident"],
                initial_open_questions=[
                    "Who benefits from the victim's silence?",
                    "What detail did the first investigation dismiss too early?",
                ],
            ),
            archive_domains=[
                ArchiveDomain(id="crime_scene", label="Crime Scene Packet", summary="Primary incident reports and observations."),
                ArchiveDomain(id="communications", label="Communications", summary="Calls, messages, and notes."),
            ],
            location_dossiers=[
                LocationDossier(
                    id="loc_primary",
                    label="Primary Scene",
                    summary="A dossier for the central location tied to the mystery.",
                    linked_document_ids=["doc_incident"],
                )
            ],
            submission=SubmissionConfig(
                required_fields=["culprit_id", "motive_text", "timeline_text", "evidence_ids"],
                min_evidence_count=2,
                canonical_truth=CanonicalTruth(
                    culprit_id="sus_primary",
                    motive_summary="Replace with the culprit's canonical motive.",
                    timeline_summary="Replace with the canonical sequence of events.",
                    motive_concepts=["replace canonical motive"],
                    timeline_concepts=["replace canonical timeline"],
                    evidence_ids=["doc_incident"],
                ),
            ),
        )

        suspect = SuspectConfig.model_validate(
            {
                "id": "sus_primary",
                "display_name": "Primary Suspect",
                "unlock_rule": None,
                "portrait_key": "PS",
                "image_path": "suspects/template-suspect.svg",
                "public_profile": {
                    "role": "Replace role",
                    "summary": "Replace with a short public description.",
                },
                "personality_profile": {
                    "traits": ["Replace with a personality trait."],
                    "speaking_style": "Measured, guarded, and deliberate.",
                    "catchphrase": "Let's stay precise.",
                    "verbal_tells": ["Avoids direct blame when under pressure."],
                    "outward_goal": "Protect their public image.",
                    "protective_target": "",
                    "protective_reason": "",
                },
                "private_truth": {
                    "facts_known": ["Replace with a fact the suspect truly knows."],
                    "secrets": ["Replace with a secret the suspect is hiding."],
                    "non_negotiables": ["Replace with a hard truth the model must never violate."],
                },
                "dialogue_rules": {
                    "baseline_tone": "composed",
                    "lie_strategy": "deflect until pressed with strong evidence",
                    "pressure_triggers": ["timeline", "motive"],
                    "fact_reveal_rules": [
                        {
                            "fact_id": "fact_0",
                            "topics": ["timeline"],
                            "evidence_ids": [],
                            "min_trust": 40,
                            "max_guardedness": 80,
                        },
                        {
                            "fact_id": "fact_1",
                            "topics": ["motive"],
                            "evidence_ids": [],
                            "min_trust": 50,
                            "max_guardedness": 65,
                        },
                    ],
                    "shut_down_threshold": 75,
                },
                "memory_rules": {
                    "remember_topics": True,
                    "remember_confrontations": True,
                    "remember_detective_tone": True,
                },
            }
        )

        document = CaseDocument(
            id="doc_incident",
            case_id=case_id,
            title="Incident Summary",
            folder="crime_scene",
            doc_type="police_report",
            source_label="Police First-Pass File",
            summary="Replace with the initial incident summary.",
            body="Replace this document body with the first authored evidence file for your mystery.",
            markdown_path=f"cases/{case_id}/archive/doc-001-incident-summary.md",
            entity_tags=["victim", "timeline"],
            image_path="evidence/template-evidence.svg",
        )

        prompts = {
            "interrogation_system": (
                "You are participating in a detective mystery simulation. "
                "Speak only as the suspect described in the payload and stay faithful to the authored truth."
            ),
            "hint_system": (
                "Point the detective toward overlooked evidence or contradictions without naming the culprit."
            ),
        }

        bundle = AuthoringBundle(case=case_config, suspects=[suspect], documents=[document], prompts=prompts, assets=[])
        self.save_bundle(case_id, bundle, owner_alias)
        self.db.write_audit_log(owner_alias, "case.created", case_id)
        return self.load_bundle(case_id, owner_alias)

    def load_bundle(self, case_id: str, alias: str) -> AuthoringBundle:
        if not self._can_access_case(case_id, alias):
            raise ValueError("You do not have access to this draft case")
        bundle = self._load_stored_bundle(case_id)
        known_paths = {asset.path for asset in bundle.assets}
        for asset in list_case_assets(self.case_dir(case_id), case_id):
            if asset.path not in known_paths:
                bundle.assets.append(asset)
                known_paths.add(asset.path)
        for row in self.db.list_case_assets(case_id):
            if row["path"] not in known_paths:
                bundle.assets.append(
                    AssetEntry(
                        path=row["path"],
                        url=row["public_url"],
                        kind=row["path"].split("/", 1)[0],
                    )
                )
        return bundle

    def list_bundles(self, alias: str) -> list[AuthoringBundle]:
        bundles_by_id = {bundle.case.id: bundle for bundle in self.db.list_case_bundles()}
        for case_dir in sorted(path for path in self.cases_root.iterdir() if path.is_dir()):
            bundle = load_authoring_bundle(case_dir)
            bundles_by_id.setdefault(bundle.case.id, bundle)
        return [
            bundle
            for bundle in bundles_by_id.values()
            if bundle.case.status == "approved" or bundle.case.owner_alias == alias or self.is_admin(alias)
        ]

    def save_bundle(self, case_id: str, bundle: AuthoringBundle, actor_alias: str) -> AuthoringBundle:
        case_dir = self.case_dir(case_id)
        stored = self.db.load_case_bundle(case_id)
        if not case_dir.exists() and stored is None:
            raise ValueError(f"Case '{case_id}' does not exist")
        case_dir.mkdir(parents=True, exist_ok=True)
        if bundle.case.id != case_id:
            raise ValueError("Case ID in bundle must match the URL case ID")
        archive_dir = case_dir / "archive"
        prompts_dir = case_dir / "prompts"
        archive_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_template_assets(case_dir)

        existing = stored or (load_authoring_bundle(case_dir) if (case_dir / "case.json").exists() else None)
        owner_alias = (existing.case.owner_alias if existing else None) or actor_alias
        if existing and not (self.is_admin(actor_alias) or owner_alias == actor_alias):
            raise ValueError("You do not have permission to edit this case")
        if existing and bundle.case.version != existing.case.version:
            raise ValueError("This draft changed since it was loaded. Reload it before saving.")
        if existing:
            bundle.case.version += 1
        if not self.is_admin(actor_alias):
            bundle.case.status = "draft"
            bundle.case.owner_alias = owner_alias
        elif not bundle.case.owner_alias:
            bundle.case.owner_alias = owner_alias

        case_json = bundle.case.model_dump(mode="json", exclude={"cover_image_url"})
        case_json["archive_domains"] = [
            domain.model_dump(mode="json", exclude={"image_url"})
            for domain in bundle.case.archive_domains
        ]
        case_json["location_dossiers"] = [
            dossier.model_dump(mode="json", exclude={"image_url"})
            for dossier in bundle.case.location_dossiers
        ]
        (case_dir / "case.json").write_text(json.dumps(case_json, indent=2), encoding="utf-8")

        suspects_json = {
            "suspects": [
                suspect.model_dump(mode="json", exclude={"image_url"})
                for suspect in bundle.suspects
            ]
        }
        (case_dir / "suspects.json").write_text(json.dumps(suspects_json, indent=2), encoding="utf-8")

        for path in archive_dir.glob("*.md"):
            path.unlink()

        for index, document in enumerate(bundle.documents, start=1):
            slug = _slugify(document.title)
            filename = f"doc-{index:03d}-{slug}.md"
            front_matter = {
                "id": document.id,
                "title": document.title,
                "doc_type": document.doc_type,
                "folder": document.folder,
                "source_label": document.source_label,
                "unlock_rule": document.unlock_rule,
                "entity_tags": document.entity_tags,
                "summary": document.summary,
                "image_path": document.image_path,
            }
            body = (
                "---\n"
                f"{yaml.safe_dump(front_matter, sort_keys=False).strip()}\n"
                "---\n\n"
                f"{document.body.strip()}\n"
            )
            (archive_dir / filename).write_text(body, encoding="utf-8")

        for path in prompts_dir.glob("*.txt"):
            path.unlink()
        for name, content in bundle.prompts.items():
            if not re.fullmatch(r"[a-z0-9_-]{1,64}", name):
                raise ValueError(f"Unsafe prompt name: {name}")
            (prompts_dir / f"{name}.txt").write_text(content.strip() + "\n", encoding="utf-8")

        saved = load_authoring_bundle(case_dir)
        self.db.save_case_bundle(saved)
        if self.db.supports_vector_index:
            indexed_chunks = []
            for chunk in self.retrieval.build_chunks(saved.documents):
                indexed_chunks.append(
                    (
                        chunk.chunk_id,
                        chunk.document.id,
                        chunk.chunk_id.split(":")[-2],
                        chunk.text,
                        self.retrieval.ollama.embed(chunk.text),
                    )
                )
            self.db.replace_retrieval_chunks(saved.case.id, saved.case.version, indexed_chunks)
        self.db.write_audit_log(actor_alias, "case.saved", case_id, {"version": saved.case.version})
        return self.load_bundle(case_id, actor_alias)

    def save_asset(
        self,
        case_id: str,
        folder: str,
        filename: str,
        content: bytes,
        actor_alias: str,
        content_type: str | None = None,
    ) -> AssetEntry:
        case_dir = self.case_dir(case_id)
        if not case_dir.exists() and self.db.load_case_bundle(case_id) is None:
            raise ValueError(f"Case '{case_id}' does not exist")
        case_dir.mkdir(parents=True, exist_ok=True)
        bundle = self._load_stored_bundle(case_id)
        if not (self.is_admin(actor_alias) or bundle.case.owner_alias == actor_alias):
            raise ValueError("You do not have permission to upload assets for this case")

        allowed_types = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        extension = Path(filename).suffix.lower()
        inferred_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(extension)
        effective_type = content_type or inferred_type
        if effective_type not in allowed_types or extension not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Only PNG, JPEG, and WebP images are allowed")
        if not _valid_image_signature(content, effective_type):
            raise ValueError("Uploaded image content does not match its declared type")
        if len(content) > settings.max_upload_bytes:
            raise ValueError("Upload exceeds the configured per-file limit")
        current_bytes = sum(path.stat().st_size for path in (case_dir / "assets").rglob("*") if path.is_file())
        if self.storage.uses_r2:
            current_bytes += sum(int(row["size_bytes"]) for row in self.db.list_case_assets(case_id))
        if current_bytes + len(content) > settings.max_draft_asset_bytes:
            raise ValueError("Draft asset storage quota exceeded")

        safe_folder = _slugify(folder).replace("-", "_")
        safe_name = f"{_slugify(Path(filename).stem)}{extension}"
        relative_path = Path(safe_folder) / safe_name
        url = self.storage.put(case_id, relative_path, content, effective_type)
        if self.storage.uses_r2:
            self.db.save_case_asset(case_id, relative_path.as_posix(), url, effective_type, len(content))
        self.db.write_audit_log(actor_alias, "asset.uploaded", case_id, {"path": relative_path.as_posix()})
        return AssetEntry(
            path=relative_path.as_posix(),
            url=url,
            kind=safe_folder,
        )

    def generate_case_from_brief(self, payload: CaseBriefInput, owner_alias: str, owner_user_id: str | None = None) -> GenerateCaseDraftResponse:
        self._enforce_draft_quota(owner_alias)
        parsed = self.generator.parse_brief(payload)
        extracted = self.generator.extract_case_draft(parsed)
        case_id = self._requested_case_id(payload.case_id) or self._allocate_draft_case_id(extracted.title)
        extracted.case_id = case_id
        bundle = self.generator.generate_bundle(extracted, owner_alias, payload.difficulty, payload.estimated_minutes)
        bundle.case.owner_user_id = owner_user_id
        self._prepare_generated_case_dir(case_id, owner_alias)
        saved = self.save_bundle(case_id, bundle, owner_alias)
        self.db.write_audit_log(owner_alias, "case.generated", case_id, {"source": "brief"})
        return GenerateCaseDraftResponse(bundle=saved, warnings=extracted.warnings)

    def ingest_case_from_source(self, payload: CaseIngestionInput, owner_alias: str, owner_user_id: str | None = None) -> CaseIngestionResponse:
        self._enforce_draft_quota(owner_alias)
        extracted, groundings = self.source_ingestion.extract(payload)
        case_id = self._requested_case_id(payload.case_id) or self._allocate_draft_case_id(extracted.title)
        extracted.case_id = case_id
        bundle = self.generator.generate_bundle(extracted, owner_alias, payload.difficulty, payload.estimated_minutes)
        bundle.case.owner_user_id = owner_user_id
        grounding_notes = "\n".join(
            f"- {grounding.generated_field} [{grounding.method}/{grounding.confidence}]: {grounding.generated_value} | {', '.join(grounding.supporting_chunk_ids)} | {grounding.preview}"
            for grounding in groundings
        )
        if grounding_notes:
            bundle.prompts["interrogation_system"] = (
                bundle.prompts["interrogation_system"]
                + " This case was generated from source-ingested material; favor details supported by the source grounding notes."
            )
            bundle.prompts["source_grounding_notes"] = grounding_notes
        self._prepare_generated_case_dir(case_id, owner_alias)
        saved = self.save_bundle(case_id, bundle, owner_alias)
        self.db.write_audit_log(owner_alias, "case.generated", case_id, {"source": "ingestion"})
        return CaseIngestionResponse(bundle=saved, warnings=extracted.warnings, groundings=groundings)

    def approve_case(self, case_id: str, actor_alias: str) -> AuthoringBundle:
        if not self.is_admin(actor_alias):
            raise ValueError("Only admin aliases can approve cases")
        bundle = self._load_stored_bundle(case_id)
        self._validate_bundle_for_approval(bundle)
        bundle.case.status = "approved"
        approved = self.save_bundle(case_id, bundle, actor_alias)
        self.db.write_audit_log(actor_alias, "case.approved", case_id)
        return approved

    def delete_case(self, case_id: str, actor_alias: str) -> None:
        case_dir = self.case_dir(case_id)
        stored = self.db.load_case_bundle(case_id)
        if not case_dir.exists() and stored is None:
            raise ValueError(f"Case '{case_id}' does not exist")
        bundle = stored or load_authoring_bundle(case_dir)
        is_admin = self.is_admin(actor_alias)
        if bundle.case.status == "approved" and not is_admin:
            raise ValueError("Only admins can delete approved cases")
        if bundle.case.status == "draft" and not (is_admin or bundle.case.owner_alias == actor_alias):
            raise ValueError("You do not have permission to delete this case")
        if bundle.case.status not in {"draft", "approved"}:
            raise ValueError(f"Case status '{bundle.case.status}' cannot be deleted")
        self.storage.delete_case_assets(case_id)
        if case_dir.exists():
            shutil.rmtree(case_dir)
        self.db.delete_case_bundle(case_id)
        self.db.write_audit_log(actor_alias, "case.deleted", case_id, {"status": bundle.case.status})

    def _enforce_draft_quota(self, owner_alias: str) -> None:
        owned_drafts = 0
        for case_dir in (path for path in self.cases_root.iterdir() if path.is_dir()):
            try:
                bundle = load_authoring_bundle(case_dir)
            except (FileNotFoundError, ValueError):
                continue
            if bundle.case.status == "draft" and bundle.case.owner_alias == owner_alias:
                owned_drafts += 1
        stored_ids = {
            bundle.case.id
            for bundle in self.db.list_case_bundles()
            if bundle.case.status == "draft" and bundle.case.owner_alias == owner_alias
        }
        owned_drafts += len(stored_ids - {path.name for path in self.cases_root.iterdir() if path.is_dir()})
        if owned_drafts >= settings.max_drafts_per_player:
            raise ValueError("Private draft quota exceeded")

    def _validate_bundle_for_approval(self, bundle: AuthoringBundle) -> None:
        suspect_ids = {suspect.id for suspect in bundle.suspects}
        document_ids = {document.id for document in bundle.documents}
        missing_suspects = set(bundle.case.start_state.initial_suspect_ids) - suspect_ids
        missing_documents = set(bundle.case.start_state.initial_document_ids) - document_ids
        if missing_suspects or missing_documents:
            raise ValueError("Approval failed: start-state references are missing")
        if not bundle.documents or not bundle.suspects:
            raise ValueError("Approval failed: at least one document and suspect are required")
        for beat in bundle.case.deduction_beats:
            if set(beat.requirements.document_ids) - document_ids or set(beat.requirements.suspect_ids) - suspect_ids:
                raise ValueError(f"Approval failed: deduction '{beat.id}' has invalid references")

    def _ensure_template_assets(self, case_dir: Path) -> None:
        templates = {
            case_dir / "assets" / "suspects" / "template-suspect.svg": _template_svg("Suspect", "#5c4630", "#e8dcc9"),
            case_dir / "assets" / "evidence" / "template-evidence.svg": _template_svg("Evidence", "#3b4d5f", "#d8e4ef"),
            case_dir / "assets" / "locations" / "template-location.svg": _template_svg("Location", "#44614b", "#d9eadf"),
            case_dir / "assets" / "locations" / "template-cover.svg": _template_svg("Case File", "#5f3f3f", "#f0dddd"),
        }
        for path, content in templates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(content, encoding="utf-8")


@lru_cache(maxsize=1)
def _template_svg(label: str, accent: str, fill: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" role="img" aria-label="{label}">
  <rect width="320" height="220" fill="{fill}" rx="16"/>
  <rect x="18" y="18" width="284" height="184" fill="none" stroke="{accent}" stroke-width="6" rx="12"/>
  <circle cx="80" cy="86" r="28" fill="{accent}" opacity="0.88"/>
  <rect x="126" y="58" width="124" height="18" fill="{accent}" opacity="0.9" rx="9"/>
  <rect x="126" y="90" width="96" height="14" fill="{accent}" opacity="0.72" rx="7"/>
  <rect x="54" y="150" width="214" height="20" fill="{accent}" opacity="0.82" rx="10"/>
  <text x="160" y="196" fill="{accent}" font-size="24" font-family="Georgia, serif" text-anchor="middle">{label}</text>
</svg>"""
