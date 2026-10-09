"""Extract basic, auditable geometry measurements from STEP/STP with CadQuery."""
from __future__ import annotations

from pathlib import Path
import math
import logging
import re

import cadquery as cq
from feature_schema import FEATURE_COLUMNS
from thickness_analyzer import analyze_wall_thickness

FEATURE_NAMES = list(FEATURE_COLUMNS)
logger = logging.getLogger(__name__)


def _has_explicit_length_unit(text: str) -> bool:
    """Recognize STEP length units within the same complex entity declaration.

    STEP permits whitespace/newlines and a complex entity can contain several
    unit types. Keeping the check local to the ``LENGTH_UNIT`` declaration
    avoids both rejecting harmless formatting variants and accidentally
    associating a nearby angle/time unit with a length unit.
    """
    # Remove STEP comments first; otherwise a commented-out unit could make an
    # otherwise unit-less file appear safe to convert.
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    known_conversion_units = {
        "INCH", "INCHES", "FOOT", "FEET", "YARD", "YARDS", "MILE",
        "MILES", "MIL", "THOU", "MICRON", "MICROMETER", "MICROMETRE",
        "MILLIMETER", "MILLIMETRE", "CENTIMETER", "CENTIMETRE", "METER",
        "METRE", "DECIMETER", "DECIMETRE",
    }
    for match in re.finditer(r"LENGTH_UNIT\s*\(\s*\)", text, re.I):
        # A complex STEP entity ends at its first semicolon. The preceding
        # entity identifier is included so this remains bounded and auditable.
        start = text.rfind("#", 0, match.start())
        end = text.find(";", match.end())
        declaration = text[start if start >= 0 else match.start():end if end >= 0 else len(text)]
        if re.search(r"\bSI_UNIT\s*\(\s*(?:\$|\.[A-Z]+\.)\s*,\s*\.METRE\.\s*\)", declaration, re.I):
            return True
        conversion = re.search(r"\bCONVERSION_BASED_UNIT\s*\(\s*'([^']+)'", declaration, re.I)
        if conversion and conversion.group(1).strip().upper() in known_conversion_units:
            return True
    return False


def extract_step_features(file_path, *, include_warnings=False, mesh_path=None):
    path = Path(file_path)
    if path.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("Please upload a .step or .stp file.")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("The STEP file is empty or unavailable.")
    try:
        text = path.read_text(encoding="latin-1", errors="ignore")
        if not _has_explicit_length_unit(text):
            raise ValueError("No recognized STEP length-unit declaration was found. Re-export with explicit units so measurements can be converted to mm safely.")
        # CadQuery importStep defaults to target unit MM and Open CASCADE converts
        # from the declared STEP length unit during import.
        workplane = cq.importers.importStep(str(path), unit="MM")
        shape = workplane.val()
        if shape.isNull():
            raise ValueError("No usable shape was found in this STEP file.")
        solids = shape.Solids()
        if not solids:
            raise ValueError("The imported file contains no solid geometry. Export a STEP model with at least one solid.")
        bbox = shape.BoundingBox()
        length, width, height = (float(bbox.xlen), float(bbox.ylen), float(bbox.zlen))
        volume, area = abs(float(shape.Volume())), float(shape.Area())
        raw = [length, width, height, volume, area]
        if not all(math.isfinite(value) for value in raw):
            raise ValueError("The CAD model produced non-finite measurements. Re-export or repair the source model.")
        if min(length, width, height) <= 0:
            raise ValueError("The STEP model has a zero or invalid bounding-box dimension.")
        if volume <= 0:
            raise ValueError("The imported geometry has no positive enclosed solid volume.")
        values = {
            "length_mm": length, "width_mm": width, "height_mm": height,
            "volume_mm3": volume, "surface_area_mm2": area,
            "solid_count": float(len(solids)), "face_count": float(len(shape.Faces())),
            "edge_count": float(len(shape.Edges())), "vertex_count": float(len(shape.Vertices())),
            "length_width_ratio": length / width, "length_height_ratio": length / height,
            "width_height_ratio": width / height, "surface_area_volume_ratio": area / volume,
        }
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("A derived geometry ratio is not finite.")
        if mesh_path is not None:
            # Local mesh conversion only; the source CAD never leaves this server.
            cq.exporters.export(shape, str(mesh_path), exportType="STL", tolerance=0.15, angularTolerance=0.25, unit="MM")
        warnings = []
        if len(solids) > 1:
            warnings.append(f"The model contains {len(solids)} solids; measurements cover the imported assembly as a whole.")
        warnings.append("The STEP file declared a length unit; CadQuery/Open CASCADE converted imported coordinates to mm. Confirm intended part scale against the source CAD model.")
        thickness = analyze_wall_thickness(shape)
        warnings.append(f"Wall thickness is not automatically measured: {thickness['reason']}")
        warnings.append("Basic geometric extraction does not assess draft, undercuts, defects, filling, or solidification.")
        if mesh_path is not None and not Path(mesh_path).is_file():
            warnings.append("CAD measurements completed, but a browser preview could not be generated.")
        return (values, warnings) if include_warnings else values
    except ValueError:
        logger.exception("STEP validation or geometry extraction failed")
        raise
    except Exception as exc:
        logger.exception("Unexpected STEP import or geometry extraction failure")
        raise ValueError("Could not import STEP geometry. Confirm this is a valid STEP solid with supported units and try exporting it again.") from exc
