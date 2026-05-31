from __future__ import annotations

import json
import re
from collections.abc import Generator
from dataclasses import dataclass
from urllib import error, request

from ..config import Settings
from ..models import CaseDocument, ConversationState, LoadedCase, PlayerCaseState, SuspectConfig
from .retrieval import RetrievalService


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
        evidence: CaseDocument | None = None,
    ) -> DialogueOutcome:
        outcome = self._call_ollama(case, suspect, conversation, state, player_message, evidence)
        if outcome is not None:
            return outcome
        return self._heuristic_response(suspect, conversation, player_message, evidence)

    def _call_ollama(
        self,
        case: LoadedCase,
        suspect: SuspectConfig,
        conversation: ConversationState,
        state: PlayerCaseState,
        player_message: str,
        evidence: CaseDocument | None,
    ) -> DialogueOutcome | None:
        system_prompt = case.prompts.get(
            "interrogation_system",
            "You are a suspect in a detective game. Stay consistent with the supplied facts and answer only as the suspect.",
        )
        prompt_payload = {
            "suspect": suspect.model_dump(mode="json"),
            "conversation": conversation.model_dump(mode="json"),
            "state": {
                "suspicion_level": state.suspicion_level,
                "discovered_contexts": state.discovered_contexts,
            },
            "evidence": evidence.model_dump(mode="json") if evidence else None,
            "player_message": player_message,
            "instructions": {
                "format": "Return strict JSON with reply, new_context, revealed_fact_ids, suspicion_delta, guardedness_delta, trust_delta.",
                "constraints": [
                    "Do not contradict private facts or non-negotiables.",
                    "Do not reveal hidden truth unless pressure or evidence justifies it.",
                    "Keep replies concise and characterful.",
                ],
            },
        }
        req_body = json.dumps(
            {
                "model": self.settings.ollama_chat_model,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(prompt_payload)},
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
            with request.urlopen(req, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return None

        content = body.get("message", {}).get("content", "")
        if not content:
            return None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        return DialogueOutcome(
            reply=parsed.get("reply", ""),
            new_context=parsed.get("new_context", []),
            revealed_fact_ids=parsed.get("revealed_fact_ids", []),
            suspicion_delta=int(parsed.get("suspicion_delta", 0)),
            guardedness_delta=int(parsed.get("guardedness_delta", 0)),
            trust_delta=int(parsed.get("trust_delta", 0)),
        )

    def score_reply(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        evidence: CaseDocument | None,
    ) -> DialogueOutcome:
        """Compute deterministic state deltas without an LLM call.

        Returns a full DialogueOutcome; callers that already have a reply (e.g. streaming)
        use only the delta fields and discard the heuristic reply text.
        """
        return self._heuristic_response(suspect, conversation, player_message, evidence)

    def _heuristic_response(
        self,
        suspect: SuspectConfig,
        conversation: ConversationState,
        player_message: str,
        evidence: CaseDocument | None,
    ) -> DialogueOutcome:
        triggers = [trigger.lower() for trigger in suspect.dialogue_rules.pressure_triggers]
        message_tokens = _tokens(player_message)
        matched_trigger = next((trigger for trigger in triggers if trigger in player_message.lower()), None)
        revealed_fact_ids: list[str] = []
        reply = f"{suspect.display_name} remains {suspect.dialogue_rules.baseline_tone}."
        new_context: list[str] = []
        suspicion_delta = 2 if "why" in message_tokens or "how" in message_tokens else 0
        guardedness_delta = 1
        trust_delta = 0

        evidence_text = evidence.body if evidence else ""
        is_pressure = matched_trigger is not None or bool(_tokens(evidence_text) & message_tokens)

        available_facts = suspect.private_truth.facts_known + suspect.private_truth.secrets
        if is_pressure and len(conversation.revealed_fact_ids) < len(available_facts):
            fact_index = len(conversation.revealed_fact_ids)
            revealed = available_facts[fact_index]
            revealed_fact_ids.append(f"fact_{fact_index}")
            new_context = self.retrieval_service.derive_contexts(revealed)
            reply = f"{suspect.display_name} hesitates, then admits: {revealed}"
            guardedness_delta = 4
            trust_delta = -1 if suspect.private_truth.secrets else 1
            suspicion_delta += 6
        elif evidence:
            reply = (
                f"{suspect.display_name} studies {evidence.title} and replies carefully. "
                f"'{suspect.dialogue_rules.lie_strategy.capitalize()}, detective. That document proves less than you think.'"
            )
            new_context = self.retrieval_service.derive_contexts(evidence.body, [evidence])
            guardedness_delta = 5
            suspicion_delta += 5
        else:
            summary = suspect.public_profile.summary
            reply = f"{suspect.display_name} says, '{summary} I have already told the police what I know.'"
            new_context = self.retrieval_service.derive_contexts(summary)

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
            "suspect": {"id": suspect.id, "display_name": suspect.display_name, "public_profile": suspect.public_profile.model_dump()},
            "player_message": player_message,
            "evidence_title": evidence.title if evidence else None,
        }
        req_body = json.dumps(
            {
                "model": self.settings.ollama_chat_model,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(prompt_payload)},
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
            with request.urlopen(req, timeout=30) as resp:
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
                        yield token
                    if chunk.get("done"):
                        break
        except (error.URLError, TimeoutError):
            outcome = self._heuristic_response(suspect, conversation, player_message, evidence)
            yield outcome.reply

