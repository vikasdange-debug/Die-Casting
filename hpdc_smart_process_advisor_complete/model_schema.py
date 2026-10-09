"""Compatibility re-exports; new code should import from :mod:`feature_schema`."""
from feature_schema import (
    COUNT_FEATURES,
    FEATURE_COLUMNS,
    FEATURE_DEFINITIONS,
    FEATURE_UNITS,
    SCHEMA_VERSION,
    SYNTHETIC_WARNING,
    TARGETS,
    TARGET_COLUMNS,
    validate_feature_mapping,
)

__all__ = [
    "COUNT_FEATURES", "FEATURE_COLUMNS", "FEATURE_DEFINITIONS", "FEATURE_UNITS", "SCHEMA_VERSION",
    "SYNTHETIC_WARNING", "TARGETS", "TARGET_COLUMNS", "validate_feature_mapping",
]
