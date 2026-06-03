from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

from ..case_loader import load_authoring_bundle
from ..config import settings
from ..models import (
    ArchiveDomain,
    AssetEntry,
    AuthoringBundle,
    CaseBriefInput,
    CaseIngestionInput,
    CaseIngestionResponse,
    CaseConfig,
    CaseDocument,
    CreateCaseRequest,
    GenerateCaseDraftResponse,
    LocationDossier,
    StartState,
    SubmissionConfig,
    SuspectConfig,
)
from .brief_generator import BriefGenerationService
from .source_ingestion import SourceIngestionService


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


class AuthoringService:
    def __init__(self, cases_root: Path) -> None:
        self.cases_root = cases_root
        self.cases_root.mkdir(parents=True, exist_ok=True)
        self.generator = BriefGenerationService()
        self.source_ingestion = SourceIngestionService(settings)

    def case_dir(self, case_id: str) -> Path:
        return self.cases_root / case_id

    def is_admin(self, alias: str) -> bool:
        return alias in settings.admin_aliases

    def _can_access_case(self, case_id: str, alias: str) -> bool:
        bundle = load_authoring_bundle(self.case_dir(case_id))
        return bundle.case.status == "approved" or bundle.case.owner_alias == alias or self.is_admin(alias)

    def create_case(self, payload: CreateCaseRequest, owner_alias: str) -> AuthoringBundle:
        case_dir = self.case_dir(payload.id)
        if case_dir.exists():
            raise ValueError(f"Case '{payload.id}' already exists")

        (case_dir / "archive").mkdir(parents=True, exist_ok=True)
        (case_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (case_dir / "assets" / "suspects").mkdir(parents=True, exist_ok=True)
        (case_dir / "assets" / "evidence").mkdir(parents=True, exist_ok=True)
        (case_dir / "assets" / "locations").mkdir(parents=True, exist_ok=True)

        case_config = CaseConfig(
            id=payload.id,
            title=payload.title,
            hook=payload.hook,
            difficulty=payload.difficulty,
            estimated_minutes=payload.estimated_minutes,
            version=1,
            status="draft",
            owner_alias=owner_alias,
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
            case_id=payload.id,
            title="Incident Summary",
            folder="crime_scene",
            doc_type="police_report",
            source_label="Police First-Pass File",
            summary="Replace with the initial incident summary.",
            body="Replace this document body with the first authored evidence file for your mystery.",
            markdown_path=f"cases/{payload.id}/archive/doc-001-incident-summary.md",
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
        self.save_bundle(payload.id, bundle, owner_alias)
        return self.load_bundle(payload.id, owner_alias)

    def load_bundle(self, case_id: str, alias: str) -> AuthoringBundle:
        if not self._can_access_case(case_id, alias):
            raise ValueError("You do not have access to this draft case")
        return load_authoring_bundle(self.case_dir(case_id))

    def list_bundles(self, alias: str) -> list[AuthoringBundle]:
        bundles: list[AuthoringBundle] = []
        for case_dir in sorted(path for path in self.cases_root.iterdir() if path.is_dir()):
            bundle = load_authoring_bundle(case_dir)
            if bundle.case.status == "approved" or bundle.case.owner_alias == alias or self.is_admin(alias):
                bundles.append(bundle)
        return bundles

    def save_bundle(self, case_id: str, bundle: AuthoringBundle, actor_alias: str) -> AuthoringBundle:
        case_dir = self.case_dir(case_id)
        if not case_dir.exists():
            raise ValueError(f"Case '{case_id}' does not exist")
        if bundle.case.id != case_id:
            raise ValueError("Case ID in bundle must match the URL case ID")
        archive_dir = case_dir / "archive"
        prompts_dir = case_dir / "prompts"
        archive_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_template_assets(case_dir)

        existing = load_authoring_bundle(case_dir) if (case_dir / "case.json").exists() else None
        owner_alias = (existing.case.owner_alias if existing else None) or actor_alias
        if existing and not (self.is_admin(actor_alias) or owner_alias == actor_alias):
            raise ValueError("You do not have permission to edit this case")
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
            (prompts_dir / f"{name}.txt").write_text(content.strip() + "\n", encoding="utf-8")

        return self.load_bundle(case_id, actor_alias)

    def save_asset(self, case_id: str, folder: str, filename: str, content: bytes, actor_alias: str) -> AssetEntry:
        case_dir = self.case_dir(case_id)
        if not case_dir.exists():
            raise ValueError(f"Case '{case_id}' does not exist")
        bundle = load_authoring_bundle(case_dir)
        if not (self.is_admin(actor_alias) or bundle.case.owner_alias == actor_alias):
            raise ValueError("You do not have permission to upload assets for this case")

        safe_folder = _slugify(folder).replace("-", "_")
        extension = Path(filename).suffix.lower() or ".bin"
        safe_name = f"{_slugify(Path(filename).stem)}{extension}"
        relative_path = Path(safe_folder) / safe_name
        target = case_dir / "assets" / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return AssetEntry(
            path=relative_path.as_posix(),
            url=f"/case-assets/{case_id}/assets/{relative_path.as_posix()}",
            kind=safe_folder,
        )

    def generate_case_from_brief(self, payload: CaseBriefInput, owner_alias: str) -> GenerateCaseDraftResponse:
        parsed = self.generator.parse_brief(payload)
        extracted = self.generator.extract_case_draft(parsed)
        bundle = self.generator.generate_bundle(extracted, owner_alias, payload.difficulty, payload.estimated_minutes)
        case_dir = self.case_dir(payload.case_id)
        if case_dir.exists():
            raise ValueError(f"Case '{payload.case_id}' already exists")
        (case_dir / "archive").mkdir(parents=True, exist_ok=True)
        (case_dir / "prompts").mkdir(parents=True, exist_ok=True)
        self._ensure_template_assets(case_dir)
        saved = self.save_bundle(payload.case_id, bundle, owner_alias)
        return GenerateCaseDraftResponse(bundle=saved, warnings=extracted.warnings)

    def ingest_case_from_source(self, payload: CaseIngestionInput, owner_alias: str) -> CaseIngestionResponse:
        extracted, groundings = self.source_ingestion.extract(payload)
        bundle = self.generator.generate_bundle(extracted, owner_alias, payload.difficulty, payload.estimated_minutes)
        grounding_notes = "\n".join(
            f"- {grounding.generated_field}: {', '.join(grounding.supporting_chunk_ids)} | {grounding.preview}"
            for grounding in groundings
        )
        if grounding_notes:
            bundle.prompts["interrogation_system"] = (
                bundle.prompts["interrogation_system"]
                + " This case was generated from source-ingested material; favor details supported by the source grounding notes."
            )
            bundle.prompts["source_grounding_notes"] = grounding_notes
        case_dir = self.case_dir(payload.case_id)
        if case_dir.exists():
            raise ValueError(f"Case '{payload.case_id}' already exists")
        (case_dir / "archive").mkdir(parents=True, exist_ok=True)
        (case_dir / "prompts").mkdir(parents=True, exist_ok=True)
        self._ensure_template_assets(case_dir)
        saved = self.save_bundle(payload.case_id, bundle, owner_alias)
        return CaseIngestionResponse(bundle=saved, warnings=extracted.warnings, groundings=groundings)

    def approve_case(self, case_id: str, actor_alias: str) -> AuthoringBundle:
        if not self.is_admin(actor_alias):
            raise ValueError("Only admin aliases can approve cases")
        bundle = load_authoring_bundle(self.case_dir(case_id))
        bundle.case.status = "approved"
        return self.save_bundle(case_id, bundle, actor_alias)

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
