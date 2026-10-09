"""Versioned input and target schema shared by generation, training, and inference."""
from __future__ import annotations

import math
from collections.abc import Mapping


SCHEMA_VERSION = "cad-geometry-13-v1"

FEATURE_COLUMNS = [
    "length_mm", "width_mm", "height_mm", "volume_mm3", "surface_area_mm2",
    "solid_count", "face_count", "edge_count", "vertex_count", "length_width_ratio",
    "length_height_ratio", "width_height_ratio", "surface_area_volume_ratio",
]

FEATURE_UNITS = {
    "length_mm": "mm", "width_mm": "mm", "height_mm": "mm",
    "volume_mm3": "mm^3", "surface_area_mm2": "mm^2",
    "solid_count": "count", "face_count": "count", "edge_count": "count", "vertex_count": "count",
    "length_width_ratio": "dimensionless", "length_height_ratio": "dimensionless",
    "width_height_ratio": "dimensionless", "surface_area_volume_ratio": "1/mm",
}

FEATURE_DEFINITIONS = {
    "length_mm": "Imported CAD axis-aligned bounding-box X extent, converted to mm.",
    "width_mm": "Imported CAD axis-aligned bounding-box Y extent, converted to mm.",
    "height_mm": "Imported CAD axis-aligned bounding-box Z extent, converted to mm.",
    "volume_mm3": "Absolute volume of the imported solid assembly in cubic millimetres.",
    "surface_area_mm2": "Surface area of the imported solid assembly in square millimetres.",
    "solid_count": "Number of solids in the imported STEP shape.",
    "face_count": "Number of faces in the imported STEP shape.",
    "edge_count": "Number of edges in the imported STEP shape.",
    "vertex_count": "Number of vertices in the imported STEP shape.",
    "length_width_ratio": "Axis-aligned X extent divided by Y extent.",
    "length_height_ratio": "Axis-aligned X extent divided by Z extent.",
    "width_height_ratio": "Axis-aligned Y extent divided by Z extent.",
    "surface_area_volume_ratio": "Assembly surface area divided by assembly volume, in inverse millimetres.",
}

TARGETS = {
    "melt_temperature_C": ("Melt temperature", "°C", "Metal temperature entering the shot system."),
    "die_temperature_C": ("Die temperature", "°C", "Die thermal condition represented by the training labels."),
    "filling_time_s": ("Filling time", "s", "Recorded cavity filling duration."),
    "intensification_pressure_MPa": ("Intensification pressure", "MPa", "Pressure during the intensification phase."),
    "fast_shot_speed_m_s": ("Fast-shot speed", "m/s", "Plunger speed during the fast-shot phase."),
    "vacuum_pressure_mbar_abs": ("Vacuum pressure", "mbar abs", "Absolute pressure; not gauge vacuum."),
    "cooling_time_s": ("Cooling time", "s", "Cooling duration represented by the training labels."),
    "gate_velocity_m_s": ("Gate velocity", "m/s", "Metal velocity at the gate, dependent on die design."),
}
TARGET_COLUMNS = list(TARGETS)

SYNTHETIC_WARNING = (
    "Prototype model trained on synthetic data. These estimates demonstrate the software pipeline "
    "and are not validated for real production."
)

COUNT_FEATURES = ("solid_count", "face_count", "edge_count", "vertex_count")


def validate_feature_mapping(features: Mapping) -> dict[str, float]:
    """Return an ordered finite model row or raise a useful schema error."""
    if not isinstance(features, Mapping):
        raise ValueError("CAD features must be provided as a name-to-number mapping.")
    missing = [name for name in FEATURE_COLUMNS if name not in features]
    if missing:
        raise ValueError("CAD feature schema is incomplete; missing: " + ", ".join(missing))
    values = {}
    for name in FEATURE_COLUMNS:
        try:
            value = float(features[name])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"CAD feature {name} must be numeric.") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"CAD feature {name} must be finite and greater than zero.")
        if name in COUNT_FEATURES and not value.is_integer():
            raise ValueError(f"CAD feature {name} must be a whole-number count.")
        values[name] = value
    return values
