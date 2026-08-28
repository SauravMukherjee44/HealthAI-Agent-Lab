import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["HEALTHAI_ORCHESTRATOR_BACKEND"] = "rules"

from backend.app.main import app
from backend.app.predictions import ModelUnavailable, PredictionService

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_runtime_warmup_is_content_free_and_disabled_for_rules_backend():
    response = client.post("/api/v1/runtime/warm")
    assert response.status_code == 200
    assert response.json() == {"status": "disabled"}


def test_model_catalog_uses_canonical_versioned_names():
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    models = {model["slug"]: model for model in response.json()["models"]}
    assert models["heart"]["name"] == "HealthAI Cardio 2.0"
    assert models["heart"]["version"] == "healthai-cardio-v2.0.0"
    assert models["diabetes"]["name"] == "HealthAI Glyco 2.0"
    assert models["kidney"]["name"] == "HealthAI Renal 2.0"
    assert models["liver"]["name"] == "HealthAI Hepatic 2.0"
    assert models["pneumonia"]["name"] == "HealthAI PulmoVision 1.0"


def test_tool_registry_exposes_only_artifact_backed_tools_as_callable():
    response = client.get("/api/v1/tools")
    assert response.status_code == 200
    payload = response.json()
    assert payload["orchestrator"]["active_backend"] == "rules"
    assert payload["orchestrator"]["qwen_status"] == "disabled"
    assert payload["orchestrator"]["policy_validation"] == "enforced"
    assert payload["orchestrator"]["emergency_gate"] == "deterministic-pre-routing"
    tools = {tool["slug"]: tool for tool in payload["tools"]}
    assert {
        "heart_risk",
        "diabetes_risk",
        "kidney_risk",
        "liver_risk",
        "symptom_interview",
        "wellness_guidance",
        "pneumonia_xray",
        "skin_image_triage",
    } == set(tools)
    callable_slugs = {
        "heart_risk",
        "diabetes_risk",
        "kidney_risk",
        "liver_risk",
        "symptom_interview",
        "wellness_guidance",
    }
    assert all(tools[slug]["callable"] for slug in callable_slugs)
    assert tools["pneumonia_xray"]["callable"]
    assert tools["pneumonia_xray"]["deployment_status"] == "experimental"
    assert not tools["skin_image_triage"]["callable"]
    assert len(tools["heart_risk"]["required_fields"]) == 13
    assert len(tools["diabetes_risk"]["required_fields"]) == 16
    assert len(tools["kidney_risk"]["required_fields"]) == 24
    assert len(tools["liver_risk"]["required_fields"]) == 10


