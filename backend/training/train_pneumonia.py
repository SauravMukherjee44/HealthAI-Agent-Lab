"""Train a compact, reproducible PneumoniaMNIST image baseline.

This is an educational pediatric chest X-ray benchmark, not a clinical model.
"""

import argparse
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

import certifi
import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from sklearn.linear_model import LogisticRegression

from .train_models import choose_threshold, metrics

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "backend" / "artifacts"
DATASET_URL = "https://zenodo.org/records/10519652/files/pneumoniamnist.npz?download=1"
DATASET_MD5 = "28209eda62fecd6e6a2d98b1501bb15f"
os.environ.setdefault("SSL_CERT_FILE", certifi.where())


def _download() -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="pneumoniamnist-", suffix=".npz", delete=False)
    path = Path(handle.name)
    try:
        with urlopen(DATASET_URL, timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
    finally:
        handle.close()
    if hashlib.md5(path.read_bytes()).hexdigest() != DATASET_MD5:  # noqa: S324 - published integrity hash
        path.unlink(missing_ok=True)
        raise RuntimeError("PneumoniaMNIST integrity check failed.")
    return path


def _prepare(images: np.ndarray) -> np.ndarray:
    return images.reshape(len(images), -1).astype(np.float32) / 255.0


def train(output_dir: Path) -> dict:
    dataset_path = _download()
    try:
        with np.load(dataset_path) as data:
            x_train = _prepare(data["train_images"])
            y_train = data["train_labels"].reshape(-1).astype(np.int64)
            x_validation = _prepare(data["val_images"])
            y_validation = data["val_labels"].reshape(-1).astype(np.int64)
            x_test = _prepare(data["test_images"])
            y_test = data["test_labels"].reshape(-1).astype(np.int64)
    finally:
        dataset_path.unlink(missing_ok=True)

    candidates = {}
    models = {}
    for c_value in (0.01, 0.1, 1.0):
        name = f"logistic_c_{c_value:g}"
        model = LogisticRegression(
            C=c_value,
            max_iter=1500,
            class_weight="balanced",
            random_state=44,
        )
        model.fit(x_train, y_train)
        scores = model.predict_proba(x_validation)[:, 1]
        threshold = choose_threshold(y_validation, scores)
        measured = metrics(y_validation, scores, threshold)
        candidates[name] = {"threshold": round(threshold, 4), "metrics": measured}
        models[name] = model

    selected = max(
        candidates,
        key=lambda name: (
            candidates[name]["metrics"]["auroc"],
            candidates[name]["metrics"]["auprc"],
            -candidates[name]["metrics"]["brier"],
        ),
    )
    model = models[selected]
    threshold = candidates[selected]["threshold"]
    test_scores = model.predict_proba(x_test)[:, 1]
    test_metrics = metrics(y_test, test_scores, threshold)

    output_dir.mkdir(parents=True, exist_ok=True)
    converted = convert_sklearn(
        model,
        initial_types=[("features", FloatTensorType([None, 28 * 28]))],
        target_opset=17,
        options={id(model): {"zipmap": False}},
    )
    (output_dir / "pneumonia.onnx").write_bytes(converted.SerializeToString())
    metadata = {
        "slug": "pneumonia",
        "version": "pneumoniamnist-logistic-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "validation_status": "research",
        "feature_order": ["28x28_grayscale_pixels"],
        "image_size": [28, 28],
        "threshold": threshold,
        "metrics": test_metrics,
        "model_selection": {
            "selected": selected,
            "selection_set": "official-validation-only",
            "candidates": candidates,
        },
        "dataset": {
            "name": "MedMNIST v2 PneumoniaMNIST",
            "doi": "10.5281/zenodo.10519652",
            "license": "CC BY 4.0",
            "instances": int(len(x_train) + len(x_validation) + len(x_test)),
            "split": {
                "train": int(len(x_train)),
                "validation": int(len(x_validation)),
                "test": int(len(x_test)),
            },
        },
        "limitations": [
            "The benchmark contains pediatric chest X-rays and must not be generalized to adults.",
            "Images are center-cropped and reduced to 28×28 pixels, discarding clinically important detail.",
            "The source test split may share acquisition characteristics with training data.",
            "The service relies on user confirmation that the upload is a pediatric chest X-ray; it has no independent modality detector.",
            "The model cannot identify alternative diagnoses and cannot replace radiologist interpretation.",
            "Performance has not been established prospectively or on an external hospital cohort.",
        ],
    }
    (output_dir / "pneumonia.metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(train(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
