# Test and training report

**Date:** 2026-10-09  
**Environment:** Windows PowerShell, project virtual environment, Python 3.14, CadQuery/Open CASCADE, FastAPI TestClient.

## Executed checks

- Python compilation: `python -m py_compile app.py cad_feature_extractor.py feature_schema.py model_schema.py thickness_analyzer.py engineering_rules.py generate_dummy_data.py train_model.py pdf_reports.py` — passed.
- Dummy generation: `python generate_dummy_data.py` — wrote 240 rows with seed `20261009`.
- Model training: `python train_model.py` — passed; wrote the active Random Forest and metadata.
- Automated tests: `.venv\Scripts\python.exe -m pytest -q` — **18 passed**, no failures. Coverage includes both STEP/STP fixture imports, shared schema version, feature validation, model save/reload, out-of-training-range warning, missing model, and error paths.
- Live HTTP smoke check using Uvicorn: final-code homepage 200; `/health` reports the model available; valid STEP POST 200 with all eight named outputs and synthetic disclosure; PDF GET 200 with `application/pdf` and `%PDF-1.4`.
- PDF checks: ReportLab renderer generated a report from actual analysis results using the bundled runtime and both pages were visually inspected. The dependency-free fallback was exercised by the project virtual environment, rendered through Poppler, and visually inspected as a one-page report. The report includes model outputs, provenance/actual synthetic metrics, and concise warnings.
- ReportLab installation in the project virtual environment: `python -m pip install 'reportlab>=4.2,<5'` was attempted but the configured package index returned “No matching distribution found.” The local app therefore uses the fallback unless the optional reporting dependency can be installed.

Automated coverage includes generator repeatability and feature-schema alignment, trainer schema/missing-data/duplicate validation, model persistence and reloading, two-solid STEP extraction and one-solid STP extraction, unit declaration parsing, finite feature validation, explicit wall-thickness unavailability, eight-output saved-model inference, out-of-range warning, upload rendering with no raw geometry metrics, optional user-entered thickness reporting, PDF contents with and without model estimates, extension/empty/malformed/oversized uploads, missing model, schema mismatch, inference exception handling, and health/report expiry.

## Synthetic holdout results

Training used 192 rows from 96 components; held-out evaluation used 48 rows from 24 distinct components (80/20 `GroupShuffleSplit`, grouped by component, seed 42). The generated dataset contains 240 artificial records across 120 components (seed 20261009).

Per-target holdout MAE / RMSE from the executed training run:

- Melt temperature: 1.798 °C / 2.118 °C.
- Die temperature: 3.178 °C / 4.222 °C.
- Filling time: 0.00521 s / 0.00650 s.
- Intensification pressure: 2.117 MPa / 2.675 MPa.
- Fast-shot speed: 0.0735 m/s / 0.0942 m/s.
- Vacuum pressure: 6.328 mbar absolute / 7.693 mbar absolute.
- Cooling time: 0.545 s / 0.815 s.
- Gate velocity: 1.133 m/s / 1.493 m/s.

These numbers measure fit to generated formula-based labels only. They are not real HPDC model accuracy, safety, or production evidence. Reports label them as synthetic holdout errors.

## Warning

Pytest reports one Starlette deprecation warning: the installed TestClient integration currently uses `httpx`, with a future preference for `httpx2`. It does not affect the successful test run. An intermediate `tmp_path` test hit Windows access denial in pytest's default user-profile temporary directory; the test now creates and cleans a unique directory under `tests/`, and the final run passes. The package-index limitation for ReportLab is documented above; PDF downloads remain functional through the fallback.
