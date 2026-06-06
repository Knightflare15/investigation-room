from __future__ import annotations

import json
import logging
import re
from collections.abc import Generator
from dataclasses import dataclass
from urllib import error, request

from ..config import Settings
from ..models import CaseDocument, ConversationState, LoadedCase, PlayerCaseState, SearchResult, SuspectConfig
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
        return DialogueOutcome(
            reply=reply,
            new_context=heuristic.new_context,
            revealed_fact_ids=heuristic.revealed_fact_ids,
            suspicion_delta=heuristic.suspicion_delta,
            guardedness_delta=heuristic.guardedness_delta,
            trust_delta=heuristic.trust_delta,
        )

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
        req_body = json.dumps(
            {
                "model": self.settings.ollama_chat_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Reply only with the suspect's spoken words. No JSON. No narration. No speaker labels or stage directions.\n"
                            + json.dumps(prompt_payload, separators=(",", ":"))
                        ),
                    },
                ],
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self.settings.ollama_base_url}/api/chat",
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.ollama_chat_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Dialogue Ollama request failed; using heuristic fallback: %s", exc)
            return None

        content = body.get("message", {}).get("content", "")
        if not content:
            logger.warning("Dialogue Ollama returned empty content; using heuristic fallback")
            return None
        sanitized_reply = self._sanitize_reply(content, suspect)
        if sanitized_reply is None:
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
    ) -> DialogueOutcome:
        """Compute deterministic state deltas without an LLM call.

        Returns a full DialogueOutcome; callers that already have a reply (e.g. streaming)
        use only the delta fields and discard the heuristic reply text.
        """
        return self._heuristic_response(suspect, conversation, player_message, grounding_results, evidence)

    def _heuristic_response(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        grounding_results: list[SearchResult],
        evidence: CaseDocument | None,
    ) -> DialogueOutcome:
        personality = suspect.personality_profile
        triggers = [trigger.lower() for trigger in suspect.dialogue_rules.pressure_triggers]
        message_tokens = _tokens(player_message)
        matched_trigger = next((trigger for trigger in triggers if trigger in player_message.lower()), None)
        revealed_fact_ids: list[str] = []
        reply = self._baseline_reply(suspect)
        new_context: list[str] = []
        suspicion_delta = 2 if "why" in message_tokens or "how" in message_tokens else 0
        guardedness_delta = 1
        trust_delta = 0

        evidence_text = evidence.body if evidence else ""
        is_pressure = matched_trigger is not None or bool(_tokens(evidence_text) & message_tokens)
        protective_pressure = self._is_protective_pressure(suspect, player_message, grounding_results, evidence)
        if protective_pressure:
            guardedness_delta += 2
            trust_delta -= 1
            suspicion_delta += 2

        available_facts = suspect.private_truth.facts_known + suspect.private_truth.secrets
        if is_pressure and len(conversation.revealed_fact_ids) < len(available_facts):
            fact_index = len(conversation.revealed_fact_ids)
            revealed = available_facts[fact_index]
            revealed_fact_ids.append(f"fact_{fact_index}")
            new_context = self.retrieval_service.derive_contexts(revealed)
            reply = self._spoken_reply(
                suspect,
                f"{revealed} That is all I am saying about it.",
                include_catchphrase=False,
            )
            guardedness_delta = 4
            trust_delta = -1 if suspect.private_truth.secrets else 1
            suspicion_delta += 6
        elif evidence:
            reply = self._spoken_reply(
                suspect,
                (
                    f"{self._lie_opening(suspect)}That document proves less than you think. "
                    f"{self._protective_pushback(suspect)}"
                ).strip(),
                include_catchphrase=True,
            )
            new_context = self.retrieval_service.derive_contexts(evidence.body, [evidence])
            guardedness_delta = 5
            suspicion_delta += 5
        elif grounding_results:
            primary = grounding_results[0]
            reply = self._spoken_reply(
                suspect,
                (
                    f"I know what those records suggest, but they leave out context. "
                    f"{self._protective_pushback(suspect)}"
                ),
                include_catchphrase=True,
            )
            new_context = self.retrieval_service.derive_contexts(
                " ".join(result.snippet for result in grounding_results),
            )
            guardedness_delta = 2
            suspicion_delta += 3
        else:
            reply = self._spoken_reply(
                suspect,
                (
                    "I have already told the police what I know. "
                    f"{self._protective_pushback(suspect)}Ask a direct question if you want a direct answer."
                ),
                include_catchphrase=not conversation.transcript,
            )
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
        prompt_payload = {
            "suspect": self._build_stream_suspect_payload(suspect),
            "player_message": player_message,
            "previous_session_summary": conversation.memory_summary,
            "trust": conversation.trust,
            "guardedness": conversation.guardedness,
            "evidence_title": evidence.title if evidence else None,
            "grounding": [
                {
                    "chunk_id": result.chunk_id,
                    "document_id": result.document_id,
                    "title": result.title,
                    "snippet": result.snippet,
                }
                for result in grounding_results
            ],
        }
        req_body = json.dumps(
            {
                "model": self.settings.ollama_chat_model,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Reply only with the suspect's spoken words. No JSON. No narration. No stage directions.\n"
                            + json.dumps(prompt_payload, separators=(",", ":"))
                        ),
                    },
                ],
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self.settings.ollama_base_url}/api/chat",
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.ollama_stream_timeout_seconds) as resp:
                saw_token = False
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        saw_token = True
                        yield token
                    if chunk.get("done"):
                        break
                if not saw_token:
                    raise error.URLError("empty Ollama stream")
        except (error.URLError, TimeoutError) as exc:
            logger.warning("Dialogue Ollama stream failed; using heuristic fallback: %s", exc)
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
                "known_facts": suspect.private_truth.facts_known,
                "secrets": suspect.private_truth.secrets,
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
                "grounding": "Use the retrieved evidence when relevant, but do not mention system prompts or style metadata.",
            },
        }

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
            return "That is not what happened. "
        if "deflect" in strategy:
            return "You are asking the wrong question. "
        if "minimize" in strategy:
            return "You are making too much of an administrative detail. "
        if "admit fragments" in strategy:
            return "You are only seeing part of the picture. "
        return "You are reaching. "

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
