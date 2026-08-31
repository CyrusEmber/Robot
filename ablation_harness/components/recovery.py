# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Recovery push: impulse disturbance + time-to-recover measurement.

Protocol (Locomotion-Eval-v1): at a fixed time every env receives a horizontal
velocity kick of fixed magnitude in a per-env fixed direction (drawn from the
eval seed). We record the velocity-error spike and the time until the tracking
error stays below the threshold -- recovery speed separates "survives but
slides away" from "snaps back into the gait".
"""

from __future__ import annotations

import torch


def make_kick_directions(num_envs: int, seed: int, device: str) -> torch.Tensor:
    """Per-env fixed horizontal kick directions (unit vectors, world frame)."""
    gen = torch.Generator(device="cpu").manual_seed(seed)
    theta = torch.rand(num_envs, generator=gen) * 2.0 * torch.pi
    dirs = torch.stack([torch.cos(theta), torch.sin(theta)], dim=-1)
    return dirs.to(device)


def apply_kick(robot, kick_mps: float, directions: torch.Tensor) -> None:
    """Add a horizontal world-frame velocity kick to every env's base."""
    lin_w = robot.data.root_lin_vel_w.torch
    ang_w = robot.data.root_ang_vel_w.torch
    new_lin = lin_w.clone()
    new_lin[:, :2] += kick_mps * directions
    root_velocity = torch.cat([new_lin, ang_w], dim=-1)
    robot.write_root_velocity_to_sim(root_velocity)


def recovery_times(
    lin_error: torch.Tensor,
    push_step: int,
    threshold_mps: float,
    sustain_steps: int,
    step_dt: float,
    valid_mask: torch.Tensor,
) -> dict:
    """Time-to-recover per env after the push.

    Args:
        lin_error: (T, N) velocity tracking error [m/s], full episode series.
        push_step: Step index of the kick.
        threshold_mps: Error below this counts as recovered.
        sustain_steps: Must stay below threshold this many consecutive steps.
        step_dt: Policy step duration [s].
        valid_mask: (T, N) False after an env's episode ended (auto-reset).

    Returns:
        Dict with mean/median/p90 recovery time [s], never-recovered fraction,
        spike amplitude [m/s] and per-env times (None -> NaN in list).
    """
    num_steps, num_envs = lin_error.shape
    times = torch.full((num_envs,), float("nan"))
    spikes = torch.zeros(num_envs)
    below = (lin_error < threshold_mps) & valid_mask

    post = below[push_step:]
    if post.shape[0] > 0:
        spikes = lin_error[push_step:].max(dim=0).values
    if post.shape[0] >= sustain_steps:
        # first index (after the push) whose sustain_steps window is all True,
        # vectorized with the same unfold as metrics.sustained_any
        windows = post.unfold(0, sustain_steps, 1).all(dim=-1)  # (T-s+1, N)
        recovered = windows.any(dim=0)
        first_hit = windows.long().argmax(dim=0)  # first True where recovered
        times = torch.where(recovered, first_hit.float() * step_dt, times)

    recovered = ~torch.isnan(times)
    if bool(recovered.any()):
        t = times[recovered]
        mean_t = t.mean().item()
        median_t = t.median().item()
        p90_t = torch.quantile(t, 0.9).item()
    else:
        mean_t = median_t = p90_t = float("nan")
    return {
        "recovery_time_mean_s": mean_t,
        "recovery_time_median_s": median_t,
        "recovery_time_p90_s": p90_t,
        "never_recovered_frac": 1.0 - recovered.float().mean().item(),
        "spike_mean_mps": spikes.mean().item(),
    }
