from backend.app.reports import build_pdf, build_xlsx

REPORT = {
    "condition": "heart",
    "band": "lower",
    "probability": 0.21,
    "threshold": 0.42,
    "model_version": "heart-test-v1",
    "validation_status": "research",
    "inputs": {"age": 38, "resting_bp": 120},
    "limitations": ["Small historical dataset.", "Not externally validated."],
    "dataset": {"name": "Test dataset", "license": "CC BY 4.0"},
}


def test_pdf_report_has_pdf_signature():
    payload = build_pdf(REPORT, "Sample User")
    assert payload.startswith(b"%PDF")
    assert len(payload) > 1_000


def test_xlsx_report_has_zip_signature():
    payload = build_xlsx(REPORT, None)
    assert payload.startswith(b"PK")
    assert len(payload) > 1_000
