import json
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

from .registry import ASSESSMENTS, MODEL_CATALOG


class ModelUnavailable(RuntimeError):
    pass


class InvalidAssessment(ValueError):
    pass


class PredictionService:
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self._sessions: dict[str, ort.InferenceSession] = {}

    def metadata(self, condition: str) -> dict[str, Any] | None:
        path = self.artifacts_dir / f"{condition}.metadata.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _session(self, condition: str) -> ort.InferenceSession:
        if condition in self._sessions:
            return self._sessions[condition]
        path = self.artifacts_dir / f"{condition}.onnx"
        if not path.exists():
            raise ModelUnavailable(f"The {condition} research model has not been trained on this deployment.")
        self._sessions[condition] = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        return self._sessions[condition]

    def catalog(self):
        summaries = []
        for item in MODEL_CATALOG:
            data = item.model_dump()
            metadata = self.metadata(item.slug)
            if metadata:
                data.update(
                    status=metadata.get("validation_status", "research"),
                    version=metadata.get("version", "unknown"),
                    metrics=metadata.get("metrics", {}),
                )
            summaries.append(data)
        return summaries

    def predict(self, condition: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assessment = ASSESSMENTS.get(condition)
        if assessment is None:
            raise InvalidAssessment(
                "Only the registered heart, diabetes, kidney and liver research tools are supported."
            )
        metadata = self.metadata(condition)
        if metadata is None:
            raise ModelUnavailable(f"The {condition} model artifact is unavailable. Run the training pipeline first.")
        expected = metadata["feature_order"]
        if set(inputs) != set(expected):
            missing = sorted(set(expected) - set(inputs))
            extra = sorted(set(inputs) - set(expected))
            raise InvalidAssessment(f"Input fields do not match the model. Missing={missing}; extra={extra}")
        fields = {field.name: field for field in assessment["fields"]}
        values = []
        for name in expected:
            try:
                value = float(inputs[name])
            except (TypeError, ValueError) as exc:
                raise InvalidAssessment(f"{name} must be numeric.") from exc
            field = fields[name]
            if field.minimum is not None and value < field.minimum:
                raise InvalidAssessment(f"{field.label} is below the supported range.")
            if field.maximum is not None and value > field.maximum:
                raise InvalidAssessment(f"{field.label} is above the supported range.")
            if field.options and value not in {float(option.value) for option in field.options}:
                raise InvalidAssessment(f"{field.label} contains an unsupported option.")
            values.append(value)
        session = self._session(condition)
        output = session.run(None, {session.get_inputs()[0].name: np.asarray([values], dtype=np.float32)})
        probabilities = np.asarray(output[1])
        probability = float(probabilities[0][-1])
        threshold = float(metadata["threshold"])
        return {
            "condition": condition,
            "band": "elevated" if probability >= threshold else "lower",
            "probability": round(probability, 4),
            "threshold": threshold,
            "model_version": metadata["version"],
            "validation_status": metadata.get("validation_status", "research"),
            "limitations": metadata.get("limitations", []),
            "inputs": {name: inputs[name] for name in expected},
            "metrics": metadata.get("metrics", {}),
            "dataset": metadata.get("dataset", {}),
        }