def test_ambiguous_intent_requests_a_choice_without_selecting_a_tool():
    response = client.post(
        "/api/v1/triage/start",
        json={"message": "I want both a heart and diabetes screening", "locale": "en"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting"
    assert payload["condition"] is None
    assert payload["decision"]["action"] == "ask_question"
    assert payload["decision"]["tool"] is None


def test_greeting_gets_a_natural_conversational_response():
    response = client.post("/api/v1/triage/start", json={"message": "Hi", "locale": "en"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting"
    assert payload["decision"]["action"] == "respond"
    assert "Hi" in payload["response"]


def test_natural_small_talk_works_across_multiple_turns():
    first = client.post(
        "/api/v1/triage/start",
        json={"message": "Hey, what's up? Hope you're doing well.", "locale": "en"},
    )
    assert first.status_code == 200
    assert first.json()["decision"]["action"] == "respond"

    second = client.post(
        "/api/v1/triage/message",
        json={"message": "Hi.", "locale": "en", "state_token": first.json()["state_token"]},
    )
    assert second.status_code == 200
    assert second.json()["decision"]["action"] == "respond"

    third = client.post(
        "/api/v1/triage/message",
        json={
            "message": "how are you?",
            "locale": "en",
            "state_token": second.json()["state_token"],
        },
    )
    assert third.status_code == 200
    assert third.json()["decision"]["action"] == "respond"
    assert "No supported" not in third.json()["response"]


def test_unsupported_concern_receives_a_helpful_boundary():
    response = client.post(
        "/api/v1/triage/start",
        json={
            "message": "Diagnose whether I have cancer",
            "locale": "en",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unsupported"
    assert "can’t provide a diagnosis" in response.json()["response"]
    assert "clinical-intake pathway" in response.json()["response"]


def test_acidity_and_fever_start_bounded_follow_up_interviews():
    for message in ("I have acidity and reflux", "I have a fever"):
        response = client.post(
            "/api/v1/triage/start",
            json={"message": message, "locale": "en"},
        )
        payload = response.json()
        assert payload["status"] == "collecting"
        assert payload["decision"]["mode"] == "symptom_interview"
        assert payload["decision"]["tool"] is None
        assert "?" in payload["response"]


@pytest.mark.parametrize(
    "message",
    [
        "I have nausea and bloating",
        "There is burning urination",
        "I feel dizzy and tired all the time",
        "My eye is red and painful",
        "I have a toothache",
        "My ankle is swollen",
        "I have unusual period pain",
        "I have a health issue that is hard to describe",
    ],
)
def test_broad_health_concerns_enter_a_clinical_intake_instead_of_dead_ending(message):
    payload = client.post(
        "/api/v1/triage/start",
        json={"message": message, "locale": "en"},
    ).json()

    assert payload["status"] == "collecting"
    assert payload["decision"]["mode"] == "symptom_interview"
    assert payload["decision"]["tool"] is None
    assert "don't have" not in payload["response"].lower()
    assert "?" in payload["response"]


def test_symptom_interview_does_not_repeat_the_previous_question():
    first = client.post(
        "/api/v1/triage/start",
        json={"message": "I have a fever", "locale": "en"},
    ).json()
    second = client.post(
        "/api/v1/triage/message",
        json={
            "message": "It was 39 C and I am an adult",
            "locale": "en",
            "state_token": first["state_token"],
        },
    ).json()

    assert second["decision"]["mode"] == "symptom_interview"
    assert second["response"] != first["response"]


def test_fever_interview_advances_and_escalates_immune_suppression_urgently():
    messages = [
        "having hurt burn isses",
        "i'm having high fever and cough",
        "worsening with sore throat",
        "yes immune supression",
    ]
    token = None
    responses = []
    for message in messages:
        path = "/api/v1/triage/message" if token else "/api/v1/triage/start"
        body = {"message": message, "locale": "en"}
        if token:
            body["state_token"] = token
        payload = client.post(path, json=body).json()
        token = payload["state_token"]
        responses.append(payload)

    assert responses[0]["decision"]["mode"] == "symptom_interview"
    assert "highest measured temperature" in responses[2]["response"]
    assert "urgent same-day assessment" in responses[3]["response"]
    assert responses[3]["emergency"] is False


def test_emergency_gate_combines_warning_signs_across_user_turns():
    first = client.post(
        "/api/v1/triage/start",
        json={"message": "I have a fever", "locale": "en"},
    ).json()
    second = client.post(
        "/api/v1/triage/message",
        json={"message": "I also have a stiff neck", "locale": "en", "state_token": first["state_token"]},
    ).json()

    assert second["emergency"] is True
    assert second["status"] == "emergency"


def test_fever_reasoning_preserves_partial_answers_and_synthesizes_disposition():
    messages = [
        "cough and sore throat with fever",
        "102 f",
        "since yesterday",
        "adult age 35",
        "yes cough and headache",
        "no stiff neck or confusion",
        "worsening",
        "no pregnancy, immune suppression, or chronic condition",
    ]
    token = None
    responses = []
    for message in messages:
        path = "/api/v1/triage/message" if token else "/api/v1/triage/start"
        body = {"message": message, "locale": "en"}
        if token:
            body["state_token"] = token
        payload = client.post(path, json=body).json()
        token = payload["state_token"]
        responses.append(payload)

    questions = [payload["response"] for payload in responses[:-1]]
    assert any("When did the fever start?" in question for question in questions)
    assert any("adult or a child" in question for question in questions)
    assert all(payload["emergency"] is False for payload in responses)
    final = responses[-1]["response"]
    assert "102F" in final
    assert "headache" in final
    assert "worsening" in final
    assert "assessed by a qualified clinician today" in final


def test_triage_routes_diabetes_and_returns_fields():
    response = client.post(
        "/api/v1/triage/start", json={"message": "I am very thirsty and worried about diabetes", "locale": "en"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["condition"] == "diabetes"
    assert payload["status"] == "ready"
    assert len(payload["required_fields"]) == 16
    assert payload["state_token"]


def test_triage_routes_hindi_heart_message():
    response = client.post("/api/v1/triage/start", json={"message": "मुझे हृदय और कोलेस्ट्रॉल जोखिम समझना है", "locale": "hi"})
    assert response.status_code == 200
    assert response.json()["condition"] == "heart"


def test_triage_routes_kidney_and_liver_tools():
    kidney = client.post(
        "/api/v1/triage/start",
        json={"message": "I have kidney lab results including creatinine", "locale": "en"},
    )
    liver = client.post(
        "/api/v1/triage/start",
        json={"message": "I want to review my liver bilirubin and ALT results", "locale": "en"},
    )

    assert kidney.json()["condition"] == "kidney"
    assert len(kidney.json()["required_fields"]) == 24
    assert liver.json()["condition"] == "liver"
    assert len(liver.json()["required_fields"]) == 10


def test_general_wellness_question_does_not_invoke_a_model():
    response = client.post(
        "/api/v1/triage/start",
        json={"message": "How can I improve my sleep habits?", "locale": "en"},
    )

    payload = response.json()
    assert payload["status"] == "collecting"
    assert payload["decision"]["action"] == "respond"
    assert payload["decision"]["tool"] is None


def test_emergency_gate_preempts_assessment():
    response = client.post(
        "/api/v1/triage/start", json={"message": "I have severe chest pain and cannot breathe", "locale": "en"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["emergency"] is True
    assert payload["status"] == "emergency"
    assert payload["required_fields"] == []
    assert "112" in payload["response"]


@pytest.mark.parametrize(
    "message",
    [
        "I am vomiting blood",
        "I have fever with a stiff neck and confusion",
        "This is the sudden worst headache of my life",
        "My lips are blue and I am gasping",
    ],
)
def test_additional_generic_symptom_red_flags_preempt_qwen(message):
    response = client.post(
        "/api/v1/triage/start",
        json={"message": message, "locale": "en"},
    )

    assert response.json()["status"] == "emergency"


def test_invalid_state_token_is_rejected():
    response = client.post(
        "/api/v1/triage/message", json={"message": "heart", "locale": "en", "state_token": "not-a-token"}
    )
    assert response.status_code == 400


def test_untrained_model_is_explicitly_unavailable(tmp_path):
    service = PredictionService(tmp_path)
    try:
        service.predict("heart", {})
    except ModelUnavailable as exc:
        assert "training pipeline" in str(exc)
    else:
        raise AssertionError("Missing model artifact must not silently fall back")


def test_prediction_and_report_exports_work_end_to_end():
    inputs = {
        "age": 54,
        "sex": 1,
        "chest_pain": 4,
        "resting_bp": 140,
        "serum_cholesterol": 239,
        "fasting_blood_sugar": 0,
        "resting_ecg": 0,
        "max_heart_rate": 160,
        "exercise_angina": 0,
        "oldpeak": 1.2,
        "st_slope": 2,
        "major_vessels": 0,
        "thal": 3,
    }
    prediction = client.post("/api/v1/assessments/heart/predict", json={"inputs": inputs})
    assert prediction.status_code == 200
    result = prediction.json()
    assert result["condition"] == "heart"
    assert result["model_name"] == "HealthAI Cardio 2.0"
    assert result["model_version"] == "healthai-cardio-v2.0.0"
    assert result["validation_status"] == "research"
    assert 0 <= result["probability"] <= 1
    assert result["report_token"]

    request = {"report_token": result["report_token"], "alias": "Sample User"}
    pdf = client.post("/api/v1/reports/pdf", json=request)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert "healthai-report.pdf" in pdf.headers["content-disposition"]

    workbook = client.post("/api/v1/reports/xlsx", json=request)
    assert workbook.status_code == 200
    assert workbook.content.startswith(b"PK")
    assert "healthai-report.xlsx" in workbook.headers["content-disposition"]


def test_voice_endpoint_fails_closed_without_model():
    response = client.post("/api/v1/voice/transcribe", files={"audio": ("clip.wav", b"RIFFinvalid", "audio/wav")})
    assert response.status_code == 422
    assert "valid WAV" in response.json()["detail"]


def test_voice_endpoint_rejects_non_wav_upload():
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("clip.webm", b"not-a-wav", "audio/webm")},
    )
    assert response.status_code == 415


def test_pneumonia_image_tool_runs_and_exports_provenance():
    image = Image.new("L", (256, 256))
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    response = client.post(
        "/api/v1/images/pneumonia/predict",
        files={"image": ("xray.png", buffer.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["condition"] == "pneumonia"
    assert payload["validation_status"] == "research"
    assert 0 <= payload["probability"] <= 1
    assert payload["report_token"]


def test_pneumonia_image_tool_rejects_invalid_or_tiny_files():
    unreadable = client.post(
        "/api/v1/images/pneumonia/predict",
        files={"image": ("xray.png", b"not-an-image", "image/png")},
    )
    tiny_image = Image.new("L", (32, 32))
    buffer = BytesIO()
    tiny_image.save(buffer, format="PNG")
    tiny = client.post(
        "/api/v1/images/pneumonia/predict",
        files={"image": ("tiny.png", buffer.getvalue(), "image/png")},
    )

    assert unreadable.status_code == 422
    assert tiny.status_code == 422
