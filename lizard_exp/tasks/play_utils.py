# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Shared PLAY-variant wiring for deterministic evaluation.

Every ``*_PLAY`` env cfg must disable the SAME set of DR events. Hand-copied
nine-line lists drifted twice (curriculum-rough PLAY missed
``randomize_limb_mass``; curriculum-flat PLAY missed the whole block), so the
list lives here exactly once and every PLAY calls :func:`disable_dr_events`.

This list is duplicated in ``ablation_harness/components/dr_controller.py``
(``_DR_EVENT_NAMES``, eval modes) -- the two must stay in sync. Adding a DR
event without updating both silently breaks deterministic evaluation.

Deliberately dependency-free (no cfg semantics, no family imports) so the
teacher snapshot module can use it without violating its zero-family-import
discipline.
"""

from __future__ import annotations


DR_EVENT_NAMES = [
    "physics_material",
    "add_base_mass",
    "base_com",
    "randomize_limb_mass",
    "randomize_inertia",
    "randomize_actuator_gains",
    "randomize_joint_params",
    "base_external_force_torque",
    "push_robot",
]


def disable_dr_events(events_cfg) -> None:
    """Null out every DR event on an EventsCfg (missing names are skipped)."""
    for name in DR_EVENT_NAMES:
        if getattr(events_cfg, name, None) is not None:
            setattr(events_cfg, name, None)
