# HPDC Smart Process Advisor

A compact FastAPI prototype for the core workflow:

**Upload STEP/STP → extract CAD features → estimate eight HPDC parameters → download a concise PDF report.**

The included model is trained on deterministic synthetic dummy data so the full software path can run. It is **not trained on foundry measurements**, and its estimates must not be used to set production equipment. Every prediction page and report identifies this limitation.

## Windows PowerShell setup

Open PowerShell in the project folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python generate_dummy_data.py
python train_model.py
python -m pytest -q
uvicorn app:app --reload
```

Visit `http://127.0.0.1:8000`. To stop the server, press **Ctrl+C**. If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again.

PDF reports use ReportLab when installed. To enable its styled renderer, run `pip install -r requirements-reporting.txt`. The application has a tested built-in PDF renderer if ReportLab cannot be downloaded; the core app and report downloads still work. In this workspace the configured package index could not provide ReportLab, so local runs used the fallback.

## Generate and train the prototype model

The dataset is committed at `data/dummy_hpdc_trials.csv`, and the already trained artifact is at `models/dummy_hpdc_model.joblib` with metadata beside it. To reproduce them:

```powershell
python generate_dummy_data.py
python train_model.py
```

The generator uses seed `20261009` by default and creates 240 artificial rows across component groups. You can choose a different deterministic seed or output path:

```powershell
python generate_dummy_data.py --rows 240 --seed 20261009 --output data/dummy_hpdc_trials.csv
```

The trainer validates source labels, schema, positive finite values, IDs, and counts, then uses an 80/20 grouped holdout by component ID (`random_state=42`). It fits a multi-output Random Forest and writes:

- `models/dummy_hpdc_model.joblib`
- `models/dummy_hpdc_model_metadata.json`

The metadata records the schema, synthetic source, seed, group split, training/test sizes, and per-target MAE/RMSE. These metrics check that the software pipeline executes; they do not measure real HPDC accuracy. The generator’s deterministic formulas and noise are invented to create learnable test targets and are not a die-casting physics model.

## Use the website

1. Choose a `.step` or `.stp` file up to 25 MB.
2. Optionally enter nominal wall thickness in mm. It is recorded as user-supplied context only; no wall-thickness mapping algorithm is implemented, and the value is not a model input.
3. Select **Analyze component**. CadQuery imports the part, checks STEP units and usable solids, converts declared units to mm, extracts the 13-feature model vector, validates the exact feature schema, and runs the saved model.
4. Review the eight parameter cards and visible synthetic-data warning.
5. Download the concise PDF report from the result page.

The parameter outputs are melt temperature (°C), die temperature (°C), filling time (s), intensification pressure (MPa), fast-shot speed (m/s), vacuum pressure (mbar absolute), cooling time (s), and gate velocity (m/s). `feature_schema.py` defines the versioned feature list (`cad-geometry-13-v1`), target names, units, and inference validation. `model_schema.py` remains as a compatibility import only. The optional wall thickness is intentionally excluded from both training and inference. The app warns when CAD feature values are outside the model's synthetic training coverage.

## CAD and engineering limits

The application checks the STEP/STP extension, upload size, explicit supported unit declaration, solid geometry, finite measurements, and feature schema. Multiple solids are included in the geometry extraction. A dedicated `thickness_analyzer.py` reports wall thickness as not assessed until a reliable algorithm is available. The primary UI and PDF do not display the raw feature vector.

Automated wall-thickness measurement, casting simulation, defect prediction, optimization, model-input what-if analysis, machine limits, and real-data model validation are not implemented. The optional nominal wall-thickness entry is only recorded; it cannot change predictions because thickness is not in the model schema. Die design, alloy, gating, venting, machine, and process context cannot be inferred from the component alone. Have a qualified HPDC engineer validate any real process settings.

## Common issues

- **Model unavailable or incompatible:** run the generator and trainer commands above; confirm both model files exist in `models/`.
- **STEP import rejected:** re-export a valid solid STEP with explicit length units, then retry. The importer does not guess unknown units.
- **ReportLab install unavailable:** core setup does not require it. The built-in PDF generator is used unless `requirements-reporting.txt` installs successfully.
- **PowerShell activation blocked:** use the process-scoped execution policy command above; it does not change the machine-wide policy.
- **Report link expired:** reports are kept in memory for the current app process (up to 32 analyses). Analyze again after restarting the server.

See `PROJECT_AUDIT.md`, `FEATURE_STATUS.md`, and `TEST_REPORT.md` for audit notes, retained scope, and actual test results. The earlier implementation backup is `backups/pre_simplification_20261009.zip`.
