import json
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
import pytest

import app as webapp
from cad_feature_extractor import FEATURE_NAMES, _has_explicit_length_unit, extract_step_features
from engineering_rules import basic_engineering_guidance
from feature_schema import FEATURE_DEFINITIONS, FEATURE_UNITS, SCHEMA_VERSION, validate_feature_mapping
from generate_dummy_data import generate
from model_schema import FEATURE_COLUMNS, SYNTHETIC_WARNING, TARGET_COLUMNS
from thickness_analyzer import analyze_wall_thickness
from train_model import train, validate_data

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "uploads" / "cf1e58ef37034085952301024873e32d.step"
client = TestClient(webapp.app)


def test_homepage_and_minimal_navigation():
    response = client.get("/")
    assert response.status_code == 200
    assert "HPDC Smart Process Advisor" in response.text
    assert 'name="file"' in response.text
    assert "nominal_wall_thickness_mm" in response.text
    assert 'href="/history"' not in response.text


def test_dummy_data_is_reproducible_and_schema_shared():
    first, second = generate(60, seed=17), generate(60, seed=17)
    assert first.equals(second)
    assert list(FEATURE_COLUMNS) == FEATURE_NAMES
    assert list(first.columns) == ["component_id", "trial_id", "data_source", "generation_seed", *FEATURE_COLUMNS, *TARGET_COLUMNS]
    assert set(first.data_source) == {"synthetic_dummy"}
    assert first.generation_seed.nunique() == 1 and first.generation_seed.iloc[0] == 17


def test_trainer_validates_schema_and_missing_data():
    with pytest.raises(ValueError, match="missing required columns"):
        validate_data(generate(60).drop(columns=[TARGET_COLUMNS[-1]]))
    duplicate = generate(60)
    duplicate.loc[1, "trial_id"] = duplicate.loc[0, "trial_id"]
    with pytest.raises(ValueError, match="trial_id must be unique"):
        validate_data(duplicate)
    with pytest.raises(FileNotFoundError, match="Run generate_dummy_data.py first"):
        train(ROOT / "data" / "no_such_training_file.csv")


def test_training_saves_reloadable_schema_versioned_model():
    artifact_dir = ROOT / "tests" / f"_training_artifacts_{uuid.uuid4().hex}"
    artifact_dir.mkdir()
    data_path, model_path, metadata_path = (artifact_dir / "training.csv", artifact_dir / "model.joblib",
                                            artifact_dir / "metadata.json")
    try:
        generate(60, seed=123).to_csv(data_path, index=False)
        train(data_path, model_path, metadata_path)
        model = webapp.joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["schema_version"] == SCHEMA_VERSION
        assert metadata["feature_columns"] == FEATURE_COLUMNS
        assert metadata["feature_units"] == FEATURE_UNITS
        assert metadata["feature_definitions"] == FEATURE_DEFINITIONS
        assert metadata["target_columns"] == TARGET_COLUMNS
        assert model.n_features_in_ == len(FEATURE_COLUMNS)
        assert metadata["dataset_provenance"].startswith("synthetic")
    finally:
        for path in (data_path, model_path, metadata_path):
            path.unlink(missing_ok=True)
        artifact_dir.rmdir()


def test_known_step_fixture_extracts_schema_and_multisolids():
    features, warnings = extract_step_features(FIXTURE, include_warnings=True)
    assert list(features) == FEATURE_COLUMNS
    assert features["solid_count"] == 2
    assert all(value > 0 for value in features.values())
    assert any("converted imported coordinates to mm" in warning for warning in warnings)
    assert any("wall thickness" in warning.lower() for warning in warnings)


def test_stp_extension_fixture_is_imported():
    fixture = ROOT / "uploads" / "2805154ce241474d8795e2173f3b75b6.stp"
    features = extract_step_features(fixture)
    assert list(features) == FEATURE_COLUMNS
    assert features["solid_count"] == 1
    response = client.post("/analyze", files={"file": (fixture.name, fixture.read_bytes(), "application/step")})
    assert response.status_code == 200 and "Fast-shot speed" in response.text


