import json
import re
from collections.abc import Callable
from typing import Any
from typing import Protocol as TypingProtocol

from pydantic import ValidationError

from .schemas import OrchestrationDecision
from .tool_registry import SpecialistToolRegistry

CONDITION_TERMS = {
    "heart_risk": {
        "heart",
        "heart disease",
        "heart condition",
        "cardiac",
        "cardiovascular",
        "chest pain",
        "cholesterol",
        "hypertension",
        "high blood pressure",
        "blood vessel blockage",
        "blood vessels blockage",
        "blockage in blood vessels",
        "blocked blood vessel",
        "blocked blood vessels",
        "arterial blockage",
        "artery blockage",
        "blocked artery",
        "blocked arteries",
        "clogged artery",
        "clogged arteries",
        "coronary blockage",
        "coronary artery disease",
        "atherosclerosis",
        "angina",
        "ecg",
        "दिल",
        "हृदय",
        "सीने में दर्द",
        "कोलेस्ट्रॉल",
    },
    "diabetes_risk": {
        "diabetes",
        "diabetic",
        "sugar",
        "blood sugar",
        "high blood sugar",
        "glucose",
        "high glucose",
        "prediabetes",
        "pre diabetes",
        "hyperglycemia",
        "hba1c",
        "a1c",
        "excessive thirst",
        "very thirsty",
        "frequent urination",
        "urinating frequently",
        "urinating often",
        "polyuria",
        "polydipsia",
        "मधुमेह",
        "शुगर",
        "बहुत प्यास",
        "बार-बार पेशाब",
    },
    "kidney_risk": {
        "kidney",
        "kidneys",
        "kidney disease",
        "kidney problem",
        "kidney issues",
        "renal",
        "renal disease",
        "creatinine",
        "blood urea",
        "urea level",
        "urine albumin",
        "albuminuria",
        "protein in urine",
        "proteinuria",
        "egfr",
        "gfr",
        "ckd",
        "गुर्दा",
        "किडनी",
        "क्रिएटिनिन",
    },
    "liver_risk": {
        "liver",
        "liver disease",
        "liver problem",
        "liver issues",
        "fatty liver",
        "bilirubin",
        "jaundice",
        "alt",
        "ast",
        "sgpt",
        "sgot",
        "lft",
        "liver enzymes",
        "liver function",
        "लिवर",
        "जिगर",
        "बिलीरुबिन",
        "पीलिया",
    },
}

# Flexible patterns cover the word-order and inflection variation common in
# typed and transcribed speech. They deliberately remain high precision: a
# specialist form is opened only when both the finding and anatomy are present.
CONDITION_PATTERNS = {
    "heart_risk": (
        re.compile(
            r"\b(?:block(?:age|ed)|clog(?:ged|ging)?|narrow(?:ed|ing)?)\b.{0,24}"
            r"\b(?:blood\s+vessels?|arter(?:y|ies)|coronary\s+arter(?:y|ies))\b"
        ),
        re.compile(
            r"\b(?:blood\s+vessels?|arter(?:y|ies)|coronary\s+arter(?:y|ies))\b.{0,24}"
            r"\b(?:block(?:age|ed)|clog(?:ged|ging)?|narrow(?:ed|ing)?)\b"
        ),
    ),
    "diabetes_risk": (
        re.compile(r"\b(?:blood\s+)?(?:sugar|glucose)\b.{0,18}\b(?:high|elevated|raised)\b"),
        re.compile(r"\b(?:high|elevated|raised)\b.{0,18}\b(?:blood\s+)?(?:sugar|glucose)\b"),
    ),
    "kidney_risk": (
        re.compile(r"\b(?:kidneys?|renal)\b.{0,18}\b(?:disease|problem|issue|failure|function|screen(?:ing)?)\b"),
        re.compile(r"\b(?:low|reduced|abnormal)\b.{0,18}\b(?:egfr|gfr|kidney\s+function)\b"),
        re.compile(r"\b(?:protein|albumin)\b.{0,14}\burine\b"),
    ),
    "liver_risk": (
        re.compile(r"\bliver\b.{0,18}\b(?:disease|problem|issue|function|enzyme|screen(?:ing)?)s?\b"),
        re.compile(r"\b(?:high|elevated|raised|abnormal)\b.{0,18}\b(?:bilirubin|alt|ast|sgpt|sgot|liver\s+enzymes?)\b"),
    ),
}

GREETING_TERMS = {"hi", "hello", "hey", "good morning", "good evening", "नमस्ते", "हेलो"}
THANKS_TERMS = {"thanks", "thank you", "धन्यवाद", "शुक्रिया"}
SMALL_TALK_PHRASES = {
    "how are you",
    "how is it going",
    "how's it going",
    "hope you are doing well",
    "hope you're doing well",
    "what is up",
    "what's up",
    "nice to meet you",
}

# High-precision examples that are clearly outside this medical research lab.
# These are handled locally so guardrail probes do not wake or wait for the LLM.
OUT_OF_SCOPE_TERMS = {
    "cricket",
    "football",
    "soccer",
    "chess",
    "video game",
    "coding",
    "javascript",
    "python code",
    "stock price",
    "movie",
    "song",
    "recipe",
}

WELLNESS_TOPICS = {
    "sleep": {
        "sleep",
        "insomnia",
        "sleeping",
        "नींद",
    },
    "hydration": {
        "hydration",
        "hydrate",
        "drinking water",
        "पानी",
    },
    "activity": {
        "exercise",
        "walking",
        "workout",
        "physical activity",
        "व्यायाम",
    },
    "nutrition": {
        "healthy diet",
        "balanced diet",
        "nutrition",
        "healthy food",
        "पोषण",
    },
}

