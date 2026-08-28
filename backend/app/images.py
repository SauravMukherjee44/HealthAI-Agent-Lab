import json
from io import BytesIO
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, UnidentifiedImageError

from .predictions import ModelUnavailable


class InvalidMedicalImage(ValueError):
    pass


class ImagePredictionService:
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self._session: ort.InferenceSession | None = None

    def _load(self) -> tuple[ort.InferenceSession, dict]:
        model_path = self.artifacts_dir / "pneumonia.onnx"
        metadata_path = self.artifacts_dir / "pneumonia.metadata.json"
        if not model_path.is_file() or not metadata_path.is_file():
            raise ModelUnavailable("The reproducible pneumonia image model is unavailable.")
        if self._session is None:
            self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        return self._session, json.loads(metadata_path.read_text(encoding="utf-8"))

    def predict_pneumonia(self, content: bytes) -> dict:
        if not content:
            raise InvalidMedicalImage("The uploaded image is empty.")
        try:
            with Image.open(BytesIO(content)) as source:
                source.load()
                width, height = source.size
                image_format = source.format or "unknown"
                if width < 128 or height < 128:
                    raise InvalidMedicalImage("Use a chest X-ray image at least 128×128 pixels.")
                if width > 10_000 or height > 10_000:
                    raise InvalidMedicalImage("The image dimensions are too large.")
                grayscale = source.convert("L")
                edge = min(width, height)
                left = (width - edge) // 2
                top = (height - edge) // 2
                prepared = grayscale.crop((left, top, left + edge, top + edge)).resize((28, 28))
                values = np.asarray(prepared, dtype=np.float32).reshape(1, -1) / 255.0
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidMedicalImage("The file is not a readable JPEG or PNG image.") from exc

        session, metadata = self._load()
        output = session.run(None, {session.get_inputs()[0].name: values})
        probability = float(np.asarray(output[1])[0][-1])
        threshold = float(metadata["threshold"])
        return {
            "condition": "pneumonia",
            "band": "elevated" if probability >= threshold else "lower",
            "probability": round(probability, 4),
            "threshold": threshold,
            "model_version": metadata["version"],
            "validation_status": metadata.get("validation_status", "research"),
            "limitations": metadata.get("limitations", []),
            "inputs": {
                "file_format": image_format,
                "source_dimensions": f"{width}×{height}",
                "preprocessing": "center-crop, grayscale, resize 28×28",
            },
            "metrics": metadata.get("metrics", {}),
            "dataset": metadata.get("dataset", {}),
        }
