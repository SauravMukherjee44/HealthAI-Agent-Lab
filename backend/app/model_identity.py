"""Canonical public identities for HealthAI model releases.

Stable API/tool slugs remain deliberately separate from public names so a model
can be upgraded without breaking callers or saved browser sessions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelIdentity:
    display_name: str
    release: str
    release_id: str
    base_model: str


MODEL_IDENTITIES = {
    "heart": ModelIdentity("HealthAI Cardio 2.0", "2.0", "healthai-cardio-v2.0.0", "UCI Statlog Heart · selected ONNX pipeline"),
    "diabetes": ModelIdentity("HealthAI Glyco 2.0", "2.0", "healthai-glyco-v2.0.0", "UCI Early Stage Diabetes · selected ONNX pipeline"),
    "kidney": ModelIdentity("HealthAI Renal 2.0", "2.0", "healthai-renal-v2.0.0", "UCI Chronic Kidney Disease · selected ONNX pipeline"),
    "liver": ModelIdentity("HealthAI Hepatic 2.0", "2.0", "healthai-hepatic-v2.0.0", "UCI Indian Liver Patient · selected ONNX pipeline"),
    "pneumonia": ModelIdentity("HealthAI PulmoVision 1.0", "1.0", "healthai-pulmovision-v1.0.0", "PneumoniaMNIST · logistic ONNX baseline"),
    "stroke": ModelIdentity("HealthAI Neuro 0.1", "0.1", "healthai-neuro-v0.1.0", "Retired legacy research artifact"),
    "reasoner": ModelIdentity("HealthAI Reasoner 1.0", "1.0", "healthai-reasoner-v1.0.0", "Qwen3-0.6B Q8 · llama.cpp"),
    "voice": ModelIdentity("HealthAI Voice 1.0", "1.0", "healthai-voice-v1.0.0", "Moonshine Tiny Streaming English · 34M"),
}


def model_identity(slug: str) -> ModelIdentity:
    return MODEL_IDENTITIES[slug]