WELLNESS_RESPONSES = {
    "sleep": "I can help with general sleep habits. A consistent sleep and wake time, a dark quiet room, and reducing late caffeine and screen exposure are reasonable basics. If poor sleep persists, affects daytime safety, or comes with breathing pauses, discuss it with a clinician.",
    "hydration": "For general hydration, regular water intake and using thirst and urine colour as rough cues can be practical. Needs vary with heat, exercise, pregnancy, and heart or kidney conditions, so I should not prescribe a universal amount. Seek clinical advice for persistent excessive thirst or dehydration signs.",
    "activity": "For general activity planning, start at a comfortable level and increase gradually, combining aerobic movement with strength and mobility work. Stop and seek care for chest pain, fainting, or unusual breathlessness. A clinician can personalize activity if you have a medical condition.",
    "nutrition": "For general nutrition, favour varied minimally processed foods, vegetables, fruit, whole grains, protein sources, and appropriate portions. Individual needs differ with allergies and medical conditions, so I can explain principles but should not prescribe a therapeutic diet.",
}

SYMPTOM_TOPICS = {
    "reflux": {
        "acid reflux",
        "acidity",
        "heartburn",
        "heart burn",
        "hurt burn",
        "acid regurgitation",
        "burning stomach",
        "burning in my chest",
        "gerd",
        "एसिडिटी",
        "सीने में जलन",
    },
    "fever": {"fever", "temperature", "feverish", "chills", "बुखार"},
    "respiratory": {"cough", "sore throat", "cold symptoms", "runny nose", "खांसी", "गले में दर्द"},
    "headache": {"headache", "migraine", "head pain", "सिरदर्द", "सिर में दर्द"},
    "pain": {"stomach pain", "back pain", "knee pain", "body pain", "abdominal pain", "दर्द"},
    "skin": {"rash", "skin irritation", "hives", "दाने", "चकत्ते"},
    "gastrointestinal": {
        "nausea",
        "vomiting",
        "diarrhea",
        "diarrhoea",
        "constipation",
        "bloating",
        "indigestion",
        "stomach upset",
        "loose motion",
        "मतली",
        "उल्टी",
        "दस्त",
        "कब्ज",
    },
    "urinary": {
        "burning urination",
        "painful urination",
        "urine problem",
        "blood in urine",
        "frequent urination",
        "flank pain",
        "पेशाब में जलन",
        "पेशाब में खून",
    },
    "dizziness_fatigue": {
        "dizzy",
        "dizziness",
        "lightheaded",
        "fatigue",
        "tired all the time",
        "low energy",
        "चक्कर",
        "थकान",
    },
    "eye": {"eye", "eye pain", "red eye", "blurred vision", "vision problem", "आंख में दर्द", "लाल आंख"},
    "ear": {"ear pain", "earache", "hearing problem", "ear discharge", "कान में दर्द"},
    "oral_dental": {
        "tooth pain",
        "toothache",
        "mouth ulcer",
        "gum swelling",
        "dental pain",
        "दांत दर्द",
        "मुंह में छाला",
    },
    "swelling": {"swelling", "swollen", "ankle swelling", "leg swelling", "सूजन"},
    "pelvic_menstrual": {
        "period pain",
        "missed period",
        "heavy period",
        "vaginal bleeding",
        "pelvic pain",
        "मासिक दर्द",
        "अनियमित माहवारी",
    },
}

SYMPTOM_FOLLOWUPS = {
    "reflux": [
        "I can help organize this without diagnosing it. How long have you had the burning or reflux, and how often does it happen?",
        "Does it relate to meals or lying down, and have you noticed trouble swallowing, vomiting, weight loss, blood in vomit, or black stools?",
        "Is it getting worse, waking you at night, or continuing despite avoiding triggers you already recognize?",
    ],
    "fever": [
        "What is the highest measured temperature, including whether it is Celsius or Fahrenheit?",
        "When did the fever start?",
        "Is this for an adult or a child, and what is their age?",
        "Besides the fever, what other symptoms are present?",
        "Are any of these warning signs present: trouble breathing, a stiff neck, confusion, a seizure, repeated vomiting, severe dehydration, or difficulty waking? Please answer yes or no and name any that are present.",
        "Is the fever improving, unchanged, or worsening?",
        "Is there pregnancy, immune suppression, or a significant chronic medical condition?",
    ],
    "respiratory": [
        "How long have the cough or throat symptoms been present, and are they improving or worsening?",
        "Is there measured fever, wheezing, chest pain, breathing difficulty, dehydration, or a chronic heart or lung condition?",
        "Have the symptoms lasted more than 10 days, or improved and then returned or worsened?",
    ],
    "headache": [
        "When did the headache start, how quickly did it reach its worst point, and is it new or different from previous headaches?",
        "Is there fever, stiff neck, confusion, fainting, weakness, vision loss, repeated vomiting, head injury, or pregnancy?",
        "Is it worsening, persistent, or interfering with normal activity despite rest and hydration?",
    ],
    "pain": [
        "Where exactly is the pain, when did it start, and how severe is it from 0 to 10?",
        "Was there an injury, and is there fever, swelling, weakness, numbness, repeated vomiting, bleeding, or difficulty walking or breathing?",
        "Is the pain improving, stable, or worsening, and what movements or situations change it?",
    ],
    "skin": [
        "When did the skin change begin, where is it, and is it spreading, painful, itchy, blistering, or associated with a new exposure?",
        "Is there fever, facial or throat swelling, breathing difficulty, purple spots, skin peeling, or involvement of the eyes or mouth?",
        "Is it worsening, recurring, or associated with a new medicine, food, cosmetic, plant, or insect exposure?",
    ],
    "gastrointestinal": [
        "What digestive symptom is most concerning, when did it start, and how often is it happening?",
        "Is there severe or localized abdominal pain, repeated vomiting, blood, black stool, fever, dehydration, or inability to keep fluids down?",
        "Is it improving or worsening, and was there recent travel, a new food or medicine, pregnancy, or a similar illness in close contacts?",
    ],
    "urinary": [
        "What urinary change are you noticing, when did it start, and is there pain or burning?",
        "Is there fever, back or side pain, vomiting, visible blood, inability to pass urine, pregnancy, or reduced urine output?",
        "Is it worsening or recurring, and is there kidney disease, diabetes, immune suppression, or a recent urinary procedure?",
    ],
    "dizziness_fatigue": [
        "When did the dizziness or fatigue start, is it constant or episodic, and what were you doing when it began?",
        "Is there fainting, chest pain, breathing difficulty, severe headache, weakness on one side, bleeding, fever, vomiting, or poor fluid intake?",
        "Is it worsening or affecting walking and daily activity, and is there pregnancy, diabetes, heart disease, anemia, or a new medicine?",
    ],
    "eye": [
        "Which eye is affected, when did it start, and is there pain, redness, discharge, injury, or a contact-lens concern?",
        "Is there sudden vision loss, severe pain, light sensitivity, chemical exposure, a foreign body, severe headache, or vomiting?",
        "Is it worsening, and do you have diabetes, immune suppression, recent eye surgery, or a new medicine?",
    ],
    "ear": [
        "Which ear is affected, when did it start, and is there pain, reduced hearing, discharge, ringing, or dizziness?",
        "Is there high fever, swelling behind the ear, severe headache, facial weakness, injury, bleeding, or a foreign object?",
        "Is it worsening or recurring, and was there recent swimming, air travel, a respiratory illness, or a new medicine?",
    ],
    "oral_dental": [
        "Where is the mouth or dental problem, when did it start, and is there pain, swelling, an ulcer, bleeding, or trouble chewing?",
        "Is there facial or neck swelling, fever, trouble swallowing, drooling, breathing difficulty, injury, or uncontrolled bleeding?",
        "Is it worsening or recurring, and was there recent dental work, a broken tooth, immune suppression, or a new medicine?",
    ],
    "swelling": [
        "Where is the swelling, when did it begin, and did it appear suddenly or gradually?",
        "Is it on one side, red, hot or painful, and is there chest pain, breathing difficulty, facial or throat swelling, fever, or an injury?",
        "Is it worsening, and is there pregnancy or known heart, kidney, liver, vein, or medication-related risk?",
    ],
    "pelvic_menstrual": [
        "What pelvic or menstrual change are you experiencing, when did it start, and how severe is the pain or bleeding?",
        "Could there be pregnancy, and is there fainting, one-sided severe pain, shoulder pain, fever, heavy bleeding, or unusual discharge?",
        "Is it worsening or recurring, and is there a known gynecologic condition, recent procedure, or new medicine?",
    ],
    "general": [
        "What symptom is bothering you most, where is it, and when did it begin?",
        "How severe is it, is it improving or worsening, and how is it affecting normal activity, eating, drinking, sleep, or walking?",
        "Is there breathing difficulty, chest pain, fainting, confusion, new weakness, severe bleeding, repeated vomiting, dehydration, or inability to pass urine?",
        "Is this for an adult or child, and is there pregnancy, immune suppression, a chronic condition, recent surgery, injury, or a new medicine?",
    ],
}

