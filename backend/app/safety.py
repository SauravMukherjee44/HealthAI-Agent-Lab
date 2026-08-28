import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyResult:
    emergency: bool
    matched_signal: str | None = None


EMERGENCY_PATTERNS = {
    "possible cardiac emergency": [
        r"\b(chest pain|chest pressure|crushing pain)\b.*\b(sweat|breath|jaw|arm|faint)",
        r"\b(severe chest pain|can't breathe|cannot breathe)\b",
        r"सीने में (तेज )?(दर्द|दबाव)",
        r"सांस (नहीं|लेने में कठिनाई)",
    ],
    "possible stroke emergency": [
        r"\b(face.{0,16}droop\w*|arm.{0,16}weak\w*|speech.{0,16}slurr\w*|sudden paralysis)\b",
        r"चेहरा टेढ़ा|बोलने में कठिनाई|अचानक.*कमजोरी",
    ],
    "loss of consciousness": [
        r"\b(unconscious|not responding|passed out and not waking)\b",
        r"बेहोश|होश नहीं",
    ],
    "possible gastrointestinal bleeding": [
        r"\b(vomit(?:ing)? blood|blood in (?:my )?vomit|haematemesis|hematemesis|black tarry stool)\b",
        r"खून की उल्टी|काला मल",
    ],
    "possible neurological infection or acute neurological event": [
        r"\b(fever|headache)\b.*\b(stiff neck|confusion|seizure)\b",
        r"\b(sudden worst headache|worst headache of my life|thunderclap headache)\b",
        r"बुखार.*गर्दन में अकड़न|अचानक.*तेज सिरदर्द|दौरा",
    ],
    "possible severe respiratory illness": [
        r"\b(blue lips|bluish lips|gasping|struggling to breathe)\b",
        r"होंठ नीले|सांस के लिए हांफ",
    ],
}


def screen_for_emergency(message: str) -> SafetyResult:
    normalized = " ".join(message.lower().split())
    normalized = _remove_explicit_negations(normalized)
    for signal, patterns in EMERGENCY_PATTERNS.items():
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
            return SafetyResult(True, signal)
    return SafetyResult(False)


def _remove_explicit_negations(text: str) -> str:
    """Prevent a direct denial of a warning sign from matching keyword rules.

    This intentionally handles only short, explicit English denials. Ambiguous
    language remains fail-safe and can still escalate.
    """
    warning_terms = (
        "stiff neck",
        "confusion",
        "confused",
        "seizure",
        "chest pain",
        "chest pressure",
        "difficulty breathing",
        "trouble breathing",
        "repeated vomiting",
        "blue lips",
        "weakness",
    )
    alternatives = "|".join(re.escape(term) for term in warning_terms)
    # Covers "no stiff neck or confusion" as well as individual denials.
    coordinated = rf"\b(?:no|without)\s+(?:signs?\s+of\s+)?(?:{alternatives})(?:\s+(?:or|and)\s+(?:{alternatives}))*"
    text = re.sub(coordinated, " ", text, flags=re.IGNORECASE)
    text = re.sub(rf"\bnot\s+(?:experiencing|having|feeling)?\s*(?:{alternatives})\b", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())
