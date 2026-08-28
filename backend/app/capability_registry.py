import json
from pathlib import Path

from .schemas import ToolSummary


def conversation_and_imaging_tools(artifacts_dir: Path) -> list[ToolSummary]:
    pneumonia_metadata_path = artifacts_dir / "pneumonia.metadata.json"
    pneumonia_available = (artifacts_dir / "pneumonia.onnx").is_file() and pneumonia_metadata_path.is_file()
    pneumonia_metadata = json.loads(pneumonia_metadata_path.read_text(encoding="utf-8")) if pneumonia_available else {}
    return [
        ToolSummary(
            slug="symptom_interview",
            name="Stateful clinical-intake reasoning",
            kind="retrieval",
            version="bounded-interview-v3",
            deployment_status="available",
            callable=True,
            description=(
                "Qwen-guided selection from reviewed follow-up protocols, structured evidence accumulation, "
                "and deterministic emergency and disposition policy."
            ),
            supported_population="General educational intake for adults; not a diagnostic assessment.",
            confidence_policy=(
                "Ask one bounded follow-up at a time. Never produce a diagnosis, probability, "
                "prescription or medication dose."
            ),
            report_sections=["reported concern", "follow-up context", "safety boundary", "next step"],
            limitations=[
                "The interview cannot determine the cause of a symptom or rule out serious illness.",
                "Free-form wording, language differences and missing context can change the selected pathway.",
            ],
        ),
        ToolSummary(
            slug="wellness_guidance",
            name="General wellness guidance",
            kind="retrieval",
            version="bounded-wellness-v1",
            deployment_status="available",
            callable=True,
            description="Bounded education for sleep, hydration, physical activity and balanced nutrition.",
            supported_population="General adult educational use.",
            confidence_policy="No therapeutic diet, medicine, diagnosis or prevention claim.",
            limitations=["Guidance is generic and is not personalized medical advice."],
        ),
        ToolSummary(
            slug="pneumonia_xray",
            name="Pneumonia chest X-ray screening",
            kind="predictive_model",
            version=str(pneumonia_metadata.get("version", "training-required")),
            deployment_status="experimental" if pneumonia_available else "planned",
            callable=pneumonia_available,
            description="Compact ONNX image baseline trained reproducibly on the official PneumoniaMNIST split.",
            supported_population="Pediatric chest X-rays represented in PneumoniaMNIST; adults are unsupported.",
            confidence_policy="Accept a reviewed chest X-ray image only; return a research pattern score, never a radiology diagnosis.",
            validation_metrics=pneumonia_metadata.get("metrics", {}),
            report_sections=["image preprocessing", "screening result", "model metrics", "limitations"],
            limitations=pneumonia_metadata.get(
                "limitations",
                ["Training and evaluation artifacts are required before this tool can execute."],
            ),
        ),
        ToolSummary(
            slug="skin_image_triage",
            name="Skin-image intake",
            kind="predictive_model",
            version="dataset-required",
            deployment_status="planned",
            callable=False,
            description="Planned image-quality and referral-priority research workflow; no disease classifier is attached.",
            supported_population="Not established.",
            confidence_policy="Do not infer a skin diagnosis from an uploaded photograph.",
            limitations=[
                "Lighting, skin tone, camera processing and lesion framing create substantial distribution shift.",
                "A licensed, diverse dataset and clinician-reviewed evaluation are required before activation.",
            ],
        ),
    ]