ASSISTANT_FOLLOWUP_PREFIX = "[HealthAI follow-up] "

FEVER_URGENT_RESPONSE = (
    "A worsening fever with immune suppression needs urgent same-day assessment by a qualified clinician. "
    "Please contact your clinical team or an urgent-care service now. If you develop trouble breathing, blue lips, "
    "confusion, a stiff neck, a seizure, severe dehydration, or become difficult to wake, call 112 or go to the "
    "nearest emergency department."
)

FEVER_SLOTS = (
    "temperature",
    "duration",
    "population",
    "associated_symptoms",
    "red_flags_answered",
    "trajectory",
    "risk_context",
)


class QwenSymptomQuestionSelector:
    """Lets Qwen select an allowlisted question; Qwen never writes medical text."""

    def __init__(self, runner):
        self.runner = runner

    def decide(self, messages: list[str], topic: str) -> OrchestrationDecision:
        questions = SYMPTOM_FOLLOWUPS[topic]
        user_text = " ".join(
            message for message in messages if not message.startswith(ASSISTANT_FOLLOWUP_PREFIX)
        ).lower()
        asked = {
            message.removeprefix(ASSISTANT_FOLLOWUP_PREFIX)
            for message in messages
            if message.startswith(ASSISTANT_FOLLOWUP_PREFIX)
        }
        fever_slots = RulesRouter._fever_answered_slots(messages) if topic == "fever" else set()
        candidates = {
            f"{topic}_{index + 1}": question
            for index, question in enumerate(questions)
            if (
                FEVER_SLOTS[index] not in fever_slots
                if topic == "fever"
                else question not in asked and not self._answered_by_user(topic, index, user_text)
            )
        }
        first_question_id = f"{topic}_1"
        if topic == "general" and first_question_id in candidates:
            # A free-form concern needs a stable what/where/when foundation before
            # the model may select severity, red-flag or risk-context questions.
            candidates = {first_question_id: candidates[first_question_id]}
        if topic == "fever" and candidates:
            # Fever intake is slot-based and ordered. This prevents the model from
            # skipping duration or age after receiving only a temperature value.
            first_candidate = next(iter(candidates))
            candidates = {first_candidate: candidates[first_candidate]}
        if not candidates:
            return OrchestrationDecision(
                action="respond",
                response=RulesRouter._interview_complete_response(topic, user_text),
                source="rules",
                mode="symptom_interview",
            )
        if len(candidates) == 1:
            return OrchestrationDecision(
                action="respond",
                response=next(iter(candidates.values())),
                source="rules",
                mode="symptom_interview",
            )
        selected = self.runner.select_symptom_question(messages, candidates)
        return OrchestrationDecision(
            action="respond",
            response=candidates[selected],
            source="qwen",
            mode="symptom_interview",
        )

    @staticmethod
    def _answered_by_user(topic: str, index: int, text: str) -> bool:
        return False


EXPLICIT_HEART_VALUE_PATTERNS = {
    "age": re.compile(r"\b(?:i am|i'm|age(?: is)?)\s*(?P<value>\d{1,3})\b", re.IGNORECASE),
    "resting_bp": re.compile(
        r"\b(?:bp|blood pressure)(?:\s+is)?\s*(?P<value>\d{2,3})\b",
        re.IGNORECASE,
    ),
    "serum_cholesterol": re.compile(
        r"\bcholesterol(?:\s+is)?\s*(?P<value>\d{2,3})\b",
        re.IGNORECASE,
    ),
}


