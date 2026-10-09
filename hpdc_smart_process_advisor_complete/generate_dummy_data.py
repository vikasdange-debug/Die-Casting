"""Generate deterministic, clearly artificial HPDC rows for software-pipeline testing only."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from feature_schema import FEATURE_COLUMNS, TARGET_COLUMNS

ROOT = Path(__file__).resolve().parent
SEED = 20261009


def generate(rows: int = 240, seed: int = SEED) -> pd.DataFrame:
    if rows < 40:
        raise ValueError("Generate at least 40 rows so component-grouped train/test splitting is possible.")
    rng = np.random.default_rng(seed)
    component_count = max(20, rows // 2)
    per_component = int(np.ceil(rows / component_count))
    records = []
    for component in range(component_count):
        length, width, height = rng.uniform(55, 320), rng.uniform(25, 175), rng.uniform(12, 115)
        fill_fraction = rng.uniform(0.18, 0.62)
        volume = length * width * height * fill_fraction
        area = 2 * (length * width + length * height + width * height) * rng.uniform(0.85, 1.35)
        solid_count = int(rng.integers(1, 4))
        face_count = int(rng.integers(24, 240))
        edge_count = int(rng.integers(48, 620))
        vertex_count = int(rng.integers(24, 320))
        geometry = {
            "length_mm": length, "width_mm": width, "height_mm": height,
            "volume_mm3": volume, "surface_area_mm2": area,
            "solid_count": solid_count, "face_count": face_count,
            "edge_count": edge_count, "vertex_count": vertex_count,
            "length_width_ratio": length / width,
            "length_height_ratio": length / height,
            "width_height_ratio": width / height,
            "surface_area_volume_ratio": area / volume,
        }
        scale = length / 200.0
        compactness = volume / (length * width * height)
        shape = geometry["surface_area_volume_ratio"]
        for trial in range(per_component):
            # These deterministic relationships plus small seeded noise are invented solely to
            # exercise a regression workflow. They are not a physical HPDC process model.
            targets = {
                "melt_temperature_C": 680 + 7 * (scale - 1) + rng.normal(0, 2),
                "die_temperature_C": 215 + 14 * (scale - 1) + 10 * (compactness - 0.4) + rng.normal(0, 4),
                "filling_time_s": 0.045 + 0.025 * scale + 0.03 * (1 - compactness) + rng.normal(0, 0.004),
                "intensification_pressure_MPa": 62 + 7 * (compactness - 0.4) + rng.normal(0, 2.5),
                "fast_shot_speed_m_s": 2.4 + 0.25 * (compactness - 0.4) - 0.1 * (scale - 1) + rng.normal(0, 0.08),
                "vacuum_pressure_mbar_abs": 105 + 20 * (1 - compactness) + rng.normal(0, 7),
                "cooling_time_s": 5 + 2.2 * scale + 0.0015 * volume / 1000 + rng.normal(0, 0.25),
                "gate_velocity_m_s": 36 + 6 * (compactness - 0.4) - 4 * (shape - 0.35) + rng.normal(0, 1.5),
            }
            record = {"component_id": f"DUMMY_PART_{component:04d}",
                      "trial_id": f"DUMMY_TRIAL_{component:04d}_{trial:02d}",
                      "data_source": "synthetic_dummy", "generation_seed": int(seed)}
            record.update(geometry)
            record.update({key: max(0.001, value) for key, value in targets.items()})
            records.append(record)
    frame = pd.DataFrame(records).iloc[:rows].copy()
    return frame[["component_id", "trial_id", "data_source", "generation_seed", *FEATURE_COLUMNS, *TARGET_COLUMNS]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=240)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", default=str(ROOT / "data" / "dummy_hpdc_trials.csv"))
    args = parser.parse_args()
    frame = generate(args.rows, args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, float_format="%.8g")
    print(f"Wrote {len(frame)} synthetic-only rows to {output} (seed={args.seed}).")
    print("Generated labels are artificial software fixtures, not foundry measurements or recommendations.")


if __name__ == "__main__":
    main()
