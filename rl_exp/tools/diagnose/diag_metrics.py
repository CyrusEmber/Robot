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

import pathlib

import torch
from isaaclab.utils.math import quat_apply, quat_apply_inverse, yaw_quat

# Bodies whose collision mesh must stay above the floor: chest, neck and the three tail links.
# The baseline line's own pre-train standard says the belly, head chain and tail carry no load
# ("不趴地、不拿尾巴当第五支撑"), so the meshes are what a load reading is checked against --
# a body can be loaded while standing, or loaded because it is grinding through the ground.
MESH_CHECK_BODIES = ["chest_pitch", "neck_pitch", "tail1_pitch", "tail2_pitch", "tail3_pitch"]


def collision_mesh_dir() -> pathlib.Path:
    """Directory of the collision meshes the bbox reader consumes (``rl_exp/meshes/collision``)."""
    return pathlib.Path(__file__).resolve().parents[2] / "meshes" / "collision"


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


def tilt_cos(projected_gravity_b: torch.Tensor) -> torch.Tensor:
    """Cosine of the base tilt angle, shape (N,).

    The same quantity ``metrics.fall_flags`` gates on (``tilt_cos < tilt_cos_min``
    means tilted over), so measuring it anywhere else is a second opinion: the
    projected gravity is a unit vector, giving ``acos(-g_z)`` without an euler detour.

    Args:
        projected_gravity_b: gravity in the base frame, shape (N, 3).
    Returns:
        Shape (N,), 1.0 = perfectly upright.
    """
    return (-projected_gravity_b[:, 2]).clamp(-1.0, 1.0)


def foot_ids(body_names: list[str]) -> list[int]:
    """Indices of the foot bodies in a sensor's body order.

    Args:
        body_names: sensor body names, in sensor order.
    Returns:
        Indices whose name ends with ``_foot``.
    """
    return [i for i, name in enumerate(body_names) if name.endswith("_foot")]


def body_load_n(net_forces_w: torch.Tensor) -> torch.Tensor:
    """Mean normal contact force per body [N], shape (num_bodies,).

    ``net_forces_w`` only answers "this body takes force", not "what it touches"
    -- pair it with :func:`mesh_min_z` before calling a load "standing".

    Args:
        net_forces_w: ``(..., num_bodies, 3)`` contact sensor history -- a live
            frame ``(num_envs, num_bodies, 3)`` or a stacked ``(T, num_envs, ...)``
            session both work: every leading dimension is averaged over.
    Returns:
        Per-body mean of the vertical component [N].
    """
    vertical = net_forces_w[..., 2]
    return vertical.reshape(-1, vertical.shape[-1]).mean(dim=0)


def load_fraction(load_n: torch.Tensor, weight_n: float) -> torch.Tensor:
    """Per-body load as a fraction of body weight, shape (num_bodies,).

    Args:
        load_n: per-body mean normal force [N], shape (num_bodies,).
        weight_n: body weight ``mass * g`` [N].
    """
    return load_n / weight_n


def mesh_bbox_corners(obj_path) -> torch.Tensor:
    """Bounding-box corners of a collision mesh in its link frame, shape (8, 3) [m].

    Args:
        obj_path: path to the ``<body>_collision.obj`` mesh.
    """
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    with open(obj_path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                for i, x in enumerate(line.split()[1:4]):
                    value = float(x)
                    lo[i] = min(lo[i], value)
                    hi[i] = max(hi[i], value)
    return torch.tensor(
        [[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])],
        dtype=torch.float32,
    )


def mesh_min_z(body_pos_w: torch.Tensor, body_quat_w: torch.Tensor,
               ids: list[int], corners: torch.Tensor) -> torch.Tensor:
    """Lowest world z of the selected bodies' collision meshes, shape (N,) [m].

    Contact force says a body is loaded; it does not say what it is loaded
    against. The body origin is not enough either (a mesh can sit above its own
    origin), so the bbox corners are rotated by the live pose and the minimum
    world z is read: ground is z=0, so a negative value is mesh through the floor.

    Args:
        body_pos_w: (N, num_bodies, 3) world positions.
        body_quat_w: (N, num_bodies, 4) world orientations, xyzw.
        ids: body column indices to measure.
        corners: (len(ids), K, 3) link-frame bbox corners.
    """
    k = corners.shape[1]
    n, nb = body_pos_w.shape[0], len(ids)
    pos = body_pos_w[:, ids][:, :, None, :].expand(n, nb, k, 3).reshape(-1, 3)
    quat = body_quat_w[:, ids][:, :, None, :].expand(n, nb, k, 4).reshape(-1, 4)
    pts = corners[None].expand(n, nb, k, 3).reshape(-1, 3)
    world = pos + quat_apply(quat, pts)
    return world.reshape(n, nb, k, 3)[..., 2].min(dim=-1).values