def test_step_unit_detection_accepts_valid_formatting_and_rejects_unrelated_units():
    assert _has_explicit_length_unit("#1=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.));")
    assert _has_explicit_length_unit("#1 = ( LENGTH_UNIT ( ) NAMED_UNIT ( * ) SI_UNIT ( $ , .METRE. ) );")
    assert _has_explicit_length_unit("#1=(LENGTH_UNIT()NAMED_UNIT(*)CONVERSION_BASED_UNIT('INCH',#2));")
    assert not _has_explicit_length_unit("#1=(NAMED_UNIT(*) SI_UNIT($,.METRE.));")
    assert not _has_explicit_length_unit("/* LENGTH_UNIT() SI_UNIT(.MILLI.,.METRE.) */")


def test_versioned_schema_rejects_missing_nonfinite_and_invalid_count_features():
    assert SCHEMA_VERSION == "cad-geometry-13-v1"
    valid = extract_step_features(FIXTURE)
    assert validate_feature_mapping(valid) == valid
    with pytest.raises(ValueError, match="missing"):
        validate_feature_mapping({key: value for key, value in valid.items() if key != FEATURE_COLUMNS[0]})
    nonfinite = dict(valid, length_mm=float("inf"))
    with pytest.raises(ValueError, match="finite"):
        validate_feature_mapping(nonfinite)
    fractional_count = dict(valid, solid_count=1.5)
    with pytest.raises(ValueError, match="whole-number"):
        validate_feature_mapping(fractional_count)


def test_thickness_assessment_and_guidance_do_not_claim_unmeasured_properties():
    assessment = analyze_wall_thickness(object())
    assert assessment["status"] == "not_assessed"
    assert assessment["minimum_mm"] is None and "not configured" in assessment["reason"]
    guidance = basic_engineering_guidance()
    assert any("Wall thickness" in item for item in guidance)
    assert any("qualified HPDC engineer" in item for item in guidance)


def test_active_saved_model_runs_real_inference_for_eight_outputs():
    assert webapp.MODEL_PATH.is_file() and webapp.META_PATH.is_file()
    features = extract_step_features(FIXTURE)
    values, metadata, error = webapp.predict(features)
    assert error is None
    assert metadata["model_kind"] == "synthetic_dummy_regression"
    assert [item["name"] for item in values] == TARGET_COLUMNS
    assert all(float(item["value"]) > 0 and item["unit"] for item in values)


def test_inference_rejects_bad_features_and_warns_outside_training_coverage():
    features = extract_step_features(FIXTURE)
    incomplete = {key: value for key, value in features.items() if key != FEATURE_COLUMNS[0]}
    result, _metadata, error = webapp.predict(incomplete)
    assert result == [] and "feature schema is incomplete" in error
    nonfinite = dict(features, length_mm=float("nan"))
    result, _metadata, error = webapp.predict(nonfinite)
    assert result == [] and "finite" in error

    extrapolated = dict(features, length_mm=1e8)
    result, metadata, error = webapp.predict(extrapolated)
    assert error is None and metadata["input_out_of_training_range"] is True
    assert all(item["value"] for item in result)


def test_valid_upload_renders_eight_predictions_and_prototype_warning():
    scratch_before = set((ROOT / "uploads").glob("hpdc_*"))
    response = client.post("/analyze", files={"file": ("housing.step", FIXTURE.read_bytes(), "application/step")})
    assert set((ROOT / "uploads").glob("hpdc_*")) == scratch_before
    assert response.status_code == 200 and len(response.text) > 1000
    assert SYNTHETIC_WARNING in response.text
    assert "housing.step" in response.text
    for label, _unit, _description in webapp.TARGETS.values():
        assert label in response.text
    assert "volume_mm3" not in response.text and "surface_area_mm2" not in response.text
    assert "Wall thickness is not automatically measured" in response.text


def test_optional_thickness_is_reported_but_not_inference_input():
    response = client.post("/analyze", data={"nominal_wall_thickness_mm": "2.4"},
                           files={"file": ("housing.step", FIXTURE.read_bytes(), "application/step")})
    assert response.status_code == 200
    assert "2.4 mm" in response.text and "not a model input" in response.text
    report_id = response.text.split('/report/', 1)[1].split('.pdf', 1)[0]
    report = client.get(f"/report/{report_id}.pdf")
    assert report.status_code == 200 and b"2.4 mm" in report.content


