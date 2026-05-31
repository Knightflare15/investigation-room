from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from ..case_loader import load_authoring_bundle
from ..models import (
    ArchiveDomain,
    AssetEntry,
    AuthoringBundle,
    CaseConfig,
    CaseDocument,
    CreateCaseRequest,
    LocationDossier,
    StartState,
    SubmissionConfig,
    SuspectConfig,
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


class AuthoringService:
    def __init__(self, cases_root: Path) -> None:
        self.cases_root = cases_root
        self.cases_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, case_id: str) -> Path:
        return self.cases_root / case_id

    def create_case(self, payload: CreateCaseRequest) -> AuthoringBundle:
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
            police_summary="Replace this with the police first-pass intake for your mystery.",
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
                "public_profile": {
                    "role": "Replace role",
                    "summary": "Replace with a short public description.",
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
        self.save_bundle(payload.id, bundle)
        return self.load_bundle(payload.id)

    def load_bundle(self, case_id: str) -> AuthoringBundle:
        return load_authoring_bundle(self.case_dir(case_id))

    def list_bundles(self) -> list[AuthoringBundle]:
        bundles: list[AuthoringBundle] = []
        for case_dir in sorted(path for path in self.cases_root.iterdir() if path.is_dir()):
            bundles.append(self.load_bundle(case_dir.name))
        return bundles

    def save_bundle(self, case_id: str, bundle: AuthoringBundle) -> AuthoringBundle:
        case_dir = self.case_dir(case_id)
        if not case_dir.exists():
            raise ValueError(f"Case '{case_id}' does not exist")
        if bundle.case.id != case_id:
            raise ValueError("Case ID in bundle must match the URL case ID")

        archive_dir = case_dir / "archive"
        prompts_dir = case_dir / "prompts"
        archive_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir.mkdir(parents=True, exist_ok=True)

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

        return self.load_bundle(case_id)

    def save_asset(self, case_id: str, folder: str, filename: str, content: bytes) -> AssetEntry:
        case_dir = self.case_dir(case_id)
        if not case_dir.exists():
            raise ValueError(f"Case '{case_id}' does not exist")

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
