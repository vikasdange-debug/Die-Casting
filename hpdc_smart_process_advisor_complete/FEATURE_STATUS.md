# Core feature status

## Included

- STEP/STP upload with extension, 25 MB size, import, unit, usable-solid, and finite-feature validation.
- Backend extraction of the preserved 13-feature CAD schema; no raw geometry table is exposed in the result UI or PDF.
- Versioned shared schema (`cad-geometry-13-v1`) used by feature extraction, data generation, training, and inference.
- Optional user-entered nominal wall thickness, labeled as such and excluded from model inputs.
- Explicit wall-thickness assessment status from `thickness_analyzer.py`; no numeric thickness is claimed without an algorithm.
- Deterministic dummy data generator and grouped multi-output Random Forest training pipeline.
- Saved synthetic model loading and actual eight-output inference with model/schema provenance verification.
- Warning when uploaded CAD features are outside the model's synthetic training coverage.
- Eight clear parameter cards with units and short descriptions.
- Persistent synthetic-only warning on each model result and report.
- Small engineering notes describing missing thickness and die/process context.
- Concise styled PDF report via ReportLab when installed; a tested local PDF renderer keeps downloads available offline.
- Basic evidence-based engineering notes and a model-health JSON endpoint.
- Single responsive upload/result interface with processing state and clear errors.

## Not included

- Automated wall thickness calculation, chatbot, persistent analysis history, batch analysis, CAD comparison, quality prediction, optimization, model-health dashboard, simulation, real machine safe ranges, or production validation.
- What-if parameter reruns: the optional manual thickness value is not a model feature, and process targets are outputs, so the current model has no user-adjustable inputs to vary honestly.
- CAD preview was removed to keep the UI and dependencies focused; filename and CAD-derived process results are shown.
