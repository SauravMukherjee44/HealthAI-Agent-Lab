from pathlib import Path

import pytest

from backend.app.routing import (
    SYMPTOM_FOLLOWUPS,
    DecisionPolicyError,
    DecisionPolicyValidator,
    FallbackRouter,
    HybridRouter,
    QwenJsonRouter,
    QwenSymptomQuestionSelector,
    RulesRouter,
)
from backend.app.schemas import OrchestrationDecision
from backend.app.tool_registry import SpecialistToolRegistry

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


@pytest.fixture
def registry():
    return SpecialistToolRegistry(ARTIFACTS)


def test_qwen_json_decision_is_parsed_but_not_executed(registry):
    fields = registry.required_fields("heart_risk")
    router = QwenJsonRouter(
        lambda _prompt: OrchestrationDecision(
            action="ask_question",
            tool="heart_risk",
            missing_fields=fields,
            response="Please provide the required measurements.",
        ).model_dump_json()
    )

    decision = router.decide(["I want a heart-risk screening"])

    assert decision.source == "qwen"
    assert DecisionPolicyValidator(registry).validate(decision) == decision


def test_hallucinated_unregistered_tool_is_blocked(registry):
    decision = OrchestrationDecision(
        action="call_tool",
        tool="calculator",
        arguments={},
        source="qwen",
    )

    with pytest.raises(DecisionPolicyError, match="not registered"):
        DecisionPolicyValidator(registry).validate(decision)


@pytest.mark.parametrize(
    ("message", "tool"),
    [
        ("Review my kidney creatinine results", "kidney_risk"),
        ("I have bilirubin and liver function results", "liver_risk"),
    ],
)
def test_rules_router_routes_new_lab_tools(registry, message, tool):
    decision = RulesRouter(registry).decide([message])

    assert decision.action == "ask_question"
    assert decision.tool == tool
    assert decision.missing_fields == registry.required_fields(tool)


@pytest.mark.parametrize(
    ("message", "tool"),
    [
        ("I have chest pain and want to understand my risk", "heart_risk"),
        ("I am very thirsty and urinating often", "diabetes_risk"),
        ("My urine albumin and blood urea are abnormal", "kidney_risk"),
        ("I have jaundice and an elevated AST", "liver_risk"),
    ],
)
def test_model_linked_signals_skip_generic_symptom_interview(registry, message, tool):
    decision = RulesRouter(registry).decide([message])

    assert decision.tool == tool
    assert decision.mode == "screening"
    assert decision.action == "ask_question"


@pytest.mark.parametrize(
    ("message", "tool"),
    [
        ("facing blood vessels blockage issue", "heart_risk"),
        ("Doctors mentioned a blocked blood vessel", "heart_risk"),
        ("I am worried about clogged arteries", "heart_risk"),
        ("Could I screen for coronary artery disease?", "heart_risk"),
        ("My blood-glucose is elevated", "diabetes_risk"),
        ("I was told I have pre-diabetes", "diabetes_risk"),
        ("My HbA1c result is high", "diabetes_risk"),
        ("I am urinating frequently and very thirsty", "diabetes_risk"),
        ("My eGFR is low", "kidney_risk"),
        ("There is protein in my urine", "kidney_risk"),
        ("I want to check a renal disease concern", "kidney_risk"),
        ("I have kidney issues", "kidney_risk"),
        ("My liver enzymes are elevated", "liver_risk"),
        ("I have a fatty-liver concern", "liver_risk"),
        ("My SGPT and SGOT are raised", "liver_risk"),
        ("I want to review an abnormal LFT", "liver_risk"),
    ],
)
def test_rules_router_normalizes_common_specialist_phrases(registry, message, tool):
    decision = RulesRouter(registry).decide([message])

    assert decision.tool == tool
    assert decision.mode == "screening"
    assert decision.action == "ask_question"


@pytest.mark.parametrize(
    "message",
    [
        "blood vessel is blocked",
        "blockage of my coronary arteries",
        "narrowing in the blood vessels",
        "my arteries may be clogged",
    ],
)
def test_flexible_vascular_word_order_routes_heart_model(registry, message):
    decision = RulesRouter(registry).decide([message])

    assert decision.tool == "heart_risk"
    assert decision.mode == "screening"


def test_rules_router_handles_general_wellness_without_a_predictive_model(registry):
    decision = RulesRouter(registry).decide(["How can I improve my sleep habits?"])

    assert decision.action == "respond"
    assert decision.tool is None
    assert "sleep" in decision.response.lower()


@pytest.mark.parametrize("message", ["How to play cricket", "Can I play cricket here?"])
def test_rules_router_rejects_clear_non_health_topics(registry, message):
    decision = RulesRouter(registry).decide([message])

    assert decision.action == "unsupported"
    assert decision.tool is None
    assert "focused on health" in decision.response.lower()


