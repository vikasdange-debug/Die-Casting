"""Small CAD-driven HPDC parameter prototype with explicitly synthetic inference."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import math
import tempfile
import uuid

import joblib
import pandas as pd
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from cad_feature_extractor import extract_step_features
from engineering_rules import basic_engineering_guidance
from feature_schema import (FEATURE_COLUMNS, FEATURE_DEFINITIONS, FEATURE_UNITS, SCHEMA_VERSION,
                            SYNTHETIC_WARNING, TARGETS, TARGET_COLUMNS, validate_feature_mapping)
from pdf_reports import analysis_pdf

ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = ROOT / "uploads"
MODEL_PATH = ROOT / "models" / "dummy_hpdc_model.joblib"
META_PATH = ROOT / "models" / "dummy_hpdc_model_metadata.json"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_REPORTS = 32
logger = logging.getLogger("hpdc_advisor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
reports: OrderedDict[str, dict] = OrderedDict()

app = FastAPI(title="HPDC Smart Process Advisor", version="1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


class UploadLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/analyze":
            try:
                if int(request.headers.get("content-length", "0")) > MAX_UPLOAD_BYTES + 1024 * 1024:
                    return render(request, "index.html", status_code=413,
                                  error="Upload exceeds the 25 MB limit. Choose a smaller STEP/STP file.",
                                  model_message=model_status())
            except ValueError:
                pass
        return await call_next(request)


app.add_middleware(UploadLimitMiddleware)


def render(request: Request, name: str, *, status_code: int = 200, **context):
    return templates.TemplateResponse(request=request, name=name, status_code=status_code, context=context)


def load_model():
    """Load only the trained dummy prototype with exact schemas and disclosed provenance."""
    if not MODEL_PATH.is_file() or not META_PATH.is_file():
        return None, None, "Model is not trained yet. Run generate_dummy_data.py, then train_model.py."
    try:
        metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
        if metadata.get("model_kind") != "synthetic_dummy_regression":
            raise ValueError("Model metadata does not identify the supported synthetic prototype.")
        if metadata.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Model feature schema version does not match the current CAD inference schema.")
        if metadata.get("feature_units") != FEATURE_UNITS or metadata.get("feature_definitions") != FEATURE_DEFINITIONS:
            raise ValueError("Model feature units or definitions do not match the current CAD schema.")
        provenance = str(metadata.get("dataset_provenance", "")).lower()
        if "synthetic" not in provenance and "dummy" not in provenance:
            raise ValueError("Model provenance is missing the synthetic/dummy label.")
        if metadata.get("feature_columns") != FEATURE_COLUMNS:
            raise ValueError("Model feature schema does not match CAD inference schema.")
        if metadata.get("target_columns") != TARGET_COLUMNS:
            raise ValueError("Model target schema does not match all eight parameters.")
        if not isinstance(metadata.get("synthetic_seed"), int) or not metadata.get("validation_method"):
            raise ValueError("Model generation seed or validation method is missing from metadata.")
        metrics = metadata.get("metrics")
        if not isinstance(metrics, dict) or any(
            key not in metrics or any(metric not in metrics[key] or not math.isfinite(float(metrics[key][metric]))
                                      or float(metrics[key][metric]) < 0 for metric in ("mae", "rmse"))
            for key in TARGET_COLUMNS
        ):
            raise ValueError("Per-target synthetic holdout metrics are missing or invalid.")
        model = joblib.load(MODEL_PATH)
        if getattr(model, "n_features_in_", None) != len(FEATURE_COLUMNS):
            raise ValueError("Saved model feature count does not match its metadata.")
        if list(getattr(model, "feature_names_in_", [])) != FEATURE_COLUMNS:
            raise ValueError("Saved model feature names do not match the inference feature order.")
        return model, metadata, None
    except Exception as exc:
        logger.exception("Dummy model validation or loading failed")
        return None, None, f"Model could not be loaded safely: {exc}"


def model_status():
    _model, metadata, issue = load_model()
    if issue:
        return issue
    return f"Synthetic prototype model ready · {metadata.get('model_version', 'version not recorded')}"


def predict(features):
    model, metadata, issue = load_model()
    if model is None:
        return [], None, issue
    try:
        ordered_features = validate_feature_mapping(features)
        row = pd.DataFrame([ordered_features], columns=FEATURE_COLUMNS)
        output = model.predict(row)
        if getattr(output, "shape", None) != (1, len(TARGET_COLUMNS)):
            raise ValueError("Model must return one numeric value for each of the eight targets.")
        feature_ranges = metadata.get("feature_ranges", {})
        outside_training_range = any(
            name in feature_ranges
            and (value < feature_ranges[name]["min"] or value > feature_ranges[name]["max"])
            for name, value in ordered_features.items()
        )
        # Per-request status only; the persisted metadata remains unchanged.
        metadata = dict(metadata)
        metadata["input_out_of_training_range"] = outside_training_range
        predictions = []
        for key, raw in zip(TARGET_COLUMNS, output[0]):
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError(f"Model returned a non-finite result for {key}.")
            label, unit, description = TARGETS[key]
            training_range = metadata.get("target_ranges", {}).get(key)
            range_note = None
            if training_range and not training_range["min"] <= value <= training_range["max"]:
                range_note = "Outside the synthetic training-data range; check the input and model behavior."
            predictions.append({"name": key, "label": label, "value": f"{value:.4g}",
                                "unit": unit, "description": description, "range_warning": range_note})
        return predictions, metadata, None
    except Exception as exc:
        logger.exception("Model inference failed")
        return [], metadata, f"CAD features were extracted, but model inference failed: {exc}"


async def read_upload(upload: UploadFile):
    filename = Path(upload.filename or "").name
    suffix = Path(filename).suffix.lower()
    try:
        if suffix not in {".step", ".stp"}:
            raise ValueError("Only .step and .stp CAD files are supported.")
        content = await upload.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await upload.close()
    if not content:
        raise ValueError("The selected CAD file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise OverflowError("Upload exceeds the 25 MB per-file limit.")
    return filename, suffix, content


def analyze_cad(filename: str, suffix: str, content: bytes, thickness_text: str | None):
    nominal_thickness = None
    if thickness_text and thickness_text.strip():
        try:
            nominal_thickness = float(thickness_text)
        except ValueError as exc:
            raise ValueError("Nominal wall thickness must be a number in millimetres.") from exc
        if not math.isfinite(nominal_thickness) or nominal_thickness <= 0:
            raise ValueError("Nominal wall thickness must be a finite value greater than zero.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="hpdc_", suffix=suffix, dir=UPLOAD_DIR, delete=False) as scratch:
            scratch.write(content)
            temp_path = Path(scratch.name)
        features, extraction_warnings = extract_step_features(temp_path, include_warnings=True)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
    predictions, metadata, prediction_error = predict(features)
    warnings = [SYNTHETIC_WARNING if predictions else "Synthetic prototype model is unavailable; no parameter estimates were generated."]
    warnings.extend(basic_engineering_guidance(include_thickness=False))
    if metadata and metadata.get("input_out_of_training_range"):
        warnings.append("CAD geometry falls outside one or more synthetic training ranges; treat the estimates as extrapolations.")
    warnings.extend(extraction_warnings)
    if prediction_error:
        warnings.append(prediction_error)
    if nominal_thickness is not None:
        warnings.append(f"User-supplied nominal wall thickness: {nominal_thickness:g} mm. It was not measured from CAD and is not a model input.")
    return {"filename": filename, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "predictions": predictions, "metadata": metadata, "warnings": warnings,
            "nominal_thickness_mm": nominal_thickness,
            "status": "Synthetic prototype estimates generated" if predictions else "Parameter estimation unavailable"}


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    logger.info("Invalid request for %s: %s", request.url.path, exc)
    return render(request, "index.html", status_code=422,
                  error="Choose a STEP/STP file and submit the analysis form.", model_message=model_status())


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return render(request, "index.html", model_message=model_status())


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, file: UploadFile = File(...),
                  nominal_wall_thickness_mm: str | None = Form(default=None)):
    try:
        filename, suffix, content = await read_upload(file)
        result = analyze_cad(filename, suffix, content, nominal_wall_thickness_mm)
    except OverflowError as exc:
        return render(request, "index.html", status_code=413, error=str(exc), model_message=model_status())
    except ValueError as exc:
        message = str(exc)
        code = 415 if message.startswith("Only .step") else 400 if "file is empty" in message.lower() else 422
        return render(request, "index.html", status_code=code, error=message, model_message=model_status())
    except Exception as exc:
        logger.exception("CAD analysis failed")
        return render(request, "index.html", status_code=422,
                      error="CAD analysis could not be completed. Confirm the file is a valid STEP solid with supported units, then try again.",
                      model_message=model_status())
    report_id = uuid.uuid4().hex
    result["report_id"] = report_id
    reports[report_id] = result
    reports.move_to_end(report_id)
    while len(reports) > MAX_REPORTS:
        reports.popitem(last=False)
    return render(request, "analysis.html", result=result)


@app.get("/report/{report_id}.pdf")
async def download_report(report_id: str):
    result = reports.get(report_id)
    if result is None:
        return Response("Report not found or the application has restarted. Analyze the CAD file again.",
                        status_code=404, media_type="text/plain")
    payload = analysis_pdf(result)
    filename = "".join(char for char in Path(result["filename"]).stem if char.isalnum() or char in "-_ ")[:60] or "analysis"
    return Response(payload, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}_hpdc_report.pdf"'})


@app.get("/health")
async def health():
    model, metadata, issue = load_model()
    return {"status": "ok", "cad_processing_available": True, "model_available": model is not None,
            "model_kind": metadata.get("model_kind") if metadata else None, "model_issue": issue}
