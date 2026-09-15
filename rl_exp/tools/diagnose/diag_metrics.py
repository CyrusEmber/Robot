# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Acceptance-side velocity metrics for the diagnose tool (pure torch, no sim).

The reward kernel reads the **yaw-aligned gravity frame**
(``teacher_mdp.miki_tracking_kernel`` over ``quat_apply_inverse(yaw_quat(q), v_w)``).
Acceptance gates must read the same frame:

* the body frame (``root_lin_vel_b``) folds pitch/roll into the forward axis, so
  a pitched-but-correctly-moving base reads as underspeed;
* a signed mean sideslip cancels a left/right alternating sideslip to ~0, so a
  robot shaking sideways passes a ``mean(slip)`` gate.

Both mistakes were live in the diagnose P2 gates until this module (v13.2 /
v14.2). Every function here is sim-free so the offline gate can test it.
"""

from __future__ import annotations

import torch
from isaaclab.utils.math import quat_apply_inverse, yaw_quat


def yaw_frame_lin_vel(quat_w: torch.Tensor, lin_vel_w: torch.Tensor) -> torch.Tensor:
    """World linear velocity in the yaw-aligned gravity frame (the reward frame).

    Args:
        quat_w: root orientation, shape (N, 4), xyzw lib convention.
        lin_vel_w: root linear velocity in world frame [m/s], shape (N, 3).
    Returns:
        Shape (N, 2): ``[forward, lateral]`` [m/s] in the reward kernel's frame.
    """
    return quat_apply_inverse(yaw_quat(quat_w), lin_vel_w)[:, :2]


def forward_error(cmd_speed: float, fwd_yaw: torch.Tensor) -> dict:
    """Forward-speed error for a straight command, three views of the same series.

    ``mean_signed_frac`` is the pre-v13.1 gate: a robot that never moved scores
    -1.0, which passed while the limit was written as ``overshoot < 0.15``.
    ``mean_abs_frac`` is the corrected gate. ``mae_mps`` is the per-frame mean
    absolute error -- reported, not gated -- and exposes a fast/slow
    alternation that either mean cancels.

    Args:
        cmd_speed: commanded forward speed [m/s].
        fwd_yaw: per-step forward speed in the yaw frame [m/s], shape (T,).
    Returns:
        Dict with ``mean_fwd_mps``, ``mean_signed_frac``, ``mean_abs_frac``, ``mae_mps``.
    """
    mean_fwd = fwd_yaw.mean().item()
    return {
        "mean_fwd_mps": round(mean_fwd, 3),
        "mean_signed_frac": round(mean_fwd / cmd_speed - 1.0, 3) if cmd_speed > 0 else None,
        "mean_abs_frac": round(abs(mean_fwd / cmd_speed - 1.0), 3) if cmd_speed > 0 else None,
        "mae_mps": round((fwd_yaw - cmd_speed).abs().mean().item(), 3) if fwd_yaw.numel() else 0.0,
    }


def sideslip_abs_mean(vel_yaw_y: torch.Tensor) -> float:
    """Acceptance sideslip: per-frame ``mean|v_lat|`` in the reward frame [m/s].

    Absolute per frame on purpose: ``mean(vel_yaw_y)`` cancels a left/right
    alternating sideslip, so that gate passed robots that were shaking
    sideways. The signed mean stays available as a diagnostic (it tells the
    drift side), never as the gate.

    Args:
        vel_yaw_y: per-step lateral velocity in the yaw frame [m/s], shape (T,).
    Returns:
        Mean absolute lateral speed [m/s].
    """
    return round(vel_yaw_y.abs().mean().item(), 3) if vel_yaw_y.numel() else 0.0