@pytest.mark.parametrize(
    "message",
    ["Hi", "How can I improve my sleep habits?", "How to play cricket"],
)
def test_hybrid_fast_paths_do_not_wait_for_qwen(registry, message):
    qwen = QwenJsonRouter(lambda _prompt: (_ for _ in ()).throw(AssertionError("Qwen should not be invoked")))

    decision = HybridRouter(qwen, RulesRouter(registry)).decide([message])

    assert decision.source == "rules"
    assert decision.response


@pytest.mark.parametrize(
    "message",
    ["I have acidity and reflux", "I have heartburn", "I have had a fever since yesterday"],
)
def test_rules_router_starts_generic_symptom_interview(registry, message):
    decision = RulesRouter(registry).decide([message])

    assert decision.action == "respond"
    assert decision.mode == "symptom_interview"
    assert decision.tool is None
    assert "?" in decision.response


def test_rules_router_tolerates_voice_misspelling_of_heartburn(registry):
    decision = RulesRouter(registry).decide(["having hurt burn isses"])

    assert decision.mode == "symptom_interview"
    assert decision.tool is None
    assert "burning or reflux" in decision.response.lower()


def test_rules_router_does_not_repeat_compound_fever_question(registry):
    question = SYMPTOM_FOLLOWUPS["fever"][2]
    decision = RulesRouter(registry).decide(
        [
            "I have a high fever and cough",
            f"[HealthAI follow-up] {question}",
            "It is worsening with a sore throat",
        ]
    )

    assert decision.mode == "symptom_interview"
    assert decision.response != question


def test_hybrid_accepts_only_bounded_qwen_symptom_followup(registry):
    qwen = QwenJsonRouter(
        lambda _prompt: OrchestrationDecision(
            action="respond",
            mode="symptom_interview",
            response="How long has the fever been present, and what was the highest measured temperature?",
        ).model_dump_json()
    )
    decision = HybridRouter(qwen, RulesRouter(registry)).decide(["I have a fever"])

    assert decision.source == "qwen"
    assert decision.mode == "symptom_interview"


def test_hybrid_rejects_diagnostic_or_treatment_response(registry):
    qwen = QwenJsonRouter(
        lambda _prompt: OrchestrationDecision(
            action="respond",
            mode="symptom_interview",
            response="You likely have flu. Take medicine twice daily?",
        ).model_dump_json()
    )
    decision = HybridRouter(qwen, RulesRouter(registry)).decide(["I have a fever"])

    assert decision.source == "rules"
    assert "likely" not in decision.response.lower()


def test_production_symptom_selector_can_only_return_curated_wording(registry):
    class FakeRunner:
        @staticmethod
        def select_symptom_question(_messages, candidates):
            return "reflux_2"

    selector = QwenSymptomQuestionSelector(FakeRunner())
    qwen = QwenJsonRouter(lambda _prompt: "this path must not run")
    decision = HybridRouter(qwen, RulesRouter(registry), selector).decide(["I have acidity"])

    assert decision.source == "qwen"
    assert decision.mode == "symptom_interview"
    assert decision.response == SYMPTOM_FOLLOWUPS["reflux"][1]


def test_general_selector_must_begin_with_the_foundational_question():
    class FakeRunner:
        @staticmethod
        def select_symptom_question(_messages, candidates):
            raise AssertionError(f"single candidate should not invoke Qwen: {candidates}")

    decision = QwenSymptomQuestionSelector(FakeRunner()).decide(
        ["I have a health issue that is hard to describe"],
        "general",
    )

    assert decision.response == SYMPTOM_FOLLOWUPS["general"][0]


def test_incomplete_tool_call_is_blocked(registry):
    decision = OrchestrationDecision(
        action="call_tool",
        tool="diabetes_risk",
        arguments={"age": 42},
        missing_fields=[field for field in registry.required_fields("diabetes_risk") if field != "age"],
        source="rules",
    )

    with pytest.raises(DecisionPolicyError, match="cannot run"):
        DecisionPolicyValidator(registry).validate(decision)


def test_invalid_qwen_output_uses_deterministic_fallback(registry):
    router = FallbackRouter(
        QwenJsonRouter(lambda _prompt: "not valid json"),
        RulesRouter(registry),
    )

    decision = router.decide(["I am worried about diabetes and blood sugar"])

    assert decision.source == "rules"
    assert decision.tool == "diabetes_risk"


@pytest.mark.parametrize(
    "message",
    [
        "Hi.",
        "how are you?",
        "Hey, what's up? Hope you're doing well.",
    ],
)
def test_rules_router_handles_natural_small_talk(registry, message):
    decision = RulesRouter(registry).decide([message])

    assert decision.action == "respond"
    assert decision.tool is None
    assert "No supported" not in decision.response


