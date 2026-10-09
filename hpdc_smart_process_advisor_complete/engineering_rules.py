"""Small, transparent engineering guidance for the geometry-only prototype."""
from __future__ import annotations


def basic_engineering_guidance(*, include_thickness: bool = True) -> list[str]:
    """Return evidence-based cautions without asserting unmeasured defects."""
    notes = []
    if include_thickness:
        notes.append("Wall thickness is not automatically measured; assess thin sections and transitions from the design model or a validated thickness tool.")
    notes.extend([
        "Die design, gating, venting, machine and alloy context are not inferred from the part model.",
        "Validate process estimates with a qualified HPDC engineer and suitable trials or casting simulation before production use.",
    ])
    return notes
