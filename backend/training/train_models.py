"""Train reproducible research models from licensed UCI datasets.

These compact baselines intentionally favour reproducibility and calibrated
probabilities over leaderboard performance. They are educational screening
models and are not clinically validated medical devices.
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import certifi
import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from ucimlrepo import fetch_ucirepo

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "backend" / "artifacts"
os.environ.setdefault("SSL_CERT_FILE", certifi.where())


def choose_threshold(y_true: np.ndarray, scores: np.ndarray, minimum_sensitivity: float = 0.90) -> float:
    candidates = np.linspace(0.05, 0.95, 181)
    eligible: list[tuple[float, float]] = []
    for threshold in candidates:
        predicted = scores >= threshold
        tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
        sensitivity = tp / (tp + fn) if tp + fn else 0.0
        specificity = tn / (tn + fp) if tn + fp else 0.0
        if sensitivity >= minimum_sensitivity:
            eligible.append((specificity, float(threshold)))
    return max(eligible)[1] if eligible else 0.5


def metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float]:
    predicted = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "auroc": round(float(roc_auc_score(y_true, scores)), 4),
        "auprc": round(float(average_precision_score(y_true, scores)), 4),
        "sensitivity": round(float(tp / (tp + fn)) if tp + fn else 0.0, 4),
        "specificity": round(float(tn / (tn + fp)) if tn + fp else 0.0, 4),
        "ppv": round(float(tp / (tp + fp)) if tp + fp else 0.0, 4),
        "npv": round(float(tn / (tn + fn)) if tn + fn else 0.0, 4),
        "brier": round(float(brier_score_loss(y_true, scores)), 4),
        "test_samples": int(len(y_true)),
    }


def prepare_heart():
    dataset = fetch_ucirepo(id=145)
    features = dataset.data.features.copy()
    feature_order = [
        "age",
        "sex",
        "chest_pain",
        "resting_bp",
        "serum_cholesterol",
        "fasting_blood_sugar",
        "resting_ecg",
        "max_heart_rate",
        "exercise_angina",
        "oldpeak",
        "st_slope",
        "major_vessels",
        "thal",
    ]
    rename = dict(zip(features.columns, feature_order, strict=True))
    features = features.rename(columns=rename).astype(np.float32)
    raw_target = dataset.data.targets.iloc[:, 0]
    target = (raw_target.astype(float) > 1).astype(np.int64).to_numpy()
    return (
        "heart",
        features[feature_order].to_numpy(dtype=np.float32),
        target,
        feature_order,
        {
            "name": "UCI Statlog (Heart)",
            "doi": "10.24432/C57303",
            "license": "CC BY 4.0",
            "instances": int(len(features)),
        },
        [
            "The dataset contains only 270 historical records and may not represent the Indian population.",
            "The model uses clinical measurements that require professional collection and interpretation.",
            "Performance has not been established prospectively or in an external clinical cohort.",
        ],
    )


def prepare_diabetes():
    dataset = fetch_ucirepo(id=529)
    features = dataset.data.features.copy()
    feature_order = [
        "age",
        "gender",
        "polyuria",
        "polydipsia",
        "sudden_weight_loss",
        "weakness",
        "polyphagia",
        "genital_thrush",
        "visual_blurring",
        "itching",
        "irritability",
        "delayed_healing",
        "partial_paresis",
        "muscle_stiffness",
        "alopecia",
        "obesity",
    ]
    features.columns = feature_order
    for column in feature_order[1:]:
        if column == "gender":
            features[column] = features[column].astype(str).str.lower().map({"female": 0, "male": 1})
        else:
            features[column] = features[column].astype(str).str.lower().map({"no": 0, "yes": 1})
    features = features.astype(np.float32)
    target = (
        dataset.data.targets.iloc[:, 0]
        .astype(str)
        .str.lower()
        .map({"negative": 0, "positive": 1})
        .astype(np.int64)
        .to_numpy()
    )
    return (
        "diabetes",
        features[feature_order].to_numpy(dtype=np.float32),
        target,
        feature_order,
        {
            "name": "UCI Early Stage Diabetes Risk Prediction",
            "doi": "10.24432/C5VG8H",
            "license": "CC BY 4.0",
            "instances": int(len(features)),
        },
        [
            "The questionnaire dataset contains 520 participants from a single hospital in Bangladesh.",
            "Symptoms overlap with many other conditions and cannot establish a diabetes diagnosis.",
            "Performance has not been established prospectively or in an external Indian cohort.",
        ],
    )


def prepare_liver():
    dataset = fetch_ucirepo(id=225)
    features = dataset.data.features.copy()
    feature_order = [
        "age",
        "gender",
        "total_bilirubin",
        "direct_bilirubin",
        "alkaline_phosphatase",
        "alanine_aminotransferase",
        "aspartate_aminotransferase",
        "total_proteins",
        "albumin",
        "albumin_globulin_ratio",
    ]
    features.columns = feature_order
    features["gender"] = features["gender"].astype(str).str.strip().str.lower().map({"female": 0, "male": 1})
    features = features.apply(lambda column: np.asarray(column, dtype=np.float32))
    target = (dataset.data.targets.iloc[:, 0].astype(int) == 1).astype(np.int64).to_numpy()
    return (
        "liver",
        features[feature_order].to_numpy(dtype=np.float32),
        target,
        feature_order,
        {
            "name": "UCI ILPD (Indian Liver Patient Dataset)",
            "doi": "10.24432/C5D02C",
            "license": "CC BY 4.0",
            "instances": int(len(features)),
        },
        [
            "The dataset contains 583 historical records from north-east Andhra Pradesh and is not nationally representative.",
            "The cohort is sex-imbalanced (441 male and 142 female records), and published work has identified sex-related performance concerns.",
            "The inputs are laboratory measurements that require professional collection and interpretation.",
            "Performance has not been established prospectively or in an external clinical cohort.",
        ],
    )


def prepare_kidney():
    dataset = fetch_ucirepo(id=336)
    features = dataset.data.features.copy()
    feature_order = [
        "age",
        "blood_pressure",
        "specific_gravity",
        "albumin",
        "sugar",
        "red_blood_cells",
        "pus_cell",
        "pus_cell_clumps",
        "bacteria",
        "blood_glucose_random",
        "blood_urea",
        "serum_creatinine",
        "sodium",
        "potassium",
        "hemoglobin",
        "packed_cell_volume",
        "white_blood_cell_count",
        "red_blood_cell_count",
        "hypertension",
        "diabetes_mellitus",
        "coronary_artery_disease",
        "appetite",
        "pedal_edema",
        "anemia",
    ]
    features.columns = feature_order
    mappings = {
        "red_blood_cells": {"normal": 0, "abnormal": 1},
        "pus_cell": {"normal": 0, "abnormal": 1},
        "pus_cell_clumps": {"notpresent": 0, "present": 1},
        "bacteria": {"notpresent": 0, "present": 1},
        "hypertension": {"no": 0, "yes": 1},
        "diabetes_mellitus": {"no": 0, "yes": 1},
        "coronary_artery_disease": {"no": 0, "yes": 1},
        "appetite": {"good": 0, "poor": 1},
        "pedal_edema": {"no": 0, "yes": 1},
        "anemia": {"no": 0, "yes": 1},
    }
    for column, mapping in mappings.items():
        features[column] = features[column].astype(str).str.strip().str.lower().map(mapping)
    features = features.apply(lambda column: np.asarray(column, dtype=np.float32))
    target = dataset.data.targets.iloc[:, 0].astype(str).str.strip().str.lower().eq("ckd").astype(np.int64).to_numpy()
    return (
        "kidney",
        features[feature_order].to_numpy(dtype=np.float32),
        target,
        feature_order,
        {
            "name": "UCI Chronic Kidney Disease",
            "doi": "10.24432/C5G020",
            "license": "CC BY 4.0",
            "instances": int(len(features)),
        },
        [
            "The dataset contains only 400 historical hospital records and has substantial missing data in several fields.",
            "Many inputs are laboratory or microscopy findings that require professional collection and interpretation.",
            "The source population and collection setting may not represent current community screening populations.",
            "Performance has not been established prospectively or in an external clinical cohort.",
        ],
    )


def train_one(spec, output_dir: Path):
    slug, X, y, feature_order, dataset, limitations = spec
    X_train, X_holdout, y_train, y_holdout = train_test_split(X, y, test_size=0.4, stratify=y, random_state=44)
    X_validation, X_test, y_validation, y_test = train_test_split(
        X_holdout, y_holdout, test_size=0.5, stratify=y_holdout, random_state=44
    )
    candidates = {
        "regularized_logistic_regression": Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=44)),
            ]
        ),
        "rbf_support_vector_machine": Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                (
                    "classifier",
                    SVC(
                        kernel="rbf",
                        class_weight="balanced",
                        probability=True,
                        random_state=44,
                    ),
                ),
            ]
        ),
    }
    validation_results = {}
    ranked = []
    for candidate_name, candidate in candidates.items():
        candidate.fit(X_train, y_train)
        candidate_scores = candidate.predict_proba(X_validation)[:, 1]
        candidate_threshold = choose_threshold(y_validation, candidate_scores)
        candidate_metrics = metrics(y_validation, candidate_scores, candidate_threshold)
        validation_results[candidate_name] = {
            "threshold": round(candidate_threshold, 4),
            "metrics": candidate_metrics,
        }
        ranked.append(
            (
                candidate_metrics["auroc"],
                candidate_metrics["auprc"],
                -candidate_metrics["brier"],
                candidate_name,
            )
        )
    selected_name = max(ranked)[3]
    pipeline = candidates[selected_name]
    threshold = validation_results[selected_name]["threshold"]
    test_scores = pipeline.predict_proba(X_test)[:, 1]
    measured = metrics(y_test, test_scores, threshold)
    validation_status = "research"

    output_dir.mkdir(parents=True, exist_ok=True)
    converted = convert_sklearn(
        pipeline,
        initial_types=[("features", FloatTensorType([None, len(feature_order)]))],
        target_opset=17,
        options={id(pipeline.named_steps["classifier"]): {"zipmap": False}},
    )
    (output_dir / f"{slug}.onnx").write_bytes(converted.SerializeToString())
    metadata = {
        "slug": slug,
        "version": f"{slug}-uci-candidate-selected-v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "validation_status": validation_status,
        "feature_order": feature_order,
        "threshold": round(threshold, 4),
        "metrics": measured,
        "model_selection": {
            "selected": selected_name,
            "selection_set": "validation-only",
            "candidates": validation_results,
        },
        "dataset": dataset,
        "limitations": limitations,
        "split": {
            "train": int(len(X_train)),
            "validation": int(len(X_validation)),
            "test": int(len(X_test)),
            "random_state": 44,
        },
    }
    (output_dir / f"{slug}.metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--model",
        choices=["all", "heart", "diabetes", "kidney", "liver"],
        default="all",
    )
    args = parser.parse_args()
    specs = {
        "heart": prepare_heart,
        "diabetes": prepare_diabetes,
        "kidney": prepare_kidney,
        "liver": prepare_liver,
    }
    selected = specs if args.model == "all" else {args.model: specs[args.model]}
    for prepare in selected.values():
        train_one(prepare(), args.output_dir)


if __name__ == "__main__":
    main()
