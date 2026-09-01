# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Shared PLAY-variant wiring for deterministic evaluation.

Every ``*_PLAY`` env cfg must disable the SAME set of DR events AND apply the
same scene/terrain/noise setup. Hand-copied blocks drifted twice (curriculum-
rough PLAY missed ``randomize_limb_mass``; curriculum-flat PLAY missed the
whole block), so the wiring lives here exactly once: PLAY classes call
:func:`apply_play_wiring` as their final ``__post_init__`` step.

This list is duplicated in ``ablation_harness/components/dr_controller.py``
(``_DR_EVENT_NAMES``, eval modes) -- the two must stay in sync. The sync is
machine-enforced: ``rl_exp/tools/verify/check_dr_parity.py`` diffs the
two lists and fails if any ``*_PLAY`` class lacks the wiring call.

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


def apply_play_wiring(env_cfg, num_envs: int = 50, grid: int = 5) -> None:
    """Apply the shared PLAY setup: small scene, fixed terrain grid, no curriculum,
    no observation corruption, every DR event disabled.

    Call as the LAST step of every ``*_PLAY.__post_init__`` (after the recipe
    base has swapped in its terrain generator / obs terms).
    """
    env_cfg.scene.num_envs = num_envs
    env_cfg.scene.env_spacing = 2.5
    env_cfg.scene.terrain.max_init_terrain_level = None
    if env_cfg.scene.terrain.terrain_generator is not None:
        env_cfg.scene.terrain.terrain_generator.num_rows = grid
        env_cfg.scene.terrain.terrain_generator.num_cols = grid
        env_cfg.scene.terrain.terrain_generator.curriculum = False
    # disable corruption on every present obs group (v1/v2: single "policy"
    # group; v3: proprio/extero/priv -- the retired policy group is None)
    for group in vars(env_cfg.observations).values():
        if group is not None:
            group.enable_corruption = False
    disable_dr_events(env_cfg.events)