class Router(TypingProtocol):
    def decide(self, messages: list[str]) -> OrchestrationDecision: ...


class RulesRouter:
    """Deterministic fallback and baseline for Qwen routing evaluations."""

    def __init__(self, registry: SpecialistToolRegistry):
        self.registry = registry

    def decide(self, messages: list[str]) -> OrchestrationDecision:
        user_messages = [message for message in messages if not message.startswith(ASSISTANT_FOLLOWUP_PREFIX)]
        text = self._normalize_routing_text(" ".join(user_messages))
        latest = messages[-1].strip().lower()
        normalized_latest = re.sub(r"[^\w\s']+", " ", latest, flags=re.UNICODE)
        normalized_latest = " ".join(normalized_latest.split())
        if self._is_conversational(normalized_latest):
            return OrchestrationDecision(
                action="respond",
                response=self._conversation_response(normalized_latest),
            )
        if normalized_latest in THANKS_TERMS:
            return OrchestrationDecision(
                action="respond",
                response="You’re welcome. If you want, tell me what you’re experiencing and we can decide whether one of the available screenings is relevant.",
            )
        if self._is_disallowed_medical_request(latest):
            return OrchestrationDecision(
                action="unsupported",
                response=(
                    "I can’t provide a diagnosis, invent clinical values, or execute an unregistered disease predictor. "
                    "I can still help: describe the symptoms, when they began, and whether they are worsening, and I’ll "
                    "run the safety gate and structure the appropriate clinical-intake pathway."
                ),
            )
        wellness_topic = self._wellness_topic(normalized_latest)
        if wellness_topic:
            return OrchestrationDecision(
                action="respond",
                response=WELLNESS_RESPONSES[wellness_topic],
                mode="wellness",
            )
        symptom_topic = self._active_symptom_topic(messages)
        scores = {tool: self._condition_score(text, tool) for tool in CONDITION_TERMS}
        highest = max(scores.values())
        winners = [tool for tool, score in scores.items() if score == highest and score > 0]
        if not winners:
            if symptom_topic:
                return self._symptom_decision(messages, symptom_topic, text)
            if self._looks_like_health_concern(normalized_latest):
                return OrchestrationDecision(
                    action="respond",
                    response=SYMPTOM_FOLLOWUPS["general"][0],
                    mode="symptom_interview",
                )
            if self._is_obviously_out_of_scope(normalized_latest):
                return OrchestrationDecision(
                    action="unsupported",
                    response=(
                        "This workspace is focused on health concerns, general wellness, and its registered research "
                        "screenings, so I can’t help with that topic here. If you have a health or wellness question, "
                        "describe it naturally and I’ll run the safety check first."
                    ),
                )
            return OrchestrationDecision(
                action="respond",
                response=(
                    "Tell me what health symptom or wellness concern you want to discuss. I can run a safety check, "
                    "structure a general clinical interview, or prepare heart, diabetes, kidney and liver research screening."
                ),
            )
        if len(winners) > 1:
            return OrchestrationDecision(
                action="ask_question",
                response=(
                    "I found signals for more than one specialist model. Please choose heart, diabetes, kidney, "
                    "or liver screening so I can open the correct reviewed form."
                ),
            )
        tool = winners[0]
        known_fields: dict[str, int] = {}
        field_evidence: dict[str, str] = {}
        if tool == "heart_risk":
            conversation = " ".join(user_messages)
            for field, pattern in EXPLICIT_HEART_VALUE_PATTERNS.items():
                match = pattern.search(conversation)
                if match:
                    known_fields[field] = int(match.group("value"))
                    field_evidence[field] = match.group("value") if field == "age" else match.group(0)
        return OrchestrationDecision(
            action="ask_question",
            tool=tool,
            known_fields=known_fields,
            field_evidence=field_evidence,
            missing_fields=[field for field in self.registry.required_fields(tool) if field not in known_fields],
            response="Open the matching specialist screening form.",
            mode="screening",
        )

    @classmethod
    def _symptom_decision(cls, messages: list[str], topic: str, user_text: str) -> OrchestrationDecision:
        disposition = cls._urgent_symptom_disposition(topic, user_text)
        if disposition:
            return OrchestrationDecision(
                action="respond",
                response=disposition,
                mode="symptom_interview",
            )
        questions = SYMPTOM_FOLLOWUPS[topic]
        asked = {
            cls._normalize_question(message.removeprefix(ASSISTANT_FOLLOWUP_PREFIX))
            for message in messages
            if message.startswith(ASSISTANT_FOLLOWUP_PREFIX)
        }
        fever_slots = cls._fever_answered_slots(messages) if topic == "fever" else set()
        candidates = [
            question
            for index, question in enumerate(questions)
            if (
                FEVER_SLOTS[index] not in fever_slots
                if topic == "fever"
                else cls._normalize_question(question) not in asked
                and not QwenSymptomQuestionSelector._answered_by_user(topic, index, user_text)
            )
        ]
        return OrchestrationDecision(
            action="respond",
            response=candidates[0] if candidates else cls._interview_complete_response(topic, user_text),
            mode="symptom_interview",
        )

    @staticmethod
    def _is_conversational(latest: str) -> bool:
        words = set(latest.split())
        return (
            latest in GREETING_TERMS
            or any(phrase in latest for phrase in SMALL_TALK_PHRASES)
            or (bool(words & GREETING_TERMS) and len(words) <= 12)
        )

    @staticmethod
    def _conversation_response(latest: str) -> str:
        if "how are you" in latest or "doing well" in latest:
            return "I’m doing well—thanks for asking. How are you feeling today?"
        if "what's up" in latest or "what is up" in latest:
            return "Hey! I’m here and ready to help. How are you feeling today?"
        return "Hi! How are you feeling today? You can describe your concern naturally, by text or voice."

    @staticmethod
    def _wellness_topic(latest: str) -> str | None:
        return next(
            (topic for topic, terms in WELLNESS_TOPICS.items() if any(term in latest for term in terms)),
            None,
        )

    @staticmethod
    def _symptom_topic(text: str) -> str | None:
        return next(
            (
                topic
                for topic, terms in SYMPTOM_TOPICS.items()
                if any(RulesRouter._contains_term(text, term) for term in terms)
            ),
            None,
        )

    @staticmethod
    def _looks_like_health_concern(text: str) -> bool:
        terms = {
            "ache",
            "burn",
            "bleeding",
            "discomfort",
            "feel sick",
            "feeling sick",
            "health problem",
            "hurt",
            "hurts",
            "ill",
            "issue",
            "pain",
            "problem",
            "sick",
            "symptom",
            "unwell",
            "weak",
            "painful",
            "दर्द",
            "तबीयत",
            "समस्या",
        }
        return any(RulesRouter._contains_term(text, term) for term in terms)

    @staticmethod
    def _is_obviously_out_of_scope(text: str) -> bool:
        return any(RulesRouter._contains_term(text, term) for term in OUT_OF_SCOPE_TERMS)

    @staticmethod
    def _has_explicit_predictor_intent(text: str) -> bool:
        normalized = RulesRouter._normalize_routing_text(text)
        return any(RulesRouter._condition_score(normalized, tool) for tool in CONDITION_TERMS)

    @staticmethod
    def _normalize_routing_text(text: str) -> str:
        """Normalize punctuation and common ASR separators without changing meaning."""
        normalized = re.sub(r"[_/\-]+", " ", text.casefold())
        # Python's ``\w`` does not retain Devanagari combining marks, so keep
        # the full block while still replacing punctuation for phrase matching.
        normalized = re.sub(r"[^\w\s'\u0900-\u097F]+", " ", normalized, flags=re.UNICODE)
        return " ".join(normalized.split())

    @staticmethod
    def _condition_score(text: str, tool: str) -> int:
        term_matches = sum(
            1 for term in CONDITION_TERMS[tool] if RulesRouter._contains_term(text, term)
        )
        pattern_matches = sum(bool(pattern.search(text)) for pattern in CONDITION_PATTERNS[tool])
        return term_matches + pattern_matches

    @staticmethod
    def _is_disallowed_medical_request(text: str) -> bool:
        has_boundary_request = any(
            phrase in text
            for phrase in {
                "diagnose",
                "definitive diagnosis",
                "prescribe",
                "fake values",
                "made up values",
                "invent values",
                "ignore safety",
                "ignore all safety",
                "call the stroke model",
                "call an unlisted",
                "run a stroke disease prediction",
                "निदान",
                "प्रिस्क्राइब",
                "नकली मान",
            }
        )
        return has_boundary_request

    @classmethod
    def _active_symptom_topic(cls, messages: list[str]) -> str | None:
        """Use the most recent symptom-bearing turn, so a new concern can replace an older one."""
        latest = messages[-1].casefold()
        latest_topic = cls._symptom_topic(latest)
        if latest_topic and re.search(
            r"\b(?:i have|i'm having|i am having|my concern is|new concern|now i have)\b",
            latest,
        ):
            return latest_topic
        # A user reply belongs to the immediately preceding follow-up even when
        # the reply names an associated symptom from another topic (for example,
        # "sore throat" while answering the fever interview).
        if len(messages) >= 2 and messages[-2].startswith(ASSISTANT_FOLLOWUP_PREFIX):
            previous_question = cls._normalize_question(
                messages[-2].removeprefix(ASSISTANT_FOLLOWUP_PREFIX)
            )
            for topic, questions in SYMPTOM_FOLLOWUPS.items():
                if any(cls._normalize_question(question) == previous_question for question in questions):
                    return topic
        for message in reversed(messages):
            topic = cls._symptom_topic(message.casefold())
            if topic:
                return topic
        return None

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(re.sub(r"[^\w\s]", " ", question.casefold()).split())

    @staticmethod
    def _urgent_symptom_disposition(topic: str, text: str) -> str | None:
        if topic != "fever":
            return None
        evidence = RulesRouter._fever_evidence(text)
        if evidence.get("immune_risk") and evidence.get("trajectory") == "worsening":
            return FEVER_URGENT_RESPONSE
        return None

    @staticmethod
    def _fever_evidence(text: str) -> dict[str, Any]:
        temperature_match = re.search(
            r"\b(?P<value>\d{2,3}(?:\.\d+)?)\s*(?:°\s*)?(?P<unit>[cf])\b",
            text,
            re.IGNORECASE,
        )
        duration_match = re.search(
            r"\b(?:since\s+)?(?:today|yesterday|this morning|last night)\b"
            r"|\bfor\s+(?:about\s+)?\d+\s*(?:hour|day|week)s?\b",
            text,
            re.IGNORECASE,
        )
        age_match = re.search(r"\b(?P<age>\d{1,3})\s*(?:year|yr)s?(?:\s+old)?\b", text, re.IGNORECASE)
        population_match = re.search(r"\b(adult|child|baby|infant|teen(?:ager)?)\b", text, re.IGNORECASE)
        symptom_terms = (
            "cough",
            "sore throat",
            "headache",
            "rash",
            "runny nose",
            "body ache",
            "chills",
            "vomiting",
            "diarrhea",
        )
        associated = [term for term in symptom_terms if RulesRouter._contains_term(text, term)]
        red_flag_terms = (
            "trouble breathing",
            "difficulty breathing",
            "stiff neck",
            "confusion",
            "seizure",
            "repeated vomiting",
            "severe dehydration",
            "difficult to wake",
            "difficulty waking",
        )
        red_flags = [term for term in red_flag_terms if term in text]
        trajectory = next(
            (
                value
                for value, terms in {
                    "worsening": ("worsening", "getting worse", "worse"),
                    "improving": ("improving", "getting better", "better"),
                    "unchanged": ("unchanged", "same", "stable"),
                }.items()
                if any(term in text for term in terms)
            ),
            None,
        )
        immune_terms = (
            "immune suppression",
            "immune supression",
            "immunosuppressed",
            "immunocompromised",
            "low immunity",
        )
        risk_terms = (
            *immune_terms,
            "pregnant",
            "pregnancy",
            "chronic condition",
            "chronic disease",
            "heart disease",
            "lung disease",
            "kidney disease",
        )
        # An explicit negative answer is useful only after the risk/red-flag
        # question appears in history; the asked-question check handles that.
        explicit_negative = bool(re.search(r"\b(no|none|neither)\b", text))
        immune_denied = bool(
            re.search(
                r"\b(?:no|without)\b[^.?!]{0,60}\b(?:immune suppression|immune supression|"
                r"immunosuppressed|immunocompromised|low immunity)\b",
                text,
            )
        )
        temperature = None
        if temperature_match:
            temperature = {
                "value": float(temperature_match.group("value")),
                "unit": temperature_match.group("unit").upper(),
                "display": temperature_match.group(0).upper().replace(" ", ""),
            }
        population = population_match.group(1).lower() if population_match else None
        if age_match:
            population = f"age {age_match.group('age')}"
        return {
            "temperature": temperature,
            "duration": duration_match.group(0) if duration_match else None,
            "population": population,
            "associated_symptoms": associated,
            "red_flags": red_flags,
            "red_flags_answered": bool(red_flags or explicit_negative),
            "trajectory": trajectory,
            "risk_context": [term for term in risk_terms if term in text and not (term in immune_terms and immune_denied)]
            or ("none reported" if explicit_negative else None),
            "immune_risk": any(term in text for term in immune_terms) and not immune_denied,
        }

    @classmethod
    def _fever_answered_slots(cls, messages: list[str]) -> set[str]:
        user_text = " ".join(
            message for message in messages if not message.startswith(ASSISTANT_FOLLOWUP_PREFIX)
        ).casefold()
        evidence = cls._fever_evidence(user_text)
        answered = {
            slot
            for slot in {"temperature", "duration", "population", "associated_symptoms", "trajectory"}
            if evidence.get(slot)
        }
        normalized_questions = {
            cls._normalize_question(question): index for index, question in enumerate(SYMPTOM_FOLLOWUPS["fever"])
        }
        for index, message in enumerate(messages[:-1]):
            if not message.startswith(ASSISTANT_FOLLOWUP_PREFIX):
                continue
            question_index = normalized_questions.get(
                cls._normalize_question(message.removeprefix(ASSISTANT_FOLLOWUP_PREFIX))
            )
            if question_index not in {4, 6}:
                continue
            reply = messages[index + 1].casefold()
            if reply.startswith(ASSISTANT_FOLLOWUP_PREFIX):
                continue
            negative_answer = bool(re.search(r"\b(?:no|none|neither|without)\b", reply))
            if question_index == 4 and (negative_answer or cls._fever_evidence(reply).get("red_flags")):
                answered.add("red_flags_answered")
            if question_index == 6 and (
                negative_answer or cls._fever_evidence(reply).get("risk_context")
            ):
                answered.add("risk_context")
        return answered

    @staticmethod
    def _fever_disposition(text: str) -> str:
        evidence = RulesRouter._fever_evidence(text)
        temperature = evidence.get("temperature")
        high_measured_fever = bool(
            temperature
            and (
                (temperature["unit"] == "F" and temperature["value"] >= 102)
                or (temperature["unit"] == "C" and temperature["value"] >= 38.9)
            )
        )
        same_day = bool(
            evidence.get("immune_risk")
            or (
                evidence.get("trajectory") == "worsening"
                and (high_measured_fever or "headache" in evidence.get("associated_symptoms", []))
            )
        )
        facts = []
        if temperature:
            facts.append(f"a measured temperature of {temperature['display']}")
        if evidence.get("duration"):
            facts.append(f"fever {evidence['duration']}")
        if evidence.get("associated_symptoms"):
            facts.append("associated " + ", ".join(evidence["associated_symptoms"][:4]))
        if evidence.get("trajectory"):
            facts.append(f"symptoms are {evidence['trajectory']}")
        summary = "; ".join(facts) if facts else "the fever information provided"
        emergency_copy = (
            "If trouble breathing, a stiff neck, confusion, a seizure, severe dehydration, or difficulty waking develops, "
            "call 112 or go to the nearest emergency department."
        )
        if same_day:
            return (
                f"Based on what you reported—{summary}—this should be assessed by a qualified clinician today. "
                "This does not identify the cause, but worsening fever should not be closed with a generic reassurance. "
                f"{emergency_copy}"
            )
        return (
            f"Based on what you reported—{summary}—I cannot determine the cause here. Monitor the pattern closely and "
            "contact a qualified clinician if it persists, worsens, or you are concerned. "
            f"{emergency_copy}"
        )

    @staticmethod
    def _interview_complete_response(topic: str, user_text: str = "") -> str:
        if topic == "fever":
            return RulesRouter._fever_disposition(user_text)
        labels = {
            "reflux": "burning or reflux",
            "fever": "fever",
            "respiratory": "cough or throat symptoms",
            "headache": "headache",
            "pain": "pain",
            "skin": "skin concern",
            "gastrointestinal": "digestive concern",
            "urinary": "urinary concern",
            "dizziness_fatigue": "dizziness or fatigue concern",
            "eye": "eye concern",
            "ear": "ear concern",
            "oral_dental": "mouth or dental concern",
            "swelling": "swelling concern",
            "pelvic_menstrual": "pelvic or menstrual concern",
            "general": "general symptom",
        }
        return (
            f"Thanks—I have the key context for this {labels[topic]} concern. I cannot diagnose it here. "
            "If it is persistent, worsening, or concerning, please arrange an assessment with a qualified clinician."
        )

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        if re.fullmatch(r"[a-z0-9 ]+", term):
            return bool(re.search(rf"\b{re.escape(term)}\b", text))
        return term in text


