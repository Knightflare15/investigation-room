from __future__ import annotations

import json
from pathlib import Path

import yaml

from .models import AssetEntry, AuthoringBundle, CaseConfig, CaseDocument, LoadedCase, SuspectFile


def _asset_url(case_id: str, asset_path: str | None) -> str | None:
    if not asset_path:
        return None
    return f"/case-assets/{case_id}/assets/{asset_path.replace('\\', '/')}"


def _resolve_case_assets(config: CaseConfig) -> CaseConfig:
    for domain in config.archive_domains:
        domain.image_url = _asset_url(config.id, domain.image_path)
    for dossier in config.location_dossiers:
        dossier.image_url = _asset_url(config.id, dossier.image_path)
    config.cover_image_url = _asset_url(config.id, config.cover_image_path)
    return config


def _parse_markdown_document(path: Path, case_id: str) -> CaseDocument:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{path} is missing front matter")

    _, frontmatter, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}
    return CaseDocument(
        id=meta["id"],
        case_id=case_id,
        title=meta["title"],
        folder=meta["folder"],
        doc_type=meta["doc_type"],
        source_label=meta.get("source_label", ""),
        unlock_rule=meta.get("unlock_rule"),
        entity_tags=meta.get("entity_tags", []),
        summary=meta.get("summary", ""),
        body=body.strip(),
        markdown_path=str(path.as_posix()),
        image_path=meta.get("image_path"),
        image_url=_asset_url(case_id, meta.get("image_path")),
    )


def load_case(case_dir: Path) -> LoadedCase:
    config = _resolve_case_assets(CaseConfig.model_validate(json.loads((case_dir / "case.json").read_text(encoding="utf-8"))))
    suspect_file = SuspectFile.model_validate(json.loads((case_dir / "suspects.json").read_text(encoding="utf-8")))
    prompts_dir = case_dir / "prompts"
    archive_dir = case_dir / "archive"

    suspects = {
        suspect.id: suspect.model_copy(update={"image_url": _asset_url(config.id, suspect.image_path)})
        for suspect in suspect_file.suspects
    }
    documents = {
        document.id: document
        for document in sorted(
            (_parse_markdown_document(path, config.id) for path in archive_dir.glob("*.md")),
            key=lambda item: item.id,
        )
    }
    prompts = {
        path.stem: path.read_text(encoding="utf-8").strip()
        for path in prompts_dir.glob("*.txt")
    }
    return LoadedCase(config=config, suspects=suspects, documents=documents, prompts=prompts)


def list_case_assets(case_dir: Path, case_id: str) -> list[AssetEntry]:
    assets_dir = case_dir / "assets"
    if not assets_dir.exists():
        return []
    assets: list[AssetEntry] = []
    for path in sorted(asset for asset in assets_dir.rglob("*") if asset.is_file()):
        relative = path.relative_to(assets_dir).as_posix()
        folder = relative.split("/", 1)[0] if "/" in relative else "misc"
        assets.append(
            AssetEntry(
                path=relative,
                url=_asset_url(case_id, relative),
                kind=folder,
            )
        )
    return assets


def load_authoring_bundle(case_dir: Path) -> AuthoringBundle:
    loaded = load_case(case_dir)
    return AuthoringBundle(
        case=loaded.config,
        suspects=list(loaded.suspects.values()),
        documents=list(loaded.documents.values()),
        prompts=loaded.prompts,
        assets=list_case_assets(case_dir, loaded.config.id),
    )


def loaded_case_from_bundle(bundle: AuthoringBundle) -> LoadedCase:
    config = _resolve_case_assets(bundle.case.model_copy(deep=True))
    suspects = {
        suspect.id: suspect.model_copy(update={"image_url": suspect.image_url or _asset_url(config.id, suspect.image_path)})
        for suspect in bundle.suspects
    }
    documents = {
        document.id: document.model_copy(update={"image_url": document.image_url or _asset_url(config.id, document.image_path)})
        for document in bundle.documents
    }
    return LoadedCase(config=config, suspects=suspects, documents=documents, prompts=dict(bundle.prompts))


def load_cases(cases_root: Path) -> dict[str, LoadedCase]:
    loaded: dict[str, LoadedCase] = {}
    for case_dir in sorted(path for path in cases_root.iterdir() if path.is_dir()):
        case = load_case(case_dir)
        loaded[case.config.id] = case
    return loaded