def test_rules_router_explains_unsupported_health_concern_naturally(registry):
    decision = RulesRouter(registry).decide(["Diagnose whether I have cancer"])

    assert decision.action == "unsupported"
    assert "can’t provide a diagnosis" in decision.response
    assert "clinical-intake pathway" in decision.response


def test_hybrid_selector_respects_a_newer_symptom_topic(registry):
    class FakeRunner:
        @staticmethod
        def select_symptom_question(_messages, candidates):
            assert candidates
            assert all(question_id.startswith("fever_") for question_id in candidates)
            return next(iter(candidates))

    router = HybridRouter(
        QwenJsonRouter(lambda _prompt: "this path must not run"),
        RulesRouter(registry),
        QwenSymptomQuestionSelector(FakeRunner()),
    )
    decision = router.decide(
        [
            "I have heartburn",
            f"[HealthAI follow-up] {SYMPTOM_FOLLOWUPS['reflux'][0]}",
            "I'm having a high fever and cough now",
        ]
    )

    assert decision.mode == "symptom_interview"
    assert decision.response in SYMPTOM_FOLLOWUPS["fever"]


def test_hybrid_does_not_override_urgent_fever_disposition(registry):
    class FailingRunner:
        @staticmethod
        def select_symptom_question(_messages, _candidates):
            raise AssertionError("question selector must not override urgent disposition")

    router = HybridRouter(
        QwenJsonRouter(lambda _prompt: "this path must not run"),
        RulesRouter(registry),
        QwenSymptomQuestionSelector(FailingRunner()),
    )
    decision = router.decide(["My high fever is worsening and I am immunosuppressed"])

    assert "urgent same-day assessment" in decision.response


def test_unknown_fields_are_blocked(registry):
    required = registry.required_fields("heart_risk")
    decision = OrchestrationDecision(
        action="ask_question",
        tool="heart_risk",
        known_fields={"diagnosis": "heart disease"},
        missing_fields=required,
        source="qwen",
    )

    with pytest.raises(DecisionPolicyError, match="Unknown fields"):
        DecisionPolicyValidator(registry).validate(decision)


def test_conversational_response_cannot_smuggle_tool_arguments(registry):
    decision = OrchestrationDecision(
        action="respond",
        known_fields={"age": 55},
        response="Hello",
        source="qwen",
    )

    with pytest.raises(DecisionPolicyError, match="cannot include"):
        DecisionPolicyValidator(registry).validate(decision)


def test_hybrid_router_preserves_supported_route_and_evidence(registry):
    qwen = QwenJsonRouter(
        lambda _prompt: OrchestrationDecision(
            action="respond",
            known_fields={"age": 54, "resting_bp": 145},
            field_evidence={"age": "54", "resting_bp": "BP is 145"},
            response="I noticed two values.",
        ).model_dump_json()
    )
    decision = HybridRouter(qwen, RulesRouter(registry)).decide(["I am 54 and my BP is 145; check my heart risk"])

    assert decision.tool == "heart_risk"
    assert decision.action == "ask_question"
    assert decision.known_fields == {"age": 54, "resting_bp": 145}
    assert "2 explicit values" in decision.response


def test_hybrid_router_supplements_explicit_heart_measurements(registry):
    qwen = QwenJsonRouter(
        lambda _prompt: OrchestrationDecision(
            action="ask_question",
            tool="heart_risk",
            known_fields={"age": 54},
            field_evidence={"age": "54"},
            response="Continue.",
        ).model_dump_json()
    )
    decision = HybridRouter(qwen, RulesRouter(registry)).decide(
        ["I am 54, my blood pressure is 145 and cholesterol is 240. Check my heart risk."]
    )

    assert decision.known_fields == {
        "age": 54,
        "resting_bp": 145,
        "serum_cholesterol": 240,
    }
    assert decision.field_evidence == {
        "age": "54",
        "resting_bp": "blood pressure is 145",
        "serum_cholesterol": "cholesterol is 240",
    }


def test_hybrid_routes_hypertension_and_vessel_blockage_without_waiting_for_qwen(registry):
    qwen = QwenJsonRouter(lambda _prompt: (_ for _ in ()).throw(AssertionError("Qwen should not be invoked")))

    decision = HybridRouter(qwen, RulesRouter(registry)).decide(
        ["I have hypertension and sometimes blockage in blood vessels"]
    )

    assert decision.tool == "heart_risk"
    assert decision.mode == "screening"
    assert decision.source == "rules"


def test_hybrid_router_does_not_allow_freeform_medical_response(registry):
    qwen = QwenJsonRouter(
        lambda _prompt: OrchestrationDecision(
            action="respond",
            response="Here is an invented treatment.",
        ).model_dump_json()
    )
    decision = HybridRouter(qwen, RulesRouter(registry)).decide(["My knee hurts"])

    assert decision.action == "respond"
    assert decision.mode == "symptom_interview"
    assert "invented treatment" not in decision.response
    assert decision.source == "rules"
