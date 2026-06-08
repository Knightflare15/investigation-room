from __future__ import annotations

import re
from collections import Counter

from ..models import (
    ArchiveDomain,
    AuthoringBundle,
    BoardLinkDefinition,
    CaseBriefInput,
    CaseConfig,
    CaseDocument,
    DeductionBeat,
    DeductionRequirements,
    EvidenceDraft,
    ExtractedCaseDraft,
    ExtractedSuspectDraft,
    LocationDossier,
    ParsedCaseBrief,
    PersonalityProfile,
    PrivateTruth,
    PublicProfile,
    RescanRule,
    StartState,
    SubmissionConfig,
    SuspectConfig,
    Trigger,
    TriggerEffects,
    DialogueRules,
    MemoryRules,
)


REQUIRED_HEADINGS = [
    "Case Title",
    "Premise",
    "Victim",
    "Setting",
    "Suspects",
    "Relationships",
    "Timeline",
    "Evidence",
    "Hidden Truth",
    "Solution",
]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def _split_list_section(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[-*]\s*", "", stripped)
        if stripped:
            items.append(stripped)
    return items


def _split_csvish(value: str) -> list[str]:
    parts = re.split(r"[;,]\s*|\n+", value.strip())
    return [part.strip(" -") for part in parts if part.strip(" -")]


def _initials(name: str) -> str:
    tokens = [token[0] for token in re.findall(r"[A-Za-z0-9]+", name)]
    return "".join(tokens[:2]).upper() or "SU"


class BriefGenerationService:
    def parse_brief(self, payload: CaseBriefInput) -> ParsedCaseBrief:
        brief = payload.brief.strip()
        if not brief:
            raise ValueError("Case brief is empty.")

        heading_pattern = re.compile(
            r"^(?P<heading>" + "|".join(re.escape(heading) for heading in REQUIRED_HEADINGS) + r")\s*:?\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        matches = list(heading_pattern.finditer(brief))
        sections: dict[str, str] = {}
        if not matches:
            raise ValueError("Case brief is missing the required section headings.")

        for index, match in enumerate(matches):
            raw_heading = match.group("heading")
            heading = next(item for item in REQUIRED_HEADINGS if item.lower() == raw_heading.lower())
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(brief)
            sections[heading] = brief[start:end].strip()

        missing = [heading for heading in REQUIRED_HEADINGS if not sections.get(heading)]
        if missing:
            raise ValueError(f"Case brief is missing required content for: {', '.join(missing)}")
        return ParsedCaseBrief(case_id=payload.case_id, sections=sections)

    def extract_case_draft(self, parsed: ParsedCaseBrief) -> ExtractedCaseDraft:
        title = parsed.sections["Case Title"].splitlines()[0].strip()
        premise = parsed.sections["Premise"].strip()
        setting = parsed.sections["Setting"].strip()
        victim = parsed.sections["Victim"].strip()
        relationships = _split_list_section(parsed.sections["Relationships"])
        timeline = _split_list_section(parsed.sections["Timeline"])
        hidden_truth = _split_list_section(parsed.sections["Hidden Truth"])
        suspects = self._extract_suspects(parsed.sections["Suspects"])
        evidence = self._extract_evidence(parsed.sections["Evidence"])
        culprit_name, motive, solution_summary = self._extract_solution(parsed.sections["Solution"], suspects)
        contradictions = self._derive_contradictions(relationships, timeline, hidden_truth, evidence)
        warnings: list[str] = []

        if len(suspects) < 2:
            raise ValueError("At least two suspects must be provided in the Suspects section.")
        if not evidence:
            warnings.append("No structured evidence blocks were found; the generator created minimal archive evidence.")
            evidence = self._fallback_evidence(premise, setting, hidden_truth)
        if not culprit_name:
            culprit_name = suspects[0].name
            warnings.append("No culprit was clearly identified in Solution; defaulted to the first suspect.")
        if not motive:
            motive = "Control the narrative before the full truth surfaced."
            warnings.append("No motive was clearly identified in Solution; a generic motive was added.")

        return ExtractedCaseDraft(
            case_id=parsed.case_id,
            title=title,
            premise=premise,
            setting=setting,
            victim=victim,
            relationships=relationships,
            timeline=timeline,
            hidden_truth=hidden_truth,
            solution_summary=solution_summary,
            culprit_name=culprit_name,
            motive=motive,
            contradictions=contradictions,
            suspects=suspects,
            evidence=evidence,
            warnings=warnings,
        )

    def generate_bundle(self, extracted: ExtractedCaseDraft, owner_alias: str, difficulty: str, estimated_minutes: int) -> AuthoringBundle:
        suspect_configs = self._build_suspects(extracted)
        documents = self._build_documents(extracted, suspect_configs)
        initial_suspects = [suspect.id for suspect in suspect_configs[: min(3, len(suspect_configs))]]
        initial_documents = [document.id for document in documents[: min(3, len(documents))]]
        locations = self._build_locations(extracted, documents)
        rescan_rules = self._build_rescan_rules(extracted, suspect_configs, documents, locations)
        board_links = self._build_board_links(extracted, suspect_configs, documents)
        deduction_beats = self._build_deduction_beats(extracted, suspect_configs, documents, board_links)

        case_config = CaseConfig(
            id=extracted.case_id,
            title=extracted.title,
            hook=extracted.premise.split(".")[0].strip()[:160] or extracted.premise[:160],
            difficulty=difficulty,
            estimated_minutes=estimated_minutes,
            version=1,
            status="draft",
            owner_alias=owner_alias,
            police_summary=f"{extracted.premise}\n\nVictim: {extracted.victim}\nSetting: {extracted.setting}",
            cover_image_path="locations/template-cover.svg",
            start_state=StartState(
                initial_suspect_ids=initial_suspects,
                initial_document_ids=initial_documents,
                initial_open_questions=self._initial_questions(extracted),
            ),
            archive_domains=self._build_domains(),
            location_dossiers=locations,
            rescan_rules=rescan_rules,
            submission=SubmissionConfig(
                required_fields=["culprit_id", "motive_text", "timeline_text", "evidence_ids"],
                min_evidence_count=min(3, max(2, len(initial_documents))),
            ),
            valid_board_links=board_links,
            deduction_beats=deduction_beats,
        )

        prompts = {
            "interrogation_system": (
                f"You are participating in a detective mystery simulation set around '{extracted.title}'. "
                "Stay consistent with the supplied suspect truth, personality profile, and retrieved evidence context."
            ),
            "hint_system": (
                "Guide the detective toward contradictions, hidden relationships, or overlooked evidence without naming the culprit outright."
            ),
        }
        return AuthoringBundle(case=case_config, suspects=suspect_configs, documents=documents, prompts=prompts, assets=[])

    def _extract_suspects(self, section: str) -> list[ExtractedSuspectDraft]:
        blocks = [block.strip() for block in re.split(r"\n\s*\n(?=Name\s*:)", section, flags=re.IGNORECASE) if block.strip()]
        if len(blocks) == 1 and "Name:" not in blocks[0]:
            blocks = [block.strip() for block in re.split(r"\n\s*-\s*", section) if block.strip()]
        suspects: list[ExtractedSuspectDraft] = []
        for block in blocks:
            fields = self._parse_block_fields(block)
            name = fields.get("name") or fields.get("suspect") or block.splitlines()[0].strip("- ").strip()
            if not name:
                continue
            summary = fields.get("public summary") or fields.get("summary") or fields.get("description") or "Publicly composed, with more to hide than they admit."
            suspect = ExtractedSuspectDraft(
                name=name,
                role=fields.get("role", "Person of interest"),
                public_summary=summary,
                hidden_facts=_split_csvish(fields.get("hidden facts", fields.get("hidden fact", ""))),
                secrets=_split_csvish(fields.get("secrets", "")),
                traits=_split_csvish(fields.get("traits", "")),
                speaking_style=fields.get("speaking style", "Measured and guarded."),
                catchphrase=fields.get("catchphrase", ""),
                verbal_tells=_split_csvish(fields.get("verbal tells", "")),
                outward_goal=fields.get("outward goal", "Protect their position and avoid exposure."),
                protective_target=fields.get("protective target", fields.get("protecting", "")),
                protective_reason=fields.get("protective reason", ""),
            )
            suspects.append(suspect)
        return suspects

    def _extract_evidence(self, section: str) -> list[EvidenceDraft]:
        evidence: list[EvidenceDraft] = []
        blocks = [block.strip() for block in re.split(r"\n\s*\n(?=Title\s*:)", section, flags=re.IGNORECASE) if block.strip()]
        if not blocks:
            blocks = [item for item in _split_list_section(section) if item]
        for block in blocks:
            fields = self._parse_block_fields(block)
            title = fields.get("title") or block.splitlines()[0].strip("- ").strip()
            if not title:
                continue
            details = _split_list_section(block)
            summary = fields.get("summary") or "A case document generated from the creator brief."
            doc_type = fields.get("type", fields.get("doc type", self._infer_doc_type(title, summary)))
            tags = _split_csvish(fields.get("tags", ""))
            hidden_value = fields.get("hidden", "").lower()
            evidence.append(
                EvidenceDraft(
                    title=title,
                    summary=summary,
                    details=details[1:] if len(details) > 1 else details,
                    doc_type=doc_type,
                    folder=self._infer_folder(doc_type, title, summary),
                    tags=tags or self._derive_tags_from_text(f"{title} {summary}"),
                    hidden=hidden_value in {"yes", "true", "hidden", "later"},
                )
            )
        return evidence

    def _extract_solution(self, section: str, suspects: list[ExtractedSuspectDraft]) -> tuple[str, str, str]:
        fields = self._parse_block_fields(section)
        culprit_name = fields.get("culprit", "")
        motive = fields.get("motive", "")
        if not culprit_name:
            lower = section.lower()
            for suspect in suspects:
                if suspect.name.lower() in lower:
                    culprit_name = suspect.name
                    break
        return culprit_name, motive, section.strip()

    def _derive_contradictions(
        self,
        relationships: list[str],
        timeline: list[str],
        hidden_truth: list[str],
        evidence: list[EvidenceDraft],
    ) -> list[str]:
        contradictions = hidden_truth[:2]
        if timeline:
            contradictions.append(f"The public timeline does not fully align with: {timeline[-1]}")
        if relationships:
            contradictions.append(f"One relationship appears more strategic than admitted: {relationships[0]}")
        if evidence:
            contradictions.append(f"Evidence may undermine an early statement: {evidence[0].title}")
        return list(dict.fromkeys(item for item in contradictions if item))[:4]

    def _fallback_evidence(self, premise: str, setting: str, hidden_truth: list[str]) -> list[EvidenceDraft]:
        return [
            EvidenceDraft(
                title="Incident Summary",
                summary=premise[:180],
                details=[premise, setting],
                doc_type="police_report",
                folder="crime_scene",
                tags=self._derive_tags_from_text(f"{premise} {setting}"),
            ),
            EvidenceDraft(
                title="Witness Notes",
                summary="A condensed witness-style account generated from the brief.",
                details=hidden_truth[:2] or [setting],
                doc_type="witness_statement",
                folder="witness_accounts",
                tags=self._derive_tags_from_text("witness statement timeline"),
            ),
        ]

    def _build_suspects(self, extracted: ExtractedCaseDraft) -> list[SuspectConfig]:
        culprit = extracted.culprit_name.lower()
        suspects: list[SuspectConfig] = []
        for index, suspect in enumerate(extracted.suspects, start=1):
            suspect_id = f"sus_{_slugify(suspect.name)}"
            private_facts = suspect.hidden_facts or [f"{suspect.name} knows more about {extracted.victim} than they admit."]
            secrets = suspect.secrets or ([f"{suspect.name} is withholding a key detail tied to the solution."] if suspect.name.lower() == culprit else [f"{suspect.name} is protecting their own reputation."])
            traits = suspect.traits or self._derive_traits_from_summary(suspect.public_summary)
            speaking_style = suspect.speaking_style or "Measured and guarded."
            outward_goal = suspect.outward_goal or ("Control the fallout." if suspect.name.lower() == culprit else "Protect themselves from becoming the obvious target.")
            protective_target = suspect.protective_target or ("the truth about the case" if suspect.name.lower() == culprit else "")
            protective_reason = suspect.protective_reason or ("Revealing too much would unravel the case early." if suspect.name.lower() == culprit else "")
            pressure_triggers = self._derive_pressure_triggers(suspect, extracted)
            suspects.append(
                SuspectConfig(
                    id=suspect_id,
                    display_name=suspect.name,
                    public_profile=PublicProfile(role=suspect.role, summary=self._sanitize_public_summary(suspect.public_summary, private_facts + secrets)),
                    personality_profile=PersonalityProfile(
                        traits=traits,
                        speaking_style=speaking_style,
                        catchphrase=suspect.catchphrase,
                        verbal_tells=suspect.verbal_tells or ["Avoids giving direct timelines under pressure."],
                        outward_goal=outward_goal,
                        protective_target=protective_target,
                        protective_reason=protective_reason,
                    ),
                    private_truth=PrivateTruth(
                        facts_known=private_facts,
                        secrets=secrets,
                        non_negotiables=[f"{suspect.name} must stay consistent with the authored solution."],
                    ),
                    dialogue_rules=DialogueRules(
                        baseline_tone=self._baseline_tone_from_traits(traits),
                        lie_strategy="deflect until the evidence becomes too specific",
                        pressure_triggers=pressure_triggers,
                        shut_down_threshold=80 if suspect.name.lower() == culprit else 75,
                    ),
                    memory_rules=MemoryRules(),
                    portrait_key=_initials(suspect.name),
                    image_path="suspects/template-suspect.svg",
                    unlock_rule=None if index <= 3 else f"unlock_{suspect_id}",
                )
            )
        return suspects

    def _build_documents(self, extracted: ExtractedCaseDraft, suspects: list[SuspectConfig]) -> list[CaseDocument]:
        documents: list[CaseDocument] = []
        documents.append(
            CaseDocument(
                id="doc_incident",
                case_id=extracted.case_id,
                title="Incident Summary",
                folder="crime_scene",
                doc_type="police_report",
                source_label="Initial Incident File",
                summary=extracted.premise[:180],
                body="\n\n".join(
                    [
                        extracted.premise,
                        f"Victim: {extracted.victim}",
                        f"Setting: {extracted.setting}",
                        "Timeline anchors:",
                        *[f"- {item}" for item in extracted.timeline[:4]],
                    ]
                ),
                markdown_path=f"cases/{extracted.case_id}/archive/doc-001-incident-summary.md",
                entity_tags=self._derive_tags_from_text(f"{extracted.victim} {extracted.setting} {extracted.premise}"),
                image_path="evidence/template-evidence.svg",
            )
        )

        doc_index = 2
        for suspect in suspects[:2]:
            documents.append(
                CaseDocument(
                    id=f"doc_statement_{_slugify(suspect.display_name)}",
                    case_id=extracted.case_id,
                    title=f"Witness Statement - {suspect.display_name}",
                    folder="witness_accounts",
                    doc_type="witness_statement",
                    source_label="Interview Notes",
                    summary=f"Public statement attributed to {suspect.display_name}.",
                    body=(
                        f"{suspect.display_name} describes the night in a {suspect.personality_profile.speaking_style.lower()} way.\n\n"
                        f"Public account: {suspect.public_profile.summary}\n\n"
                        f"Observed tell: {suspect.personality_profile.verbal_tells[0] if suspect.personality_profile.verbal_tells else 'Keeps answers careful and selective.'}"
                    ),
                    markdown_path=f"cases/{extracted.case_id}/archive/doc-{doc_index:03d}-statement-{_slugify(suspect.display_name)}.md",
                    entity_tags=self._derive_tags_from_text(f"{suspect.display_name} {suspect.public_profile.role} witness timeline"),
                    image_path="evidence/template-evidence.svg",
                )
            )
            doc_index += 1

        evidence_items = extracted.evidence[:]
        added_special_type = Counter()
        for item in evidence_items:
            documents.append(
                CaseDocument(
                    id=f"doc_{_slugify(item.title)}",
                    case_id=extracted.case_id,
                    title=item.title,
                    folder=item.folder,
                    doc_type=item.doc_type,
                    source_label="Generated Evidence Packet",
                    unlock_rule=f"unlock_doc_{_slugify(item.title)}" if item.hidden else None,
                    summary=item.summary,
                    body="\n\n".join(item.details or [item.summary]),
                    markdown_path=f"cases/{extracted.case_id}/archive/doc-{doc_index:03d}-{_slugify(item.title)}.md",
                    entity_tags=item.tags,
                    image_path="evidence/template-evidence.svg",
                )
            )
            added_special_type[item.doc_type] += 1
            doc_index += 1

        if not any(doc.doc_type == "forensic_report" for doc in documents):
            documents.append(
                CaseDocument(
                    id="doc_forensic_overview",
                    case_id=extracted.case_id,
                    title="Forensic Overview",
                    folder="forensics",
                    doc_type="forensic_report",
                    source_label="Analyst Summary",
                    summary="A generated forensic-style summary to support the investigation loop.",
                    body="\n\n".join(extracted.hidden_truth[:2] or [extracted.setting, extracted.solution_summary]),
                    markdown_path=f"cases/{extracted.case_id}/archive/doc-{doc_index:03d}-forensic-overview.md",
                    entity_tags=self._derive_tags_from_text(f"{extracted.victim} forensic timeline"),
                    image_path="evidence/template-evidence.svg",
                )
            )
            doc_index += 1

        if not any(doc.doc_type == "communications_log" for doc in documents):
            documents.append(
                CaseDocument(
                    id="doc_comms_log",
                    case_id=extracted.case_id,
                    title="Communications Log",
                    folder="communications",
                    doc_type="communications_log",
                    source_label="Recovered Communications",
                    summary="A generated communications-style record tying names and timing together.",
                    body="\n\n".join(extracted.relationships[:2] or extracted.timeline[:2] or [extracted.premise]),
                    markdown_path=f"cases/{extracted.case_id}/archive/doc-{doc_index:03d}-communications-log.md",
                    entity_tags=self._derive_tags_from_text("communications call log message timeline"),
                    image_path="evidence/template-evidence.svg",
                )
            )

        return documents

    def _build_rescan_rules(
        self,
        extracted: ExtractedCaseDraft,
        suspects: list[SuspectConfig],
        documents: list[CaseDocument],
        locations: list[LocationDossier],
    ) -> list[RescanRule]:
        hidden_documents = [document for document in documents if document.unlock_rule]
        rules: list[RescanRule] = []
        for index, document in enumerate(hidden_documents, start=1):
            trigger_value = document.entity_tags[0] if document.entity_tags else document.title
            location_id = next(
                (location.id for location in locations if document.id in location.linked_document_ids),
                locations[0].id if locations else None,
            )
            rules.append(
                RescanRule(
                    id=f"unlock_{document.id}",
                    trigger=Trigger(type="context_entity_discovered", value=trigger_value, location_id=location_id),
                    effects=TriggerEffects(unlock_document_ids=[document.id], surface_document_ids=["doc_incident"]),
                )
            )

        for suspect in [candidate for candidate in suspects if candidate.unlock_rule]:
            rules.append(
                RescanRule(
                    id=f"unlock_{suspect.id}",
                    trigger=Trigger(type="conversation_context_discovered", value=suspect.display_name),
                    effects=TriggerEffects(unlock_suspect_ids=[suspect.id]),
                )
            )
        return rules

    def _build_board_links(
        self,
        extracted: ExtractedCaseDraft,
        suspects: list[SuspectConfig],
        documents: list[CaseDocument],
    ) -> list[BoardLinkDefinition]:
        culprit = next((suspect for suspect in suspects if suspect.display_name.lower() == extracted.culprit_name.lower()), suspects[0])
        target_doc = next((document for document in documents if document.unlock_rule), documents[min(1, len(documents) - 1)])
        return [
            BoardLinkDefinition(
                id=f"victim-{target_doc.id}-hidden-thread",
                source_id="victim",
                target_id=target_doc.id,
                link_type="hidden-thread",
                notes=f"One hidden thread tied to {target_doc.title} may unlock more of the case.",
            ),
            BoardLinkDefinition(
                id=f"{culprit.id}-{target_doc.id}-motive-link",
                source_id=culprit.id,
                target_id=target_doc.id,
                link_type="motive-link",
                notes=f"{culprit.display_name} has a motive thread tied to {target_doc.title}.",
            ),
        ]

    def _build_deduction_beats(
        self,
        extracted: ExtractedCaseDraft,
        suspects: list[SuspectConfig],
        documents: list[CaseDocument],
        board_links: list[BoardLinkDefinition],
    ) -> list[DeductionBeat]:
        culprit = next(
            (suspect for suspect in suspects if suspect.display_name.lower() == extracted.culprit_name.lower()),
            suspects[0],
        )
        beats: list[DeductionBeat] = []
        hidden_documents = [document for document in documents if document.unlock_rule]
        primary_hidden = hidden_documents[0] if hidden_documents else None
        primary_link = board_links[0] if board_links else None
        culprit_link = next((link for link in board_links if link.source_id == culprit.id), None)

        if primary_hidden and primary_link:
            beats.append(
                DeductionBeat(
                    id=f"deduce-{_slugify(primary_hidden.title)}",
                    title=f"{primary_hidden.title} Proven",
                    payoff=(
                        f"You proved {primary_hidden.title} matters to the hidden thread: "
                        f"{primary_link.notes}"
                    ),
                    requirements=DeductionRequirements(
                        document_ids=[primary_hidden.id],
                        board_link_ids=[primary_link.id],
                    ),
                    objective=f"Use {primary_hidden.title} to pressure the suspect with the weakest explanation.",
                )
            )

        if culprit_link:
            linked_doc = next((document for document in documents if document.id == culprit_link.target_id), primary_hidden)
            requirements = DeductionRequirements(
                board_link_ids=[culprit_link.id],
                suspect_ids=[culprit.id],
            )
            if linked_doc:
                requirements.document_ids = [linked_doc.id]
            beats.append(
                DeductionBeat(
                    id=f"deduce-{_slugify(culprit.display_name)}-motive",
                    title=f"{culprit.display_name} Motive Thread",
                    payoff=(
                        f"Your board now ties {culprit.display_name} to a concrete motive thread. "
                        f"{culprit_link.notes}"
                    ),
                    requirements=requirements,
                    objective=f"Press {culprit.display_name} with the linked evidence and compare the answer against the timeline.",
                )
            )

        context_doc = next(
            (
                document
                for document in documents
                if document.entity_tags and document.id != (primary_hidden.id if primary_hidden else "")
            ),
            documents[0] if documents else None,
        )
        if context_doc and context_doc.entity_tags:
            context = context_doc.entity_tags[0]
            beats.append(
                DeductionBeat(
                    id=f"deduce-{_slugify(context)}-context",
                    title=f"{context} Becomes Relevant",
                    payoff=(
                        f"{context} is no longer just a search term. It connects directly to {context_doc.title} "
                        "and should be tested against the suspects' statements."
                    ),
                    requirements=DeductionRequirements(
                        document_ids=[context_doc.id],
                        context_values=[context],
                    ),
                    objective=f"Use {context} as a focused rescan or interrogation pressure point.",
                )
            )

        if extracted.hidden_truth:
            truth_doc = next(
                (document for document in documents if document.doc_type in {"forensic_report", "communications_log"}),
                documents[-1] if documents else None,
            )
            if truth_doc:
                beats.append(
                    DeductionBeat(
                        id="deduce-hidden-truth-pattern",
                        title="Hidden Truth Pattern",
                        payoff=(
                            f"The evidence now supports the buried pattern: {extracted.hidden_truth[0]} "
                            "Treat this as a theory anchor, not a loose clue."
                        ),
                        requirements=DeductionRequirements(document_ids=[truth_doc.id]),
                        objective="Pin the strongest supporting evidence, then formalize the accusation when the timeline holds.",
                    )
                )

        unique: list[DeductionBeat] = []
        seen: set[str] = set()
        for beat in beats:
            if beat.id in seen:
                continue
            unique.append(beat)
            seen.add(beat.id)
        return unique[:4]

    def _build_domains(self) -> list[ArchiveDomain]:
        return [
            ArchiveDomain(id="crime_scene", label="Crime Scene Packet", image_path="locations/template-location.svg", summary="Primary incident records and early observations."),
            ArchiveDomain(id="witness_accounts", label="Witness Accounts", image_path="locations/template-location.svg", summary="Statements, recollections, and interview notes."),
            ArchiveDomain(id="forensics", label="Forensics and Medical", image_path="evidence/template-evidence.svg", summary="Generated forensic and medical-style summaries."),
            ArchiveDomain(id="communications", label="Communications and Logs", image_path="evidence/template-evidence.svg", summary="Messages, logs, or coordination records."),
        ]

    def _build_locations(self, extracted: ExtractedCaseDraft, documents: list[CaseDocument]) -> list[LocationDossier]:
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", extracted.setting) if sentence.strip()]
        primary_summary = sentences[0] if sentences else extracted.setting
        linked = [document.id for document in documents[:3]]
        return [
            LocationDossier(
                id="loc_primary_scene",
                label="Primary Scene",
                summary=primary_summary,
                image_path="locations/template-location.svg",
                linked_document_ids=linked,
            )
        ]

    def _initial_questions(self, extracted: ExtractedCaseDraft) -> list[str]:
        base = extracted.contradictions[:]
        if extracted.culprit_name:
            base.append(f"What is {extracted.culprit_name} trying hardest to keep buried?")
        if extracted.evidence:
            base.append(f"Why does {extracted.evidence[0].title} matter more than it first appears?")
        return base[:3] or [
            "Which statement breaks first under pressure?",
            "What detail in the archive changes the timeline?",
            "Who benefits most from the hidden truth staying hidden?",
        ]

    def _parse_block_fields(self, block: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        current_key: str | None = None
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                current_key = key.strip().lower()
                fields[current_key] = value.strip()
            elif current_key is not None:
                fields[current_key] = f"{fields[current_key]} {stripped}".strip()
        return fields

    def _infer_doc_type(self, title: str, summary: str) -> str:
        text = f"{title} {summary}".lower()
        if any(word in text for word in ("autopsy", "forensic", "toxicology", "medical")):
            return "forensic_report"
        if any(word in text for word in ("call", "message", "email", "log")):
            return "communications_log"
        if any(word in text for word in ("witness", "statement", "interview")):
            return "witness_statement"
        if any(word in text for word in ("ledger", "receipt", "invoice", "bank")):
            return "financial_record"
        return "memo"

    def _infer_folder(self, doc_type: str, title: str, summary: str) -> str:
        if doc_type == "forensic_report":
            return "forensics"
        if doc_type == "communications_log":
            return "communications"
        if doc_type == "witness_statement":
            return "witness_accounts"
        if doc_type == "financial_record":
            return "financial"
        text = f"{title} {summary}".lower()
        if "scene" in text or "incident" in text:
            return "crime_scene"
        return "crime_scene"

    def _derive_tags_from_text(self, text: str) -> list[str]:
        tokens = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text)
        tags = list(dict.fromkeys(tokens))
        if not tags:
            words = [word for word in re.findall(r"[A-Za-z0-9']+", text.lower()) if len(word) > 4]
            tags = [word.title() for word in words[:4]]
        return tags[:4]

    def _derive_pressure_triggers(self, suspect: ExtractedSuspectDraft, extracted: ExtractedCaseDraft) -> list[str]:
        triggers = []
        if suspect.protective_target:
            triggers.append(suspect.protective_target)
        if suspect.role:
            triggers.append(suspect.role)
        triggers.extend(suspect.traits[:2])
        triggers.extend(item.title for item in extracted.evidence[:2])
        triggers.extend(self._derive_tags_from_text(extracted.motive))
        return list(dict.fromkeys(trigger for trigger in triggers if trigger))[:5]

    def _baseline_tone_from_traits(self, traits: list[str]) -> str:
        text = " ".join(traits).lower()
        if "charming" in text or "smooth" in text:
            return "coolly amused"
        if "aggressive" in text or "thin-skinned" in text:
            return "tense and defensive"
        if "empathetic" in text or "gentle" in text:
            return "soft-spoken but guarded"
        return "controlled and careful"

    def _derive_traits_from_summary(self, summary: str) -> list[str]:
        text = summary.lower()
        traits = []
        if "calm" in text or "precise" in text:
            traits.append("controlled")
        if "soft" in text or "gentle" in text:
            traits.append("empathetic")
        if "evasive" in text or "guarded" in text:
            traits.append("guarded")
        if "sharp" in text or "charming" in text:
            traits.append("charming")
        return traits or ["guarded", "strategic"]

    def _sanitize_public_summary(self, summary: str, private_items: list[str]) -> str:
        lowered = summary.lower()
        for item in private_items:
            snippet = item.strip().lower()
            if snippet and snippet in lowered:
                return "Publicly composed and careful about what they choose to reveal."
        return summary
