from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .registry import ASSESSMENTS, get_fields
from .routing import (
    ASSISTANT_FOLLOWUP_PREFIX,
    DecisionPolicyError,
    DecisionPolicyValidator,
    Router,
    RulesRouter,
)
from .safety import screen_for_emergency
from .schemas import Locale, OrchestrationDecision, TriageResponse
from .security import TokenCodec
from .tool_registry import SpecialistToolRegistry

DISCLAIMER = "Educational screening only — not a diagnosis or medical advice."


@dataclass
class TriageState:
    session_id: str
    locale: str
    messages: list[str]
    condition: str | None = None
    known_fields: dict | None = None
    field_evidence: dict | None = None

    def as_payload(self) -> dict:
        return {
            "kind": "triage",
            "session_id": self.session_id,
            "locale": self.locale,
            "messages": self.messages[-24:],
            "condition": self.condition,
            "known_fields": self.known_fields or {},
            "field_evidence": self.field_evidence or {},
        }


class TriageOrchestrator:
    def __init__(
        self,
        codec: TokenCodec,
        registry: SpecialistToolRegistry | None = None,
        router: Router | None = None,
        state_ttl_seconds: int = 1800,
    ):
        self.codec = codec
        if registry is None:
            registry = SpecialistToolRegistry(Path(__file__).resolve().parents[1] / "artifacts")
        self.registry = registry
        self.router = router or RulesRouter(registry)
        self.state_ttl_seconds = state_ttl_seconds
        self.policy = DecisionPolicyValidator(registry)

    def _state_token(self, state: TriageState) -> str:
        return self.codec.encode(state.as_payload(), ttl_seconds=self.state_ttl_seconds)

    @staticmethod
    def _copy(locale: Locale | str, key: str, condition: str | None = None) -> str:
        language = locale.value if isinstance(locale, Locale) else locale
        name = ASSESSMENTS.get(condition or "", {}).get("name", "assessment")
        content = {
            "en": {
                "emergency": "Your description may contain an emergency warning sign. Call 112 now or go to the nearest emergency department. Do not continue this screening or wait for an AI result.",
                "ready": f"I can help structure the {name.lower()} screening. Complete the fields below using recent, reliable values, then review them before the model runs.",
                "unsupported": "I can discuss general sleep, hydration, activity and nutrition, or structure heart, diabetes, kidney or liver research screening when the required measurements are available.",
                "clarify": "I found signals for more than one screening. Choose heart, diabetes, kidney or liver so I can collect the correct measurements.",
            },
            "hi": {
                "emergency": "आपके विवरण में आपातकालीन चेतावनी संकेत हो सकता है। अभी 112 पर कॉल करें या नज़दीकी आपातकालीन विभाग जाएँ। AI परिणाम की प्रतीक्षा न करें।",
                "ready": f"मैं {name.lower()} स्क्रीनिंग की जानकारी व्यवस्थित करने में मदद कर सकता हूँ। नीचे हाल की और विश्वसनीय जानकारी भरें और मॉडल चलाने से पहले उसकी जाँच करें।",
                "unsupported": "मैं नींद, पानी, गतिविधि और पोषण की सामान्य जानकारी दे सकता हूँ, या ज़रूरी माप उपलब्ध होने पर हृदय, मधुमेह, किडनी या लिवर शोध स्क्रीनिंग व्यवस्थित कर सकता हूँ।",
                "clarify": "मुझे एक से अधिक स्क्रीनिंग के संकेत मिले। सही जानकारी लेने के लिए हृदय, मधुमेह, किडनी या लिवर में से एक चुनें।",
            },
        }
        return content.get(language, content["en"])[key]

    def start(self, message: str, locale: Locale) -> TriageResponse:
        state = TriageState(session_id=uuid4().hex, locale=locale.value, messages=[message])
        return self._advance(state)

    def continue_session(self, token: str, message: str, locale: Locale) -> TriageResponse:
        payload = self.codec.decode(token, "triage")
        state = TriageState(
            session_id=payload["session_id"],
            locale=locale.value,
            messages=[*payload.get("messages", []), message],
            condition=payload.get("condition"),
            known_fields=payload.get("known_fields", {}),
            field_evidence=payload.get("field_evidence", {}),
        )
        return self._advance(state)

    def _advance(self, state: TriageState) -> TriageResponse:
        # Evaluate the complete user history so warning signs split across turns
        # (for example, "fever" followed by "stiff neck") are not missed.
        user_history = " ".join(
            message for message in state.messages if not message.startswith(ASSISTANT_FOLLOWUP_PREFIX)
        )
        safety = screen_for_emergency(user_history)
        if safety.emergency:
            decision = OrchestrationDecision(
                action="escalate",
                response="Emergency warning signs detected by the deterministic safety gate.",
            )
            return TriageResponse(
                state_token=self._state_token(state),
                response=self._copy(state.locale, "emergency"),
                status="emergency",
                emergency=True,
                disclaimer=DISCLAIMER,
                decision=decision,
            )
        decision = self.router.decide(state.messages)
        if decision.tool:
            prior = state.known_fields or {}
            merged = {**prior, **decision.known_fields, **decision.arguments}
            decision.field_evidence = {**(state.field_evidence or {}), **decision.field_evidence}
            decision.known_fields = merged
            decision.arguments = {}
            decision.missing_fields = [
                field for field in self.registry.required_fields(decision.tool) if field not in merged
            ]
            if decision.action in {"ask_question", "call_tool"}:
                decision.action = "ask_question" if decision.missing_fields else "call_tool"
        try:
            decision = self.policy.validate(decision, state.messages)
        except DecisionPolicyError:
            decision = OrchestrationDecision(
                action="unsupported",
                response="The proposed action did not pass the deterministic policy gate.",
                source=decision.source,
            )
        condition = self.registry.condition_for(decision.tool) if decision.tool else None
        state.condition = state.condition or condition
        state.known_fields = decision.known_fields or state.known_fields or {}
        state.field_evidence = decision.field_evidence or state.field_evidence or {}
        if state.condition and decision.action in {"ask_question", "call_tool"}:
            return TriageResponse(
                state_token=self._state_token(state),
                response=decision.response or self._copy(state.locale, "ready", state.condition),
                status="ready",
                condition=state.condition,
                required_fields=get_fields(state.condition),
                disclaimer=DISCLAIMER,
                decision=decision,
                known_fields=state.known_fields,
            )
        if decision.action == "ask_question":
            return TriageResponse(
                state_token=self._state_token(state),
                response=decision.response or self._copy(state.locale, "clarify"),
                status="collecting",
                disclaimer=DISCLAIMER,
                decision=decision,
            )
        if decision.action == "respond":
            if decision.mode == "symptom_interview":
                state.messages.append(f"{ASSISTANT_FOLLOWUP_PREFIX}{decision.response}")
            return TriageResponse(
                state_token=self._state_token(state),
                response=decision.response,
                status="collecting",
                disclaimer=DISCLAIMER,
                decision=decision,
            )
        return TriageResponse(
            state_token=self._state_token(state),
            response=decision.response or self._copy(state.locale, "unsupported"),
            status="unsupported",
            disclaimer=DISCLAIMER,
            decision=decision,
        )