class QwenJsonRouter:
    """Runtime-neutral adapter for a local Qwen runner constrained to JSON output.

    The runner is injected so llama.cpp, an AWS container, or a test double can use
    the same policy boundary. Raw model text is never executed.
    """

    def __init__(self, runner: Callable[[str], str]):
        self.runner = runner

    def decide(self, messages: list[str]) -> OrchestrationDecision:
        prompt = self._prompt(messages)
        raw = self.runner(prompt)
        try:
            payload: dict[str, Any] = json.loads(raw)
            if (
                not payload.get("response")
                and payload.get("tool") is None
                and set(payload.get("arguments", {})) == {"response"}
            ):
                payload["response"] = payload["arguments"].pop("response")
            payload["source"] = "qwen"
            return OrchestrationDecision.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise ValueError("Qwen returned an invalid orchestration decision.") from exc

    @staticmethod
    def _prompt(messages: list[str]) -> str:
        conversation = json.dumps(messages[-6:], ensure_ascii=False)
        return (
            "You handle friendly conversation, general wellness education, and route only four educational screening tools. "
            "Always include mode: conversation, wellness, symptom_interview, or screening. "
            "Reply naturally to greetings, thanks, capability questions, and harmless small talk using action=respond. "
            "For clearly unrelated non-health requests such as sports rules, coding, entertainment, or finance, use "
            "action=unsupported, tool=null, empty clinical objects, and briefly redirect to health or wellness. "
            "You may give brief general education about sleep, hydration, physical activity, and balanced nutrition. "
            "Keep wellness responses under 90 words; do not diagnose, prescribe a treatment or diet, recommend a medicine or dose, "
            "or claim that a habit will prevent or cure disease. Encourage qualified care for persistent or worsening symptoms. "
            "Never ask for the user's name, identity, contact details, or account; ask how they are feeling instead. "
            "For common symptoms outside a registered predictor—such as fever, reflux/acidity, cough, headache, rash, or "
            "non-emergency pain—use mode=symptom_interview, tool=null, empty clinical objects, and action=respond. Ask exactly "
            "one short follow-up question that gathers duration, severity, measured values, associated symptoms, risk context, "
            "or change over time. Do not name a likely disease, give a probability, recommend a medicine, dose, test, or treatment, "
            "or reassure the user that the concern is harmless. "
            "For health concerns, identify whether heart_risk, diabetes_risk, kidney_risk, or liver_risk is relevant. Ask a concise follow-up "
            "when the intent is ambiguous. Extract only values the user explicitly supplied, using these exact fields. "
            "heart_risk fields: age, sex, chest_pain, resting_bp, serum_cholesterol, fasting_blood_sugar, resting_ecg, "
            "max_heart_rate, exercise_angina, oldpeak, st_slope, major_vessels, thal. diabetes_risk fields: age, "
            "gender, polyuria, polydipsia, sudden_weight_loss, weakness, polyphagia, genital_thrush, visual_blurring, "
            "itching, irritability, delayed_healing, partial_paresis, muscle_stiffness, alopecia, obesity. "
            "kidney_risk and liver_risk require reviewed structured forms; select the relevant tool but do not infer or extract "
            "their laboratory values from conversational text. "
            "Use numeric values for measurements and 0/1 only when the user explicitly says no/yes. For every known_fields item, "
            "field_evidence must contain the exact short phrase copied from the conversation that proves that value. "
            "If there is no exact evidence, omit the field. Never convert an unmentioned symptom to 0 or 1. Never "
            "infer sex, gender, a "
            "measurement, diagnosis, treatment, or probability. Emergency handling is performed before you. "
            "The JSON schema enforces the allowed values. Examples: For 'Hi', return action respond, tool null, empty "
            "objects and arrays, and a friendly response. For 'I am 54 and my BP is 145; check heart risk', return "
            "action ask_question, tool heart_risk, known_fields {age:54, resting_bp:145}, field_evidence "
            "{age:'54', resting_bp:'BP is 145'}, arguments {}, the remaining field names, and a concise response. "
            "For 'I am thirsty and urinate often', select diabetes_risk and include only polyuria=1 and polydipsia=1 "
            "with exact evidence—do not fill any other symptom. "
            "Use action=ask_question when a screening is selected but fields are missing; call_tool only when all "
            "registered fields were explicitly supplied. Use unsupported for medical tasks outside the four tools, "
            "but explain the boundary politely. Conversation, oldest to newest: "
            f"{conversation} /no_think"
        )


