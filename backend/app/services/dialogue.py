from __future__ import annotations

import logging
import re
from collections.abc import Generator
from dataclasses import dataclass

from ..config import Settings
from ..models import CaseDocument, ConversationState, LoadedCase, PlayerCaseState, SearchResult, SuspectConfig
from .providers import ProviderUnavailable, create_chat_provider
from .retrieval import RetrievalService

logger = logging.getLogger(__name__)

_LEAK_PATTERNS = (
    "answers in a ",
    "replies in a ",
    "speaking style",
    "verbal tells",
    " cadence",
    " voice",
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


@dataclass
class DialogueOutcome:
    reply: str
    new_context: list[str]
    revealed_fact_ids: list[str]
    suspicion_delta: int
    guardedness_delta: int
    trust_delta: int


class DialogueService:
    def __init__(self, settings: Settings, retrieval_service: RetrievalService) -> None:
        self.settings = settings
        self.retrieval_service = retrieval_service
        self.provider = create_chat_provider(settings)

    def generate(
        self,
        case: LoadedCase,
        suspect: SuspectConfig,
        conversation: ConversationState,
        state: PlayerCaseState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None = None,
    ) -> DialogueOutcome:
        heuristic = self._heuristic_response(suspect, conversation, player_message, grounding_results, evidence)
        reply = self._call_ollama(case, suspect, conversation, state, player_message, grounding_results, evidence)
        if reply is None:
            return heuristic
        return self.score_reply(suspect, conversation, player_message, grounding_results, evidence, reply=reply)

    def _call_ollama(
        self,
        case: LoadedCase,
        suspect: SuspectConfig,
        conversation: ConversationState,
        state: PlayerCaseState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> str | None:
        system_prompt = case.prompts.get(
            "interrogation_system",
            "You are a suspect in a detective game. Stay consistent with the supplied facts and answer only as the suspect.",
        )
        prompt_payload = self._build_prompt_payload(
            suspect,
            conversation,
            state,
            player_message,
            grounding_results,
            evidence,
        )
        try:
            content = self.provider.complete(system_prompt, prompt_payload)
        except ProviderUnavailable as exc:
            logger.warning("Dialogue provider %s failed; using heuristic fallback: %s", self.provider.name, exc)
            return None
        if not content:
            logger.warning("Dialogue provider returned empty content; using heuristic fallback")
            return None
        sanitized_reply = self._sanitize_reply(content, suspect)
        if sanitized_reply is None or self._leaks_unrevealed_fact(
            sanitized_reply,
            suspect,
            conversation,
            player_message,
            grounding_results,
            evidence,
        ):
            logger.warning("Dialogue Ollama reply leaked metadata; using heuristic fallback")
            return None
        return sanitized_reply

    def score_reply(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
        reply: str | None = None,
    ) -> DialogueOutcome:
        """Compute deterministic state deltas and align reveals with the visible reply."""
        outcome = self._heuristic_response(suspect, conversation, player_message, grounding_results, evidence)
        if reply is None:
            return outcome
        revealed_fact_ids = [
            fact_id
            for fact_id in outcome.revealed_fact_ids
            if self._reply_contains_fact(reply, self._fact_text(suspect, fact_id))
        ]
        new_context = outcome.new_context
        if outcome.revealed_fact_ids and not revealed_fact_ids:
            new_context = self.retrieval_service.derive_contexts(
                " ".join(result.snippet for result in grounding_results),
                [evidence] if evidence else None,
            )
        return DialogueOutcome(
            reply=reply,
            new_context=new_context,
            revealed_fact_ids=revealed_fact_ids,
            suspicion_delta=outcome.suspicion_delta,
            guardedness_delta=outcome.guardedness_delta if revealed_fact_ids or not outcome.revealed_fact_ids else 2,
            trust_delta=outcome.trust_delta if revealed_fact_ids or not outcome.revealed_fact_ids else 0,
        )

    def _heuristic_response(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> DialogueOutcome:
        personality = suspect.personality_profile
        message_tokens = _tokens(player_message)
        revealed_fact_ids: list[str] = []
        reply = self._baseline_reply(suspect)
        new_context: list[str] = []
        suspicion_delta = 2 if "why" in message_tokens or "how" in message_tokens else 0
        guardedness_delta = 1
        trust_delta = 0

        protective_pressure = self._is_protective_pressure(suspect, player_message, grounding_results, evidence)
        if protective_pressure:
            guardedness_delta += 2
            trust_delta -= 1
            suspicion_delta += 2

        available_facts = suspect.private_truth.facts_known + suspect.private_truth.secrets
        fact_index = self._eligible_fact_index(suspect, conversation, player_message, grounding_results, evidence)
        if fact_index is not None and fact_index < len(available_facts):
            revealed = available_facts[fact_index]
            revealed_fact_ids.append(f"fact_{fact_index}")
            new_context = self.retrieval_service.derive_contexts(revealed)
            reply = self._revealed_fact_reply(suspect, conversation, revealed)
            guardedness_delta = 4
            trust_delta = -1 if suspect.private_truth.secrets else 1
            suspicion_delta += 6
        elif evidence:
            reply = self._evidence_reply(suspect, conversation, evidence.title)
            new_context = self.retrieval_service.derive_contexts(evidence.body, [evidence])
            guardedness_delta = 5
            suspicion_delta += 5
        elif grounding_results:
            primary = grounding_results[0]
            reply = self._grounded_reply(suspect, conversation, player_message, primary.title)
            new_context = self.retrieval_service.derive_contexts(
                " ".join(result.snippet for result in grounding_results),
            )
            guardedness_delta = 2
            suspicion_delta += 3
        else:
            reply = self._ungrounded_reply(suspect, conversation, player_message)
            new_context = self.retrieval_service.derive_contexts(suspect.public_profile.summary)

        if protective_pressure and personality.protective_reason:
            new_context = list(
                dict.fromkeys(
                    new_context + self.retrieval_service.derive_contexts(personality.protective_reason)
                )
            )

        return DialogueOutcome(
            reply=reply,
            new_context=new_context,
            revealed_fact_ids=revealed_fact_ids,
            suspicion_delta=suspicion_delta,
            guardedness_delta=guardedness_delta,
            trust_delta=trust_delta,
        )

    def stream_reply(
        self,
        case: LoadedCase,
        suspect: SuspectConfig,
        conversation: ConversationState,
        state: PlayerCaseState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None = None,
    ) -> Generator[str, None, None]:
        """Yield reply tokens as they arrive from Ollama (non-JSON stream mode).

        Falls back to yielding the full heuristic reply in one chunk when Ollama
        is unavailable so the SSE endpoint always produces output.
        """
        system_prompt = case.prompts.get(
            "interrogation_system",
            "You are a suspect in a detective game. Stay consistent with the supplied facts and answer only as the suspect.",
        )
        prompt_payload = self._build_prompt_payload(
            suspect, conversation, state, player_message, grounding_results, evidence
        )
        try:
            raw_reply = "".join(self.provider.stream(system_prompt, prompt_payload))
            sanitized = self._sanitize_reply(raw_reply, suspect)
            if sanitized is None or self._leaks_unrevealed_fact(
                sanitized,
                suspect,
                conversation,
                player_message,
                grounding_results,
                evidence,
            ):
                raise ProviderUnavailable("reply failed policy validation")
            for token in re.findall(r"\S+\s*", sanitized):
                yield token
        except ProviderUnavailable as exc:
            logger.warning("Dialogue provider stream failed; using heuristic fallback: %s", exc)
            outcome = self._heuristic_response(suspect, conversation, player_message, grounding_results, evidence)
            yield outcome.reply

    def _baseline_reply(self, suspect: SuspectConfig) -> str:
        return self._spoken_reply(
            suspect,
            "I have already told you what I can. Ask something specific.",
            include_catchphrase=False,
        )

    def _spoken_reply(
        self,
        suspect: SuspectConfig,
        content: str,
        include_catchphrase: bool = True,
    ) -> str:
        reply = content.strip()
        reply = re.sub(r"\s+", " ", reply)
        return reply

    def _build_prompt_payload(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        state: PlayerCaseState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> dict[str, object]:
        personality = suspect.personality_profile
        return {
            "suspect": {
                "name": suspect.display_name,
                "role": suspect.public_profile.role,
                "public_summary": suspect.public_profile.summary,
                "tone": suspect.dialogue_rules.baseline_tone,
                "lie_strategy": suspect.dialogue_rules.lie_strategy,
                "traits": personality.traits[:4],
                "speaking_style": personality.speaking_style,
                "verbal_tells": personality.verbal_tells[:2],
                "outward_goal": personality.outward_goal,
                "protective_target": personality.protective_target,
                "protective_reason": personality.protective_reason,
                "allowed_facts": self._allowed_facts(
                    suspect,
                    conversation,
                    player_message,
                    grounding_results,
                    evidence,
                ),
                "non_negotiables": suspect.private_truth.non_negotiables,
                "previous_session_summary": conversation.memory_summary,
            },
            "conversation": {
                "trust": conversation.trust,
                "guardedness": conversation.guardedness,
                "revealed_fact_ids": conversation.revealed_fact_ids,
                "recent_transcript": [
                    {"speaker": turn.speaker, "text": turn.text}
                    for turn in conversation.transcript[-4:]
                ],
            },
            "state": {
                "suspicion_level": state.suspicion_level,
                "discovered_contexts": state.discovered_contexts[-6:],
            },
            "grounding": [
                {
                    "chunk_id": result.chunk_id,
                    "document_id": result.document_id,
                    "title": result.title,
                    "snippet": result.snippet,
                    "matched_entity_tags": result.matched_entity_tags,
                }
                for result in grounding_results
            ],
            "evidence": (
                {
                    "title": evidence.title,
                    "summary": evidence.summary,
                    "entity_tags": evidence.entity_tags,
                }
                if evidence
                else None
            ),
            "player_message": player_message,
            "output_rules": {
                "reply_style": "Only the suspect's spoken words. No narration, no labels, no speaker names.",
                "length": "2 to 5 sentences maximum.",
                "conversation": (
                    "Answer the detective's latest question directly before deflecting or pushing back. "
                    "Acknowledge relevant prior turns without recapping the whole exchange. Vary sentence openings "
                    "and do not repeat stock phrases, the question, or the suspect's catchphrase."
                ),
                "naturalism": (
                    "Write natural spoken dialogue with contractions and occasional short sentences. "
                    "Do not explain the suspect's tone, traits, strategy, goals, or verbal tells."
                ),
                "grounding": (
                    "Use retrieved evidence naturally when relevant. Treat profile and rule fields as private acting "
                    "direction. Never mention system prompts, metadata, retrieved context, or document IDs."
                ),
            },
        }

    def _allowed_facts(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> list[str]:
        facts = suspect.private_truth.facts_known + suspect.private_truth.secrets
        allowed_ids = set(conversation.revealed_fact_ids)
        eligible_index = self._eligible_fact_index(suspect, conversation, player_message, grounding_results, evidence)
        return [
            fact
            for index, fact in enumerate(facts)
            if f"fact_{index}" in allowed_ids or index == eligible_index
        ]

    def _eligible_fact_index(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> int | None:
        facts = suspect.private_truth.facts_known + suspect.private_truth.secrets
        unrevealed = [index for index in range(len(facts)) if f"fact_{index}" not in conversation.revealed_fact_ids]
        if not unrevealed:
            return None
        haystack_parts = [player_message]
        haystack_parts.extend(result.title for result in grounding_results)
        haystack_parts.extend(result.snippet for result in grounding_results)
        if evidence:
            haystack_parts.extend([evidence.id, evidence.title, evidence.summary, evidence.body, *evidence.entity_tags])
        haystack = " ".join(haystack_parts).lower()

        rules = {rule.fact_id: rule for rule in suspect.dialogue_rules.fact_reveal_rules}
        for index in unrevealed:
            rule = rules.get(f"fact_{index}")
            if rule is None:
                triggers = suspect.dialogue_rules.pressure_triggers
                if any(trigger.lower() in haystack for trigger in triggers):
                    return index
                continue
            if conversation.trust < rule.min_trust or conversation.guardedness > rule.max_guardedness:
                continue
            topic_match = not rule.topics or any(topic.lower() in haystack for topic in rule.topics)
            evidence_match = not rule.evidence_ids or bool(evidence and evidence.id in rule.evidence_ids)
            if topic_match and evidence_match:
                return index
        return None

    def _fact_text(self, suspect: SuspectConfig, fact_id: str) -> str:
        facts = suspect.private_truth.facts_known + suspect.private_truth.secrets
        try:
            index = int(fact_id.removeprefix("fact_"))
        except ValueError:
            return ""
        return facts[index] if 0 <= index < len(facts) else ""

    def _reply_contains_fact(self, reply: str, fact: str) -> bool:
        meaningful = {token for token in _tokens(fact) if len(token) > 4}
        if not meaningful:
            return False
        overlap = meaningful & _tokens(reply)
        return len(overlap) >= min(3, max(1, (len(meaningful) + 1) // 2))

    def _leaks_unrevealed_fact(
        self,
        reply: str,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> bool:
        facts = suspect.private_truth.facts_known + suspect.private_truth.secrets
        allowed_facts = set(self._allowed_facts(suspect, conversation, player_message, grounding_results, evidence))
        reply_tokens = _tokens(reply)
        for fact in facts:
            if fact in allowed_facts:
                continue
            meaningful = {token for token in _tokens(fact) if len(token) > 5}
            if len(meaningful & reply_tokens) >= min(3, max(1, len(meaningful))):
                return True
        return False

    def _build_stream_suspect_payload(self, suspect: SuspectConfig) -> dict[str, object]:
        personality = suspect.personality_profile
        return {
            "id": suspect.id,
            "display_name": suspect.display_name,
            "role": suspect.public_profile.role,
            "public_summary": suspect.public_profile.summary,
            "tone": suspect.dialogue_rules.baseline_tone,
            "lie_strategy": suspect.dialogue_rules.lie_strategy,
            "traits": personality.traits[:4],
            "protective_target": personality.protective_target,
            "speaking_style": personality.speaking_style,
        }

    def _sanitize_reply(self, reply: str, suspect: SuspectConfig) -> str | None:
        cleaned = reply.strip().strip('"')
        quoted = re.findall(r'"([^"]+)"', cleaned)
        if quoted:
            cleaned = quoted[0].strip()
        cleaned = re.sub(rf"^{re.escape(suspect.display_name)}\s*:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"^[^.?!\"]*\b(?:answers|replies|says|glances|studies)\b[^.?!\"]*[.:]\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.strip().strip('"')
        cleaned = re.sub(r"\s+", " ", cleaned)
        lowered = cleaned.lower()
        catchphrase = suspect.personality_profile.catchphrase.strip()
        if catchphrase and lowered.startswith(catchphrase.lower()):
            cleaned = cleaned[len(catchphrase) :].strip(" .,:;!-")
            cleaned = cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned
            lowered = cleaned.lower()
        if not cleaned:
            return None
        if cleaned.startswith(f"{suspect.display_name} "):
            return None
        if any(pattern in lowered for pattern in _LEAK_PATTERNS):
            return None
        if "personality profile" in lowered or "private truth" in lowered:
            return None
        return cleaned

    def compact_memory_summary(self, suspect: SuspectConfig, conversation: ConversationState) -> str:
        previous = conversation.memory_summary.strip()
        detective_lines = [turn.text for turn in conversation.transcript if turn.speaker == "detective"]
        suspect_lines = [turn.text for turn in conversation.transcript if turn.speaker != "detective"]
        topics = self.retrieval_service.derive_contexts(" ".join(detective_lines + suspect_lines))
        unique_topics = list(dict.fromkeys(topics))
        topic_text = ", ".join(unique_topics[:4]) if unique_topics else "timeline and inconsistencies"
        reveal_text = ", ".join(conversation.revealed_fact_ids[-2:]) if conversation.revealed_fact_ids else ""
        evidence_text = ", ".join(conversation.confronted_evidence_ids[-2:]) if conversation.confronted_evidence_ids else ""

        segments: list[str] = []
        if previous:
            segments.append(previous)
        segments.append(f"Pressed {suspect.display_name} on {topic_text}.")
        if reveal_text:
            segments.append(f"Revealed threads: {reveal_text}.")
        if evidence_text:
            segments.append(f"Confronted with {evidence_text}.")
        summary = " ".join(segment for segment in segments if segment).strip()
        return summary[:420]

    def _lie_opening(self, suspect: SuspectConfig) -> str:
        strategy = suspect.dialogue_rules.lie_strategy.lower()
        if "deny" in strategy:
            return "No. That isn't what happened. "
        if "deflect" in strategy:
            return "You're asking the wrong question. "
        if "minimize" in strategy:
            return "You're making too much of an administrative detail. "
        if "admit fragments" in strategy:
            return "You're only seeing part of the picture. "
        return "You're reaching. "

    def _revealed_fact_reply(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        revealed: str,
    ) -> str:
        openings = (
            "Fine. Here's what I know:",
            "All right. This is the part I held back:",
            "You want the truth? Here it is:",
        )
        opening = openings[self._reply_variant(conversation, len(openings))]
        closing = (
            "That's all I can tell you.",
            "Don't turn that into something it isn't.",
            "I'm not going any further than that.",
        )[self._reply_variant(conversation, 3, offset=1)]
        return self._spoken_reply(suspect, f"{opening} {revealed} {closing}", include_catchphrase=False)

    def _evidence_reply(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        evidence_title: str,
    ) -> str:
        strategy = suspect.dialogue_rules.lie_strategy.lower()
        if "deny" in strategy:
            core = f"I've seen {evidence_title}. It doesn't put me where you're trying to put me."
        elif "deflect" in strategy:
            core = f"{evidence_title} raises a question, but it doesn't answer the one you're asking."
        elif "minimize" in strategy:
            core = f"{evidence_title} records an irregularity, not a crime."
        elif "admit fragments" in strategy:
            core = f"There's something useful in {evidence_title}, yes. You're still missing why it matters."
        else:
            core = f"I know what {evidence_title} says. It proves less than you think."
        return self._join_pushback(suspect, conversation, core)

    def _grounded_reply(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        source_title: str,
    ) -> str:
        intent = self._question_intent(player_message)
        repeated = self._is_repeated_topic(conversation, player_message)
        prefix = "We've already been over this. " if repeated else ""
        strategy = suspect.dialogue_rules.lie_strategy.lower()

        if intent == "accusation":
            core = f"{prefix}No. {source_title} doesn't make your accusation true."
        elif intent == "why":
            core = f"{prefix}Because {source_title} leaves out the decisions people made around it."
        elif intent == "timeline":
            core = f"{prefix}The timeline in {source_title} is incomplete. That's the honest answer."
        elif intent == "person":
            core = f"{prefix}I know what {source_title} suggests about them. Suggestion isn't proof."
        elif "deflect" in strategy:
            core = f"{prefix}You're reading too much into {source_title}. Ask what it actually establishes."
        elif "minimize" in strategy:
            core = f"{prefix}{source_title} makes a routine detail look suspicious after the fact."
        elif "admit fragments" in strategy:
            core = f"{prefix}{source_title} has one part right. I'm not convinced you understand which part."
        else:
            core = f"{prefix}I know what {source_title} suggests, but it leaves out context."
        return self._join_pushback(suspect, conversation, core)

    def _ungrounded_reply(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
    ) -> str:
        intent = self._question_intent(player_message)
        repeated = self._is_repeated_topic(conversation, player_message)
        if repeated:
            core = "You're asking me the same thing again. My answer hasn't changed."
        elif intent == "accusation":
            core = f"{self._lie_opening(suspect)}If you have evidence, show it to me."
        elif intent == "why":
            core = "I can't explain a decision you haven't identified. Be specific."
        elif intent == "timeline":
            core = "Give me a time and a place, and I'll tell you what I remember."
        elif intent == "person":
            core = "Ask me what you actually want to know about them."
        else:
            core = "That's too broad. Ask me about a person, a place, or a specific record."
        return self._join_pushback(suspect, conversation, core)

    def _join_pushback(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        core: str,
    ) -> str:
        pushback = self._protective_pushback(suspect)
        if not pushback or self._reply_variant(conversation, 3) == 0:
            return self._spoken_reply(suspect, core, include_catchphrase=False)
        return self._spoken_reply(suspect, f"{core} {pushback}", include_catchphrase=False)

    def _question_intent(self, player_message: str) -> str:
        tokens = _tokens(player_message)
        lowered = player_message.lower()
        if tokens & {"accuse", "accusing", "culprit", "guilty", "killed", "murdered"} or "did you do it" in lowered:
            return "accusation"
        if tokens & {"when", "where", "timeline", "alibi"}:
            return "timeline"
        if tokens & {"who", "he", "she", "they", "them"}:
            return "person"
        if "why" in tokens or "motive" in tokens:
            return "why"
        return "general"

    def _is_repeated_topic(self, conversation: ConversationState, player_message: str) -> bool:
        current = {token for token in _tokens(player_message) if len(token) > 3}
        if not current:
            return False
        previous_questions = [
            turn.text
            for turn in conversation.transcript[-6:]
            if turn.speaker.lower() == "detective"
        ]
        return any(len(current & _tokens(question)) >= min(2, len(current)) for question in previous_questions)

    def _reply_variant(self, conversation: ConversationState, count: int, offset: int = 0) -> int:
        suspect_turns = sum(1 for turn in conversation.transcript if turn.speaker.lower() != "detective")
        return (suspect_turns + offset) % count

    def _protective_pushback(self, suspect: SuspectConfig) -> str:
        target = suspect.personality_profile.protective_target.strip()
        if not target:
            return ""
        return f"I am not going to drag {target} into speculation."

    def _is_protective_pressure(
        self,
        suspect: SuspectConfig,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> bool:
        target = suspect.personality_profile.protective_target.strip()
        if not target:
            return False
        haystack_parts = [player_message]
        if evidence is not None:
            haystack_parts.extend([evidence.title, evidence.body, " ".join(evidence.entity_tags)])
        haystack_parts.extend(result.title for result in grounding_results)
        haystack_parts.extend(result.snippet for result in grounding_results)
        haystack = " ".join(haystack_parts).lower()
        return target.lower() in haystack
