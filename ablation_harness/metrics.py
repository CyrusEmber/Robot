# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Metric library for the locomotion eval harness.

All functions are pure tensor math on per-step series of shape (T, num_envs, ...)
so they are reusable across protocols and robots. Metric definitions are part
of the frozen protocol -- changing a formula means a protocol version bump.
"""

from __future__ import annotations

import torch


def tracking_errors(lin_vel_b: torch.Tensor, ang_vel_b: torch.Tensor, cmd: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Velocity tracking errors against the command.

    Args:
        lin_vel_b: (T, N, 3) base linear velocity in the base frame.
        ang_vel_b: (T, N, 3) base angular velocity in the base frame.
        cmd: (T, N, 3) commanded [vx, vy, wz].

    Returns:
        Lin error (T, N) [m/s] and ang error (T, N) [rad/s].
    """
    lin_err = torch.linalg.norm(lin_vel_b[..., :2] - cmd[..., :2], dim=-1)
    ang_err = torch.abs(ang_vel_b[..., 2] - cmd[..., 2])
    return lin_err, ang_err


def success_mask(lin_err: torch.Tensor, ang_err: torch.Tensor, lin_thr: float, ang_thr: float) -> torch.Tensor:
    """Per-step command success (thresholds frozen in the protocol)."""
    return (lin_err < lin_thr) & (ang_err < ang_thr)


def step_energy(
    stiffness: torch.Tensor,
    damping: torch.Tensor,
    joint_pos_target: torch.Tensor,
    joint_pos: torch.Tensor,
    joint_vel: torch.Tensor,
) -> torch.Tensor:
    """Mechanical joint energy of one step: sum |tau * qdot| [J].

    Implicit PD drives are solved inside PhysX with no torque readback path we
    can rely on, so the torque is reconstructed exactly:
    ``tau = K (q* - q) - D qdot`` using the LIVE per-joint K/D (post
    actuator-gain randomization) and the position target written by the action
    manager.

    Args:
        stiffness: (N, num_joints) live joint stiffness.
        damping: (N, num_joints) live joint damping.
        joint_pos_target: (N, num_joints) position targets this step.
        joint_pos: (N, num_joints) measured joint positions.
        joint_vel: (N, num_joints) measured joint velocities.

    Returns:
        Per-env energy of the step [J], shape (N,).
    """
    torque = stiffness * (joint_pos_target - joint_pos) - damping * joint_vel
    return (torque * joint_vel).abs().sum(dim=-1)


def fall_flags(
    tilt_cos: torch.Tensor,
    clearance: torch.Tensor | None,
    tilt_cos_min: float,
    clearance_min: float | None,
    sustain_steps: int,
    valid_mask: torch.Tensor,
) -> torch.Tensor:
    """Geometric fall detection, decoupled from the env termination terms.

    The escape-hatch lesson: terminations only check selected bodies, a prone
    robot can dodge them. Fall is defined geometrically: tilt beyond the
    threshold OR base clearance below the threshold, sustained (filters bumps).

    Args:
        tilt_cos: (T, N) cos of the tilt angle = -projected_gravity_b[:, 2].
        clearance: (T, N) base height above the terrain [m], None if no scanner.
        tilt_cos_min: cos(fall tilt angle); tilt_cos below it = tilted over.
        clearance_min: Base height below this = collapsed.
        sustain_steps: Condition must hold this many consecutive steps.
        valid_mask: (T, N) False after an env's episode ended.

    Returns:
        (N,) bool fall flags.
    """
    bad = tilt_cos < tilt_cos_min
    if clearance is not None and clearance_min is not None:
        bad = bad | (clearance < clearance_min)
    bad = bad & valid_mask
    return sustained_any(bad, sustain_steps)


def sustained_any(mask: torch.Tensor, sustain_steps: int) -> torch.Tensor:
    """(T, N) bool -> (N,) bool: any run of ``sustain_steps`` consecutive True."""
    num_steps, num_envs = mask.shape
    if num_steps < sustain_steps:
        return torch.zeros(num_envs, dtype=torch.bool, device=mask.device)
    windows = mask.unfold(0, sustain_steps, 1)  # (T-s+1, N, s)
    return windows.all(dim=-1).any(dim=0)


def completion_ratio(
    start_pos_w: torch.Tensor,
    end_pos_w: torch.Tensor,
    cmd: torch.Tensor,
    valid_mask: torch.Tensor,
    step_dt: float,
) -> torch.Tensor:
    """Terrain completion: travelled distance / commanded distance, clipped.

    Direction-insensitive on purpose (pyramid terrains are radial). Turning
    segments add no commanded distance, so in-place rotation is neutral.

    Args:
        start_pos_w: (N, 3) root position at episode start.
        end_pos_w: (N, 3) root position at episode end (or first done).
        cmd: (T, N, 3) commanded velocities.
        valid_mask: (T, N) False after an env's episode ended.
        step_dt: Policy step duration [s].
    """
    travelled = torch.linalg.norm(end_pos_w[:, :2] - start_pos_w[:, :2], dim=-1)
    cmd_speed = torch.linalg.norm(cmd[..., :2], dim=-1)
    commanded = (cmd_speed * valid_mask.float()).sum(dim=0) * step_dt
    return (travelled / commanded.clamp(min=1.0e-6)).clamp(0.0, 1.0)


def stop_overshoot(lin_vel_b: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
    """Residual speed in the final (stop) segment: mean |v_xy| while standing.

    Args:
        lin_vel_b: (T, N, 3) base linear velocity, only the stop-segment slice.
        valid_mask: Matching (T, N) validity slice.
    """
    speed = torch.linalg.norm(lin_vel_b[..., :2], dim=-1) * valid_mask.float()
    denom = valid_mask.float().sum(dim=0).clamp(min=1.0)
    return speed.sum(dim=0) / denom


def summarize_segment(values: torch.Tensor, mask: torch.Tensor) -> float:
    """Mean of ``values`` over valid steps, NaN-safe (all-invalid -> NaN)."""
    total = (values * mask.float()).sum()
    count = mask.float().sum().clamp(min=1.0)
    value = (total / count).item()
    return value if value == value else float("nan")
