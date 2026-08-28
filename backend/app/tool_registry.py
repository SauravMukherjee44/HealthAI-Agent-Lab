from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .model_identity import model_identity
from .registry import ASSESSMENTS
from .schemas import ToolSummary


@dataclass(frozen=True)
class SpecialistTool:
    slug: str
    condition: str
    name: str
    description: str
    supported_population: str
    confidence_policy: str
    report_sections: tuple[str, ...]


SPECIALIST_TOOLS = {
    "heart_risk": SpecialistTool(
        slug="heart_risk",
        condition="heart",
        name=model_identity("heart").display_name,
        description="Deterministic ONNX inference over the versioned UCI Statlog Heart input schema.",
        supported_population="Research demonstration using adults represented in the UCI Statlog Heart dataset.",
        confidence_policy="Return lower/elevated only at the versioned threshold; never label the result as a diagnosis.",
        report_sections=("screening result", "inputs", "model metrics", "limitations", "next steps"),
    ),
    "diabetes_risk": SpecialistTool(
        slug="diabetes_risk",
        condition="diabetes",
        name=model_identity("diabetes").display_name,
        description="Deterministic ONNX inference over a versioned 16-field symptom schema.",
        supported_population="Research demonstration using adults represented in the UCI early-stage diabetes dataset.",
        confidence_policy="Return lower/elevated only at the versioned threshold; never label the result as a diagnosis.",
        report_sections=("screening result", "inputs", "model metrics", "limitations", "next steps"),
    ),
    "kidney_risk": SpecialistTool(
        slug="kidney_risk",
        condition="kidney",
        name=model_identity("kidney").display_name,
        description="Versioned ONNX inference over the 24-field UCI Chronic Kidney Disease schema.",
        supported_population="Research demonstration using the hospital population represented in the UCI Chronic Kidney Disease dataset.",
        confidence_policy="Require every laboratory and clinical field; return lower/elevated only at the versioned threshold and never diagnose CKD.",
        report_sections=("screening result", "inputs", "model metrics", "limitations", "next steps"),
    ),
    "liver_risk": SpecialistTool(
        slug="liver_risk",
        condition="liver",
        name=model_identity("liver").display_name,
        description="Versioned ONNX inference over the 10-field UCI ILPD laboratory schema.",
        supported_population="Research demonstration using patients represented in the UCI Indian Liver Patient Dataset.",
        confidence_policy="Require reviewed laboratory values; return lower/elevated only at the versioned threshold and never diagnose liver disease.",
        report_sections=("screening result", "inputs", "model metrics", "limitations", "next steps"),
    ),
}


class SpecialistToolRegistry:
    """Single source of truth for tools the orchestrator is permitted to request."""

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir

    def get(self, slug: str) -> SpecialistTool | None:
        return SPECIALIST_TOOLS.get(slug)

    def required_fields(self, slug: str) -> list[str]:
        tool = self.get(slug)
        if tool is None:
            return []
        return [field.name for field in ASSESSMENTS[tool.condition]["fields"]]

    def is_callable(self, slug: str) -> bool:
        tool = self.get(slug)
        return bool(
            tool
            and (self.artifacts_dir / f"{tool.condition}.onnx").is_file()
            and (self.artifacts_dir / f"{tool.condition}.metadata.json").is_file()
        )

    def condition_for(self, slug: str) -> str | None:
        tool = self.get(slug)
        return tool.condition if tool else None

    def slug_for_condition(self, condition: str) -> str | None:
        return next((slug for slug, tool in SPECIALIST_TOOLS.items() if tool.condition == condition), None)

    def catalog(self) -> list[ToolSummary]:
        return [self._summary(tool) for tool in SPECIALIST_TOOLS.values()]

    def _summary(self, tool: SpecialistTool) -> ToolSummary:
        metadata = self._metadata(tool.condition)
        available = self.is_callable(tool.slug)
        return ToolSummary(
            slug=tool.slug,
            name=tool.name,
            kind="predictive_model",
            version=str(metadata.get("version", "artifact-required")),
            deployment_status="available" if available else "unavailable",
            callable=available,
            description=tool.description,
            required_fields=self.required_fields(tool.slug),
            supported_population=tool.supported_population,
            validation_metrics=metadata.get("metrics", {}),
            confidence_policy=tool.confidence_policy,
            report_sections=list(tool.report_sections),
            limitations=metadata.get("limitations", []),
        )

    def _metadata(self, condition: str) -> dict[str, Any]:
        path = self.artifacts_dir / f"{condition}.metadata.json"
        if not path.is_file():
            return {}
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    def run_screening(self, slug: str, inputs: dict[str, Any], prediction_service) -> dict[str, Any]:
        tool = self.get(slug)
        if tool is None or not self.is_callable(slug):
            raise ValueError(f"Tool {slug!r} is not callable.")
        return prediction_service.predict(tool.condition, inputs)


ToolAction = Literal["heart_risk", "diabetes_risk", "kidney_risk", "liver_risk"]
