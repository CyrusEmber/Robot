# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Eval mode transforms for the environment config.

Nominal answers "how strong is the policy in theory": every randomization and
noise source off. Robust answers "how good is it under the fixed training DR
distribution": events stay on, the eval seed pins the realizations so every
run sees the identical draws.
"""

from __future__ import annotations


# event names that constitute domain randomization / disturbance (mode="startup"
# physics randomization + interval disturbances). Tasks without a name are
# skipped, so this works for any env cfg built on the velocity task family.
# KEEP IN SYNC with rl_exp/tasks/play_utils.py -- every PLAY cfg disables
# the same list; adding a DR event without updating both silently breaks
# deterministic evaluation.
_DR_EVENT_NAMES = [
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


def apply_eval_mode(env_cfg, mode: str) -> None:
    """Mutate ``env_cfg`` in place for the requested eval mode.

    Args:
        env_cfg: A ManagerBasedRLEnvCfg instance (already suite-swapped).
        mode: "nominal" (all DR off, no sensor noise) or "robust" (DR on).
    """
    if mode == "nominal":
        for name in _DR_EVENT_NAMES:
            if getattr(env_cfg.events, name, None) is not None:
                setattr(env_cfg.events, name, None)
    elif mode == "robust":
        # keep the task's own DR cfg (fixed distribution) and noise; the eval
        # seed pinned by the caller makes the realizations identical across runs
        pass
    else:
        raise ValueError(f"Unknown eval mode: {mode!r} (expected 'nominal' or 'robust')")

    # corruption on every present obs group (v1/v2: single "policy" group;
    # v3: proprio/extero/priv -- the retired policy group is None), same
    # iteration discipline as play_utils.apply_play_wiring
    corruption = mode == "robust"
    for group in vars(env_cfg.observations).values():
        if group is not None:
            group.enable_corruption = corruption

    # deterministic command injection: the player overwrites the command every
    # step, so disable every autonomous mutation of the velocity command term
    cmd_cfg = env_cfg.commands.base_velocity
    cmd_cfg.heading_command = False
    cmd_cfg.rel_standing_envs = 0.0
    cmd_cfg.rel_heading_envs = 0.0
    cmd_cfg.resampling_time_range = (1.0e9, 1.0e9)
    cmd_cfg.debug_vis = False
