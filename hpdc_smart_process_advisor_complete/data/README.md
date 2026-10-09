# Prototype training data

`dummy_hpdc_trials.csv` is the active training input. It is generated locally by `generate_dummy_data.py` with deterministic seed `20261009`. Its component and trial IDs are labeled `DUMMY_*`; the `data_source` column is `synthetic_dummy`. Every target is produced from an invented geometry-linked formula plus seeded noise to make the model pipeline testable. These examples are not production records, verified experiments, simulation results, optimal settings, or a physical HPDC model.

Recreate the data and model from the repository root:

```powershell
python generate_dummy_data.py
python train_model.py
```

The generated data uses the versioned 13-feature schema in `feature_schema.py` (`cad-geometry-13-v1`) and all eight named process targets. Training validates the schema, positive finite values, counts, unique trial IDs, and synthetic source label, then performs an 80/20 grouped split by component. Feature units, definitions, model provenance, and actual holdout metrics are saved in metadata. Metrics are synthetic holdout software checks only.

The two `archived_*synthetic*` CSVs are retained from the earlier repository state for provenance. They are not used by the current generator or trainer. `template_hpdc_trials.csv` is a header-only legacy template and is not used by the dummy training pipeline.
