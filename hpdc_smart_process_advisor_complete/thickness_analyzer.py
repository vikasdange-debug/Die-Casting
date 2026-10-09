"""Honest wall-thickness assessment boundary for the current CAD pipeline.

CadQuery's basic solid properties do not provide a defensible local wall
thickness distribution. Until a validated measurement method is integrated,
this module reports the measurement as unavailable instead of inferring it from
surface area or bounding dimensions.
"""
from __future__ import annotations


def analyze_wall_thickness(shape=None) -> dict:
    """Return an explicit unavailable result; no thickness is fabricated."""
    if shape is None:
        reason = "No imported CAD shape was supplied."
    else:
        reason = "A reliable local wall-thickness algorithm is not configured for this application."
    return {
        "status": "not_assessed",
        "method": None,
        "unit": "mm",
        "minimum_mm": None,
        "median_mm": None,
        "maximum_mm": None,
        "reason": reason,
    }
