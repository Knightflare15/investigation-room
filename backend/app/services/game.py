from __future__ import annotations

import threading
from dataclasses import dataclass

from ..case_loader import load_cases
from ..config import Settings
from ..database import create_database
from ..models import (
    BoardLinkRequest,
    BoardLinkResponse,
    CommunityStatsResponse,
    ConfrontRequest,
    ConversationState,
    ConversationTurn,
    DialogueResponse,
    LoadedCase,
    PlayerCaseState,
    RescanRequest,
    RescanResponse,
    SaveStateResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SubmitTheoryRequest,
    SubmitTheoryResponse,
    SuspectConfig,
    TogglePinRequest,
)
from .dialogue import DialogueService
from .retrieval import RetrievalService


@dataclass
class RescanEffects:
    unlocked_documents: list[str]
    unlocked_suspects: list[str]
    surfaced_document_ids: list[str]


class GameService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = create_database(settings.database_url, settings.db_path)
        self._cases_lock = threading.RLock()
        self.cases = load_cases(settings.cases_path)
        self.retrieval = RetrievalService(settings)
        self.dialogue = DialogueService(settings, self.retrieval)
        self._stream_lead_events: dict[tuple[str, str, str], dict[str, list[str]]] = {}

    def _build_lead_messages(
        self,
        case: LoadedCase,
        effects: RescanEffects,
        contexts: list[str],
        source: str = "interrogation",
    ) -> list[str]:
        if not effects.unlocked_documents and not effects.unlocked_suspects:
            return []
        context_hint = next((context for context in contexts if context.strip()), source)
        messages: list[str] = []
        for document_id in effects.unlocked_documents:
            document = case.documents.get(document_id)
            label = document.title if document else document_id
            messages.append(f"Lead surfaced: {label} became relevant after {context_hint} came up.")
        for suspect_id in effects.unlocked_suspects:
            suspect = case.suspects.get(suspect_id)
            label = suspect.display_name if suspect else suspect_id
            messages.append(f"Lead surfaced: {label} can now be called in after {context_hint} came up.")
        return messages

    def pop_stream_lead_event(self, case_id: str, player_alias: str, suspect_id: str) -> dict[str, list[str]]:
        return self._stream_lead_events.pop(
            (case_id, player_alias, suspect_id),
            {"unlocked_documents": [], "unlocked_suspects": [], "lead_messages": []},
        )

    def reload_cases(self) -> None:
        new_cases = load_cases(self.settings.cases_path)
        with self._cases_lock:
            self.cases = new_cases

    def _is_admin(self, alias: str) -> bool:
        return alias in self.settings.admin_aliases

    def _can_access_case(self, case: LoadedCase, alias: str | None = None) -> bool:
        if case.config.status == "approved":
            return True
        if alias is None:
            return False
        return alias == case.config.owner_alias or self._is_admin(alias)

    def list_cases(self):
        with self._cases_lock:
            return [case.summary() for case in self.cases.values() if case.config.status == "approved"]

    def list_pending_cases(self, alias: str):
        if not self._is_admin(alias):
            raise PermissionError("Only admins can review pending cases")
        with self._cases_lock:
            return [case.summary() for case in self.cases.values() if case.config.status == "draft"]

    def get_case(self, case_id: str) -> LoadedCase:
        with self._cases_lock:
            if case_id not in self.cases:
                raise KeyError(f"Unknown case: {case_id}")
            return self.cases[case_id]

    def get_or_create_state(self, case_id: str, player_alias: str) -> PlayerCaseState:
        case = self.get_case(case_id)
        if not self._can_access_case(case, player_alias):
            raise KeyError("Case is not publicly available")
        existing = self.db.load_player_state(case_id, player_alias)
        if existing is not None:
            return existing
        state = PlayerCaseState(
            player_alias=player_alias,
            case_id=case_id,
            unlocked_document_ids=list(case.config.start_state.initial_document_ids),
            unlocked_suspect_ids=list(case.config.start_state.initial_suspect_ids),
            current_objective="Interrogate the known suspects and rescan the archive for what the police missed.",
        )
        self.db.save_player_state(state)
        return state

    def get_case_detail(self, case_id: str, player_alias: str):
        case = self.get_case(case_id)
        if not self._can_access_case(case, player_alias):
            raise KeyError("Case is not publicly available")
        state = self.get_or_create_state(case_id, player_alias)
        return case.to_detail(state)

    def get_save_state(self, case_id: str, player_alias: str) -> SaveStateResponse:
        state = self.get_or_create_state(case_id, player_alias)
        conversations = self.db.load_conversations(case_id, player_alias)
        return SaveStateResponse(state=state, conversations=conversations)

    def search_case(self, case_id: str, player_alias: str, payload: SearchRequest) -> SearchResponse:
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        results = self.retrieval.search(case, state.unlocked_document_ids, payload.query, payload.limit)
        contexts = self.retrieval.derive_contexts(payload.query, [case.documents[result.document_id] for result in results])
        for context in contexts:
            if context not in state.discovered_contexts:
                state.discovered_contexts.append(context)
        self.db.save_player_state(state)
        return SearchResponse(query=payload.query, results=results, discovered_contexts=contexts)

    def _apply_rule_effects(self, state: PlayerCaseState, case: LoadedCase, trigger_type: str, trigger_value: str) -> RescanEffects:
        unlocked_documents: list[str] = []
        unlocked_suspects: list[str] = []
        surfaced_document_ids: list[str] = []
        for rule in case.config.rescan_rules:
            if rule.trigger.type != trigger_type or rule.trigger.value != trigger_value:
                continue
            for document_id in rule.effects.unlock_document_ids:
                if document_id not in state.unlocked_document_ids:
                    state.unlocked_document_ids.append(document_id)
                    unlocked_documents.append(document_id)
            for suspect_id in rule.effects.unlock_suspect_ids:
                if suspect_id not in state.unlocked_suspect_ids:
                    state.unlocked_suspect_ids.append(suspect_id)
                    unlocked_suspects.append(suspect_id)
            for document_id in rule.effects.surface_document_ids:
                if document_id in case.documents:
                    surfaced_document_ids.append(document_id)
        return RescanEffects(
            unlocked_documents=unlocked_documents,
            unlocked_suspects=unlocked_suspects,
            surfaced_document_ids=surfaced_document_ids,
        )

    def _apply_discovered_contexts(
        self,
        state: PlayerCaseState,
        case: LoadedCase,
        contexts: list[str],
        trigger_type: str,
    ) -> RescanEffects:
        unlocked_documents: list[str] = []
        unlocked_suspects: list[str] = []
        surfaced_document_ids: list[str] = []
        for context in contexts:
            if context not in state.discovered_contexts:
                state.discovered_contexts.append(context)
            effects = self._apply_rule_effects(state, case, trigger_type, context)
            unlocked_documents.extend(effects.unlocked_documents)
            unlocked_suspects.extend(effects.unlocked_suspects)
            surfaced_document_ids.extend(effects.surfaced_document_ids)
        return RescanEffects(
            unlocked_documents=list(dict.fromkeys(unlocked_documents)),
            unlocked_suspects=list(dict.fromkeys(unlocked_suspects)),
            surfaced_document_ids=list(dict.fromkeys(surfaced_document_ids)),
        )

    def rescan_case(self, case_id: str, player_alias: str, payload: RescanRequest) -> RescanResponse:
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        focus_contexts = self.retrieval.derive_contexts(payload.focus)
        unlocked_documents: list[str] = []
        unlocked_suspects: list[str] = []
        surfaced_document_ids: list[str] = []
        for context in focus_contexts:
            if context not in state.discovered_contexts:
                state.discovered_contexts.append(context)
        effects = self._apply_discovered_contexts(
            state,
            case,
            list(state.discovered_contexts),
            "context_entity_discovered",
        )
        unlocked_documents.extend(effects.unlocked_documents)
        unlocked_suspects.extend(effects.unlocked_suspects)
        surfaced_document_ids.extend(effects.surfaced_document_ids)

        surface_pool = list(dict.fromkeys(surfaced_document_ids + state.unlocked_document_ids))
        surfaced_results = self.retrieval.surface_from_context(
            case,
            surface_pool,
            state.discovered_contexts + focus_contexts,
        )
        state.rescan_history.append(payload.focus or "Rescan run")
        state.current_objective = "Use the new archive threads to pressure a suspect or strengthen your theory board."
        self.db.save_player_state(state)
        return RescanResponse(
            focus=payload.focus,
            unlocked_documents=unlocked_documents,
            unlocked_suspects=unlocked_suspects,
            surfaced_results=surfaced_results,
            discovered_contexts=state.discovered_contexts,
        )

    def _get_conversation(self, case_id: str, player_alias: str, suspect_id: str) -> ConversationState:
        conversation = self.db.load_conversation(case_id, player_alias, suspect_id)
        return conversation or ConversationState(suspect_id=suspect_id)

    def _save_conversation(self, case_id: str, player_alias: str, conversation: ConversationState) -> None:
        self.db.save_conversation(case_id, player_alias, conversation)

    def _board_node_aliases(self, node_id: str) -> set[str]:
        aliases = {node_id}
        if node_id.startswith("doc_"):
            aliases.add(node_id.removeprefix("doc_"))
        aliases.update(alias.replace("_", "-") for alias in list(aliases))
        return aliases

    def _resolve_suspect(self, case: LoadedCase, state: PlayerCaseState, suspect_id: str) -> SuspectConfig:
        if suspect_id not in state.unlocked_suspect_ids:
            raise KeyError("Suspect is not unlocked")
        return case.suspects[suspect_id]

    def get_talk_grounding(
        self,
        case_id: str,
        player_alias: str,
        suspect_id: str,
        message: str,
        evidence_id: str | None = None,
    ) -> list[SearchResult]:
        """Retrieve supporting archive passages for an interrogation turn."""
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        self._resolve_suspect(case, state, suspect_id)
        evidence = case.documents.get(evidence_id) if evidence_id else None
        query_parts = [message]
        if evidence is not None:
            query_parts.append(evidence.title)
            query_parts.extend(evidence.entity_tags[:3])
        return self.retrieval.retrieve_dialogue_context(
            case,
            state.unlocked_document_ids,
            " ".join(part for part in query_parts if part).strip(),
            evidence=evidence,
            limit=3,
        )

    def begin_interrogation_session(self, case_id: str, player_alias: str, suspect_id: str) -> ConversationState:
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        suspect = self._resolve_suspect(case, state, suspect_id)
        conversation = self._get_conversation(case_id, player_alias, suspect_id)
        if conversation.transcript:
            conversation.memory_summary = self.dialogue.compact_memory_summary(suspect, conversation)
            conversation.transcript = []
        self._save_conversation(case_id, player_alias, conversation)
        return conversation

    def talk_to_suspect(self, case_id: str, player_alias: str, suspect_id: str, message: str, evidence_id: str | None = None) -> DialogueResponse:
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        suspect = self._resolve_suspect(case, state, suspect_id)
        conversation = self._get_conversation(case_id, player_alias, suspect_id)
        evidence = case.documents.get(evidence_id) if evidence_id else None
        grounding_results = self.get_talk_grounding(case_id, player_alias, suspect_id, message, evidence_id=evidence_id)
        outcome = self.dialogue.generate(case, suspect, conversation, state, message, grounding_results, evidence)

        conversation.transcript.append(ConversationTurn(speaker="detective", text=message))
        if evidence_id:
            conversation.confronted_evidence_ids.append(evidence_id)
        conversation.transcript.append(ConversationTurn(speaker=suspect.display_name, text=outcome.reply))
        conversation.trust = max(0, min(100, conversation.trust + outcome.trust_delta))
        conversation.guardedness = max(0, min(100, conversation.guardedness + outcome.guardedness_delta))
        conversation.revealed_fact_ids = list(dict.fromkeys(conversation.revealed_fact_ids + outcome.revealed_fact_ids))
        conversation.memory_summary = f"Topics pressed: {', '.join(outcome.new_context[:4])}" if outcome.new_context else conversation.memory_summary

        state.suspicion_level = max(0, min(100, state.suspicion_level + outcome.suspicion_delta))
        conversation_contexts = self.retrieval.derive_contexts(
            " ".join(
                part
                for part in [
                    message,
                    outcome.reply,
                    " ".join(result.title for result in grounding_results),
                    " ".join(result.snippet for result in grounding_results),
                    evidence.title if evidence else "",
                ]
                if part
            ),
            [evidence] if evidence else None,
        )
        all_contexts = list(dict.fromkeys(outcome.new_context + conversation_contexts))
        effects = self._apply_discovered_contexts(
            state,
            case,
            all_contexts,
            "conversation_context_discovered",
        )
        for context in outcome.new_context:
            if context not in state.discovered_contexts:
                state.discovered_contexts.append(context)
        state.current_objective = "Rescan the archive with what you just learned."
        if effects.unlocked_suspects:
            state.current_objective = "A new person of interest has surfaced. Bring them in or revisit the archive."
        lead_messages = self._build_lead_messages(case, effects, all_contexts)

        self._save_conversation(case_id, player_alias, conversation)
        self.db.save_player_state(state)
        return DialogueResponse(
            suspect_id=suspect_id,
            reply=outcome.reply,
            new_context=outcome.new_context,
            revealed_fact_ids=outcome.revealed_fact_ids,
            grounding_results=grounding_results,
            unlocked_documents=effects.unlocked_documents,
            unlocked_suspects=effects.unlocked_suspects,
            lead_messages=lead_messages,
            suspicion_level=state.suspicion_level,
            conversation=conversation,
        )

    def stream_talk_to_suspect(
        self,
        case_id: str,
        player_alias: str,
        suspect_id: str,
        message: str,
        grounding_results: list[SearchResult] | None = None,
    ):
        """Yield reply tokens for SSE streaming, then persist the streamed reply.

        Uses a single generation: the visible reply is streamed token-by-token, and the
        exact text the player saw is what gets persisted. State deltas (trust, guardedness,
        suspicion, revealed facts) are computed deterministically via the heuristic scorer
        with NO second LLM call, so the streamed reply and the saved reply never diverge.
        """
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        suspect = self._resolve_suspect(case, state, suspect_id)
        conversation = self._get_conversation(case_id, player_alias, suspect_id)
        grounding_results = grounding_results or self.get_talk_grounding(case_id, player_alias, suspect_id, message)

        chunks: list[str] = []
        for token in self.dialogue.stream_reply(case, suspect, conversation, state, message, grounding_results):
            chunks.append(token)
            yield token
        full_reply = "".join(chunks)

        # Deterministic deltas only — reuse the heuristic scorer but keep the streamed text.
        deltas = self.dialogue.score_reply(suspect, conversation, message, grounding_results, None)
        conversation.transcript.append(ConversationTurn(speaker="detective", text=message))
        conversation.transcript.append(ConversationTurn(speaker=suspect.display_name, text=full_reply))
        conversation.trust = max(0, min(100, conversation.trust + deltas.trust_delta))
        conversation.guardedness = max(0, min(100, conversation.guardedness + deltas.guardedness_delta))
        conversation.revealed_fact_ids = list(dict.fromkeys(conversation.revealed_fact_ids + deltas.revealed_fact_ids))
        if deltas.new_context:
            conversation.memory_summary = f"Topics pressed: {', '.join(deltas.new_context[:4])}"
        state.suspicion_level = max(0, min(100, state.suspicion_level + deltas.suspicion_delta))
        conversation_contexts = self.retrieval.derive_contexts(
            " ".join(
                part
                for part in [
                    message,
                    full_reply,
                    " ".join(result.title for result in grounding_results),
                    " ".join(result.snippet for result in grounding_results),
                ]
                if part
            )
        )
        all_contexts = list(dict.fromkeys(deltas.new_context + conversation_contexts))
        effects = self._apply_discovered_contexts(
            state,
            case,
            all_contexts,
            "conversation_context_discovered",
        )
        for context in deltas.new_context:
            if context not in state.discovered_contexts:
                state.discovered_contexts.append(context)
        state.current_objective = "Rescan the archive with what you just learned."
        if effects.unlocked_suspects:
            state.current_objective = "A new person of interest has surfaced. Bring them in or revisit the archive."
        self._save_conversation(case_id, player_alias, conversation)
        self.db.save_player_state(state)
        self._stream_lead_events[(case_id, player_alias, suspect_id)] = {
            "unlocked_documents": effects.unlocked_documents,
            "unlocked_suspects": effects.unlocked_suspects,
            "lead_messages": self._build_lead_messages(case, effects, all_contexts),
        }

    def confront_suspect(self, case_id: str, player_alias: str, suspect_id: str, request: ConfrontRequest) -> DialogueResponse:
        case = self.get_case(case_id)
        evidence = case.documents.get(request.evidence_id)
        message = request.message or f"I want to discuss {evidence.title if evidence else request.evidence_id}."
        return self.talk_to_suspect(case_id, player_alias, suspect_id, message, evidence_id=request.evidence_id)

    def add_board_link(self, case_id: str, player_alias: str, payload: BoardLinkRequest) -> BoardLinkResponse:
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        source_aliases = self._board_node_aliases(payload.source_id)
        target_aliases = self._board_node_aliases(payload.target_id)
        matched_link = next(
            (
                link
                for link in case.config.valid_board_links
                if link.source_id in source_aliases
                and link.target_id in target_aliases
                and link.link_type == payload.link_type
            ),
            None,
        )
        link_id = matched_link.id if matched_link else f"{payload.source_id}-{payload.target_id}-{payload.link_type}"
        if link_id not in state.board_links:
            state.board_links.append(link_id)

        is_valid = matched_link is not None
        unlocked_documents: list[str] = []
        unlocked_suspects: list[str] = []
        if is_valid:
            effects = self._apply_rule_effects(state, case, "board_link_confirmed", link_id)
            unlocked_documents = effects.unlocked_documents
            unlocked_suspects = effects.unlocked_suspects
            state.current_objective = "A new thread has opened. Revisit the archive or pressure the newly relevant suspect."
        self.db.save_player_state(state)
        return BoardLinkResponse(
            is_valid=is_valid,
            link_id=link_id,
            unlocked_documents=unlocked_documents,
            unlocked_suspects=unlocked_suspects,
            board_links=state.board_links,
        )

    def toggle_pin(self, case_id: str, player_alias: str, payload: TogglePinRequest) -> PlayerCaseState:
        state = self.get_or_create_state(case_id, player_alias)
        if payload.document_id in state.pinned_evidence_ids:
            state.pinned_evidence_ids.remove(payload.document_id)
        else:
            state.pinned_evidence_ids.append(payload.document_id)
        self.db.save_player_state(state)
        return state

    def submit_theory(self, case_id: str, player_alias: str, payload: SubmitTheoryRequest) -> SubmitTheoryResponse:
        state = self.get_or_create_state(case_id, player_alias)
        case = self.get_case(case_id)
        minimum = case.config.submission.min_evidence_count
        if len(payload.evidence_ids) < minimum:
            raise ValueError(f"At least {minimum} evidence items are required")
        excerpt = f"{payload.motive_text[:110]} | {payload.timeline_text[:110]}"
        self.db.save_submission(
            case_id=case_id,
            player_alias=player_alias,
            culprit_id=payload.culprit_id,
            motive_text=payload.motive_text,
            timeline_text=payload.timeline_text,
            evidence_ids=payload.evidence_ids,
            excerpt=excerpt,
        )
        state.current_objective = "Review the community split and compare your theory with other detectives."
        self.db.save_player_state(state)
        stats = self.db.get_community_stats(case_id)
        return SubmitTheoryResponse(saved=True, stats=stats)

    def get_community_stats(self, case_id: str, player_alias: str) -> CommunityStatsResponse:
        case = self.get_case(case_id)
        if not self._can_access_case(case, player_alias):
            raise KeyError("Case is not publicly available")
        return self.db.get_community_stats(case_id)