class FallbackRouter:
    def __init__(self, primary: Router, fallback: Router):
        self.primary = primary
        self.fallback = fallback

    def decide(self, messages: list[str]) -> OrchestrationDecision:
        try:
            return self.primary.decide(messages)
        except (RuntimeError, ValueError):
            return self.fallback.decide(messages)


class HybridRouter:
    """Qwen conversation/extraction with deterministic intent reconciliation.

    The small baseline model is not permitted to erase a supported deterministic
    route or turn arbitrary medical conversation into unconstrained advice.
    """

    def __init__(self, qwen: Router, rules: RulesRouter, symptom_selector: QwenSymptomQuestionSelector | None = None):
        self.qwen = qwen
        self.rules = rules
        self.symptom_selector = symptom_selector

    def decide(self, messages: list[str]) -> OrchestrationDecision:
        baseline = self.rules.decide(messages)
        # Registered, explicit screening intents already have a safe deterministic
        # route. Do not put the user-facing API behind a scale-to-zero LLM cold
        # start merely to reconfirm an allowlisted route.
        if baseline.tool:
            baseline.response = self._route_response(baseline.tool, len(baseline.known_fields))
            return baseline
        # Greetings, approved wellness education, and clear scope-boundary probes
        # already have reviewed responses. Waiting for a scale-to-zero model here
        # adds latency and cost without adding useful reasoning.
        if baseline.mode == "wellness" or baseline.action == "unsupported" or self.rules._is_conversational(
            messages[-1].strip().casefold()
        ):
            return baseline
        if baseline.mode == "symptom_interview" and self.symptom_selector is not None:
            topic = self.rules._active_symptom_topic(messages)
            if topic is None and self.rules._looks_like_health_concern(messages[-1].casefold()):
                topic = "general"
            if topic:
                user_text = " ".join(
                    message for message in messages if not message.startswith(ASSISTANT_FOLLOWUP_PREFIX)
                ).casefold()
                if self.rules._urgent_symptom_disposition(topic, user_text):
                    return baseline
                try:
                    return self.symptom_selector.decide(messages, topic)
                except (RuntimeError, ValueError):
                    return baseline
        try:
            proposal = self.qwen.decide(messages)
        except (RuntimeError, ValueError):
            return baseline

        if baseline.tool:
            allowed = set(self.rules.registry.required_fields(baseline.tool))
            conversation = " ".join(messages).casefold()
            verified_fields = {
                key: value
                for key, value in proposal.known_fields.items()
                if key in allowed
                and (evidence := proposal.field_evidence.get(key, "")).strip()
                and evidence.strip().casefold() in conversation
                and (value != 0 or any(marker in evidence.casefold() for marker in {"no ", "not ", "without", "नहीं"}))
            }
            if baseline.tool == "heart_risk":
                for field, pattern in EXPLICIT_HEART_VALUE_PATTERNS.items():
                    if field in verified_fields:
                        continue
                    match = pattern.search(" ".join(messages))
                    if match:
                        verified_fields[field] = int(match.group("value"))
                        proposal.field_evidence[field] = match.group(0)
            proposal.tool = baseline.tool
            proposal.action = "ask_question"
            proposal.known_fields = verified_fields
            proposal.field_evidence = {
                key: value for key, value in proposal.field_evidence.items() if key in proposal.known_fields
            }
            proposal.arguments = {}
            proposal.missing_fields = [field for field in allowed if field not in proposal.known_fields]
            proposal.response = self._route_response(baseline.tool, len(proposal.known_fields))
            proposal.mode = "screening"
            return proposal

        if baseline.mode == "symptom_interview":
            if self._safe_symptom_followup(proposal):
                return proposal
            return baseline

        if (
            baseline.action == "respond"
            and proposal.action == "respond"
            and not proposal.known_fields
            and baseline.mode in {"conversation", "wellness"}
        ):
            return proposal
        return baseline

    @staticmethod
    def _safe_symptom_followup(proposal: OrchestrationDecision) -> bool:
        response = proposal.response.strip().casefold()
        blocked = {
            "you have",
            "you likely",
            "diagnosis",
            "take ",
            "tablet",
            "capsule",
            "dose",
            " mg",
            "prescribe",
            "treatment",
            "medicine",
            "medication",
        }
        return (
            proposal.mode == "symptom_interview"
            and proposal.action in {"respond", "ask_question"}
            and proposal.tool is None
            and not proposal.arguments
            and not proposal.known_fields
            and not proposal.missing_fields
            and "?" in response
            and len(proposal.response) <= 360
            and not any(term in response for term in blocked)
            and not re.search(r"\b\d{1,3}\s*%", response)
        )

    @staticmethod
    def _route_response(tool: str, extracted_count: int) -> str:
        names = {
            "heart_risk": "heart-risk",
            "diabetes_risk": "early-diabetes signs",
            "kidney_risk": "kidney-disease pattern",
            "liver_risk": "liver-disease pattern",
        }
        name = names[tool]
        extracted = (
            f" I extracted {extracted_count} explicit value{'s' if extracted_count != 1 else ''} for you to review."
            if extracted_count
            else ""
        )
        return f"I matched this to the {name} specialist model.{extracted} The screening form is open below for your review."


