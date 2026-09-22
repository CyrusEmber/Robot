# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""The locomotion criterion's identity, and the derivation half of it.

Locomotion has no separate judge module: ``eval.py`` calls ``metrics`` and turns the protocol's
declared degrees, ratios and seconds into the numbers those kernels are handed. That arithmetic is
part of the criterion -- a ``sustain_steps`` off by one, or a clearance measured from the wrong
height, is invisible in a rollout that passes -- so it lives here, testable without a simulator,
and it is half of the ``judge.id`` every record carries.

The other half is :data:`metrics.METRICS_ID`, the formulas themselves. ``judge.id`` is the two
joined because that is the unit a table compares: a change in either half means two rows were not
scored by the same rule, and the field a comparison reads has to be the one that moves.
"""

from __future__ import annotations

import math

try:  # importable as a package (tests, record readers) or from inside the harness directory (eval.py)
    from ablation_harness.metrics import METRIC_KERNELS, METRICS_ID
except ImportError:  # pragma: no cover - the script-relative path
    from metrics import METRIC_KERNELS, METRICS_ID

#: The identity of the derivation these functions perform. Bump it when the arithmetic changes.
DERIVATION_ID = "loco-derivation-1"

#: The quantities :data:`DERIVATION_ID` covers, so the id names a set rather than a promise.
DERIVED_QUANTITIES = ("tilt_cos_min", "clearance_min", "sustain_steps")

#: The identity a record carries: formulas + arithmetic.
JUDGE_ID = f"{METRICS_ID}+{DERIVATION_ID}"


def semantics_surface() -> dict:
    """What this id can reach, for the frozen case table to pin by digest.

    Two entries, both tuples of names: adding a kernel or a derived quantity changes the surface,
    and a published id keeps its surface, so that needs a new id rather than an edit.
    """
    return {"derivation": list(DERIVED_QUANTITIES), "kernels": list(METRIC_KERNELS)}


def derived_thresholds(protocol: dict, *, stand_height_m: float, step_dt: float) -> dict:
    """The protocol's fall declaration as the numbers :func:`metrics.fall_flags` is handed.

    Args:
        protocol: the eval protocol, read at ``metrics.fall``.
        stand_height_m: the robot's initial base height [m], i.e. the episode's standing reference.
        step_dt: policy step duration [s].

    Returns:
        ``tilt_cos_min`` (cos of the declared angle: ``fall_flags`` compares ``tilt_cos <`` it),
        ``clearance_min`` [m] (a fraction of the *stand* height, not of the terrain), and
        ``sustain_steps`` (the dwell in sampled frames, rounded to the nearest step and never zero
        -- a dwell that rounds to zero steps would declare every frame a fall).
    """
    fall = protocol["metrics"]["fall"]
    return {
        "tilt_cos_min": math.cos(math.radians(float(fall["tilt_deg"]))),
        "clearance_min": float(fall["base_height_ratio"]) * float(stand_height_m),
        "sustain_steps": max(1, int(round(float(fall["sustain_s"]) / float(step_dt)))),
    }


def judge_reference() -> dict:
    """The record's ``judge`` block: which rule scored this run, in both halves."""
    return {
        "id": JUDGE_ID,
        "primitives": METRICS_ID,
        "derivation": DERIVATION_ID,
        "kernels": list(METRIC_KERNELS),
    }
