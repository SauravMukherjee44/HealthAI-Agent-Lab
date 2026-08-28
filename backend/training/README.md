# Reproducible model training

The current research candidates are intentionally compact, CPU-friendly
research baselines trained from CC BY 4.0 UCI datasets. They are not clinically
validated medical devices.

```bash
python -m backend.training.train_models --model all
python -m backend.training.train_pneumonia
```

The command uses fixed stratified train/validation/test splits. It compares a
regularized logistic model with an RBF support-vector model on validation data,
selects the candidate without touching the test set, selects a
sensitivity-oriented threshold on validation data, evaluates once on the test
split, and writes versioned ONNX and metadata artifacts to `backend/artifacts`.

Datasets:

- Statlog (Heart), DOI `10.24432/C57303`, CC BY 4.0.
- Early Stage Diabetes Risk Prediction, DOI `10.24432/C5VG8H`, CC BY 4.0.
- Chronic Kidney Disease, DOI `10.24432/C5G020`, CC BY 4.0.
- ILPD (Indian Liver Patient Dataset), DOI `10.24432/C5D02C`, CC BY 4.0.
- MedMNIST v2 PneumoniaMNIST, DOI `10.5281/zenodo.10519652`, CC BY 4.0.

Kidney and liver tools deliberately require their full laboratory schemas. The
language model may route to these tools, but it may not invent laboratory values
or replace professional collection and interpretation.

The pneumonia pipeline downloads the 4.2 MB official dataset, verifies its
published MD5 digest, uses its fixed train/validation/test split, selects a
regularization candidate only on validation data, and exports a 28×28 ONNX
baseline. It is pediatric-only, loses substantial detail during resizing, and
must never be presented as radiologist-equivalent or suitable for adult X-rays.

Do not change a threshold after inspecting the frozen test results. A new
experiment requires a new split seed/version and a new metadata artifact.
