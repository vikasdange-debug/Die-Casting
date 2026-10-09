# Repository audit and simplification record

**Date:** 2026-10-09  
**Application:** FastAPI, Jinja2, CadQuery/Open CASCADE, scikit-learn

## Starting state

The repository was a FastAPI app with CAD feature extraction, a complex multi-page UI, SQLite analysis history, batch and comparison workflows, local STL rendering, engineering checklists, and a report writer. A prior model was archived as `archived_synthetic_model.joblib`; its metadata marked it `synthetic_demo_only`. Two trial CSVs contained generated `DEMO_PART_*`/`DEMO_TRIAL_*` rows. The earlier app rejected synthetic provenance and therefore had no active prediction model. The previous README, templates, and training script described these old paths and were inconsistent with the requested dummy-model workflow.

The historical blank `/analyze` response came from an earlier prediction branch that fell through without returning a template when the model had `synthetic_demo_only` provenance. The simplified upload route now always returns a result page or rendered error.

Before replacing the app/templates/scripts and removing unused source modules, the prior implementation was backed up to `backups/pre_simplification_20261009.zip`. The previous model and data files were retained and renamed as archives; the new active dummy artifacts are separate files.

## Current architecture

- `app.py`: homepage, single CAD analysis POST, in-memory PDF download route, health JSON, upload-size and form error handling.
- `cad_feature_extractor.py`: STEP/STP import, explicit unit handling/conversion, solid validation, existing 13-feature extraction.
- `feature_schema.py`: canonical versioned feature/target names, units, validation, descriptions, and synthetic warning. `model_schema.py` is retained as a compatibility re-export.
- `generate_dummy_data.py`: deterministic synthetic examples with geometry-linked formulas plus noise; seed `20261009` by default.
- `train_model.py`: validates dummy-only labels and schemas, component-grouped holdout, multi-output Random Forest, metrics and provenance metadata.
- `pdf_reports.py`: styled ReportLab report when available, with a tested dependency-free PDF fallback; no raw geometry feature table.
- `thickness_analyzer.py`: explicit `not_assessed` result until a reliable thickness algorithm is available.
- `engineering_rules.py`: concise guidance limited to missing information and qualified validation.
- Jinja templates and static files provide a single upload page, results page, responsive styling, filename display, optional nominal wall thickness, and processing-state behavior.

Unused routes, templates, and modules for chatbot, persistent history, batch, CAD comparison, model-health dashboards, quality status, and extended engineering checklists were removed from the active app. Exact prior sources are available in the backup ZIP.

## Geometry and wall thickness

The inference vector preserves the previous 13 columns and order: bounding dimensions, volume, surface area, solid/topology counts, three aspect ratios, and surface-area/volume. The fixture import has declared STEP units, converted to mm by CadQuery/Open CASCADE, and multiple solids are counted. Unsupported units or invalid/empty solids are rejected.

No suitable wall-thickness measurement algorithm exists in the current extractor. The form therefore accepts optional nominal wall thickness as user-entered mm, marks it as user-supplied in the UI/report, and explicitly excludes it from inference and training. No wall-thickness distribution or thin-section detection is claimed.

## Dummy data/model provenance

`data/dummy_hpdc_trials.csv` contains 240 generated rows across 120 component IDs, seed 20261009, and the shared feature schema/eight target schema. Targets are synthetic formulas intended to be correlated with selected geometry properties for software testing. They do not encode validated HPDC physics. Training uses 192 rows across grouped components and a 48-row/24-component holdout with fixed split seed 42.

Active model and metadata: `models/dummy_hpdc_model.joblib` and `models/dummy_hpdc_model_metadata.json`. The inference loader verifies model kind, synthetic/dummy provenance, exact ordered feature/target schema, generation seed, validation metadata, metrics, feature count, and fitted feature names. The model is loaded and used to produce eight inference values; no displayed values are hardcoded.

No real production or verified experimental dataset was found. The prototype's metrics are synthetic holdout pipeline diagnostics only and are not presented as accuracy or industrial performance. The old synthetic model/CSVs and legacy validation report remain clearly named, inactive archives. The trainer reads only the new dummy dataset by default and rejects rows not tagged `synthetic_dummy`.

## Remaining boundaries

No automatic wall thickness, casting simulation, defect prediction, optimization, real machine limits, AI assistant, persistent analysis history, or production approval is implemented. PDF links remain available during the current process for the latest 32 analyses and expire on restart. The local PDF is text-only and does not embed a component preview. Synthetic outputs are for demonstrating the application pipeline only.

## Follow-up verification and hardening (2026-10-09)

- Re-inspected the current source, templates, training scripts, datasets, model metadata, and archived artifacts before modifying code. The old active workflow is a synthetic demonstration; no real or verified HPDC trial dataset/model was found. The historic inactive synthetic files remain archived and were not used by inference.
- A new shared schema identifier, `cad-geometry-13-v1`, plus feature columns, units, and definitions are recorded in model metadata and required by the model loader. The prior model/data were preserved under `backups/pre_schema_update_*` and `backups/pre_feature_units_*` before deterministic regeneration/retraining.
- Added strict finite/numeric/count validation for inference feature dictionaries, and an explicit warning when CAD inputs extend beyond the synthetic training ranges.
- Added explicit wall-thickness status and separate guidance functions. No thickness values are calculated or fed into the model; optional nominal thickness remains user-supplied and report-only.
- Tightened STEP unit declaration parsing to keep `LENGTH_UNIT` paired with its own complex-unit statement. Common SI and recognized conversion-based declarations are supported; files with unknown or absent length units are still rejected rather than guessed.
- CAD-kernel exceptions now write stack traces to the server log while returning a plain actionable upload error without importer internals.
- Improved the PDF layout and added a ReportLab path with a local fallback. ReportLab is present in the bundled workspace runtime, but installation into the project virtual environment was unavailable from the configured package index; both rendering paths were verified separately.
- The live local Uvicorn check returned HTTP 200 for `/`, `/health`, valid STEP analysis, and report download. The valid STEP fixture produced all eight outputs through the saved model; invalid-extension behavior is covered by automated tests.
