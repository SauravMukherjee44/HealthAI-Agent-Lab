from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Locale(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"


class FieldOption(BaseModel):
    value: int | float | str
    label: str


class AssessmentField(BaseModel):
    name: str
    label: str
    field_type: Literal["number", "select"] = "number"
    hint: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    options: list[FieldOption] = Field(default_factory=list)


class TriageStartRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1200)
    locale: Locale = Locale.ENGLISH

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        return " ".join(value.strip().split())


class TriageMessageRequest(TriageStartRequest):
    state_token: str


class TriageResponse(BaseModel):
    state_token: str
    response: str
    status: Literal["collecting", "ready", "emergency", "unsupported"]
    condition: str | None = None
    required_fields: list[AssessmentField] = Field(default_factory=list)
    emergency: bool = False
    disclaimer: str
    decision: "OrchestrationDecision | None" = None
    known_fields: dict[str, Any] = Field(default_factory=dict)


class OrchestrationDecision(BaseModel):
    """The only command shape a language-model router may produce."""

    action: Literal["respond", "ask_question", "call_tool", "explain_result", "escalate", "unsupported"]
    tool: (
        Literal[
            "heart_risk",
            "diabetes_risk",
            "kidney_risk",
            "liver_risk",
            "calculator",
        ]
        | None
    ) = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    known_fields: dict[str, Any] = Field(default_factory=dict)
    field_evidence: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    response: str = ""
    source: Literal["rules", "qwen"] = "rules"
    mode: Literal["conversation", "wellness", "symptom_interview", "screening"] = "conversation"


class ToolSummary(BaseModel):
    slug: str
    name: str
    kind: Literal["predictive_model", "deterministic", "retrieval", "export", "asr"]
    version: str
    deployment_status: Literal["available", "experimental", "planned", "unavailable"]
    callable: bool
    description: str
    required_fields: list[str] = Field(default_factory=list)
    supported_population: str
    validation_metrics: dict[str, float | int | str] = Field(default_factory=dict)
    confidence_policy: str
    report_sections: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PredictionRequest(BaseModel):
    inputs: dict[str, Any]
    state_token: str | None = None


class PredictionResult(BaseModel):
    condition: str
    band: Literal["lower", "elevated", "indeterminate"]
    probability: float | None
    threshold: float | None
    model_version: str
    validation_status: str
    limitations: list[str]
    report_token: str


class ReportExportRequest(BaseModel):
    report_token: str
    alias: str | None = Field(default=None, max_length=80)

    @field_validator("alias")
    @classmethod
    def clean_alias(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class ModelSummary(BaseModel):
    slug: str
    name: str
    status: Literal["validated", "research", "legacy", "unavailable"]
    version: str
    description: str
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