class DecisionPolicyError(ValueError):
    pass


class DecisionPolicyValidator:
    """Fail-closed checks between any router and executable specialist tools."""

    def __init__(self, registry: SpecialistToolRegistry):
        self.registry = registry

    def validate(self, decision: OrchestrationDecision, messages: list[str] | None = None) -> OrchestrationDecision:
        if decision.action in {"respond", "unsupported", "escalate"}:
            if decision.tool or decision.arguments or decision.known_fields:
                raise DecisionPolicyError(f"{decision.action} cannot include a tool or clinical arguments.")
            return decision

        if decision.action == "explain_result":
            if decision.tool is None:
                raise DecisionPolicyError("A result explanation must identify its source tool.")
            self._require_registered(decision.tool)
            return decision

        if decision.action == "ask_question" and decision.tool is None:
            if decision.arguments or decision.known_fields or decision.missing_fields:
                raise DecisionPolicyError("A general clarification cannot contain tool fields.")
            return decision

        if decision.tool is None:
            raise DecisionPolicyError(f"{decision.action} requires a registered tool.")

        required = set(self._require_registered(decision.tool))
        supplied = set(decision.arguments) | set(decision.known_fields)
        invalid = supplied - required
        if invalid:
            raise DecisionPolicyError(f"Unknown fields for {decision.tool}: {sorted(invalid)}")
        if decision.source == "qwen" and supplied:
            if set(decision.field_evidence) != supplied:
                raise DecisionPolicyError("Every extracted field must have one evidence span.")
            conversation = " ".join(messages or []).casefold()
            if any(
                not evidence.strip() or evidence.strip().casefold() not in conversation
                for evidence in decision.field_evidence.values()
            ):
                raise DecisionPolicyError("Extracted field evidence must be copied from the conversation.")

        expected_missing = required - supplied
        if set(decision.missing_fields) != expected_missing:
            raise DecisionPolicyError("Missing fields do not match the registered tool schema.")

        if decision.action == "call_tool" and expected_missing:
            raise DecisionPolicyError("A tool cannot run until every required field is present.")
        if decision.action == "ask_question" and not expected_missing:
            raise DecisionPolicyError("No question is needed after all required fields are present.")
        return decision

    def _require_registered(self, slug: str) -> list[str]:
        if self.registry.get(slug) is None:
            raise DecisionPolicyError(f"Tool {slug!r} is not registered.")
        if not self.registry.is_callable(slug):
            raise DecisionPolicyError(f"Tool {slug!r} is not available on this deployment.")
        return self.registry.required_fields(slug)