def test_report_download_is_pdf_and_does_not_expose_geometry_metrics():
    response = client.post("/analyze", files={"file": ("part.step", FIXTURE.read_bytes(), "application/step")})
    report_id = response.text.split('/report/', 1)[1].split('.pdf', 1)[0]
    report = client.get(f"/report/{report_id}.pdf")
    assert report.status_code == 200 and report.content.startswith(b"%PDF-")
    assert b"synthetic data" in report.content.lower()
    assert b"part.step" in report.content
    assert b"volume_mm3" not in report.content and b"face_count" not in report.content


def test_invalid_extension_empty_malformed_and_oversized_uploads(caplog):
    extension = client.post("/analyze", files={"file": ("part.txt", b"hello", "text/plain")})
    empty = client.post("/analyze", files={"file": ("empty.step", b"", "application/step")})
    malformed = client.post("/analyze", files={"file": ("broken.step", b"not CAD", "application/step")})
    assert extension.status_code == 415 and "Only .step and .stp" in extension.text
    assert empty.status_code == 400 and "empty" in empty.text.lower()
    assert malformed.status_code == 422 and "could not be completed" in malformed.text.lower()
    assert "STEP validation or geometry extraction failed" in caplog.text
    monkey = webapp.MAX_UPLOAD_BYTES
    try:
        webapp.MAX_UPLOAD_BYTES = 4
        oversized = client.post("/analyze", files={"file": ("large.step", b"12345", "application/step")})
        assert oversized.status_code == 413
    finally:
        webapp.MAX_UPLOAD_BYTES = monkey


def test_missing_model_and_invalid_schema_never_return_blank(monkeypatch):
    monkeypatch.setattr(webapp, "MODEL_PATH", ROOT / "models" / "missing_model.joblib")
    monkeypatch.setattr(webapp, "META_PATH", ROOT / "models" / "missing_model.json")
    missing = client.post("/analyze", files={"file": ("part.step", FIXTURE.read_bytes(), "application/step")})
    assert missing.status_code == 200 and len(missing.text) > 500
    assert "Parameter estimates unavailable" in missing.text
    assert "no valid prediction was produced" in missing.text.lower()
    missing_report_id = missing.text.split('/report/', 1)[1].split('.pdf', 1)[0]
    missing_report = client.get(f"/report/{missing_report_id}.pdf")
    assert missing_report.status_code == 200 and b"no valid model estimate" in missing_report.content.lower()

    bad_meta = ROOT / "models" / "schema_test.json"
    bad_meta.write_text(json.dumps({"model_kind": "synthetic_dummy_regression", "dataset_provenance": "synthetic dummy",
                                    "synthetic_seed": 1, "validation_method": "grouped split",
                                    "feature_columns": ["wrong"], "target_columns": TARGET_COLUMNS,
                                    "metrics": {key: {"mae": 1, "rmse": 1} for key in TARGET_COLUMNS}}), encoding="utf-8")
    try:
        monkeypatch.setattr(webapp, "MODEL_PATH", ROOT / "models" / "dummy_hpdc_model.joblib")
        monkeypatch.setattr(webapp, "META_PATH", bad_meta)
        model, metadata, error = webapp.load_model()
        assert model is None and metadata is None and "feature schema" in error.lower()
    finally:
        bad_meta.unlink(missing_ok=True)


def test_prediction_failure_is_reported_not_hidden(monkeypatch):
    class BrokenModel:
        def predict(self, frame):
            raise RuntimeError("test inference failure")
    monkeypatch.setattr(webapp, "load_model", lambda: (BrokenModel(), {}, None))
    features = extract_step_features(FIXTURE)
    values, metadata, error = webapp.predict(features)
    assert values == [] and "inference failed" in error


def test_health_route_and_report_expiration_are_useful():
    health = client.get("/health")
    assert health.status_code == 200 and health.json()["model_available"] is True
    expired = client.get("/report/not-a-real-report.pdf")
    assert expired.status_code == 404 and "Analyze the CAD file again" in expired.text
