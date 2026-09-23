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


def mesh_vertices(obj_path) -> torch.Tensor:
    """Every vertex of a collision mesh in its link frame, shape (V, 3) [m].

    The collision shape is the mesh's convex hull (``physics:approximation = "convexHull"`` in the
    asset), so its lowest point is one of these vertices: feeding them to :func:`mesh_min_z` gives
    the real ground clearance.

    A bounding-box-corner reading of the same mesh over-states penetration by about ten times
    (measured 2026-09-21 on a dragging neck: -0.052 m from corners, -0.005 m from vertices). In the
    link frame a box corner sits at the lowest vertex's height, but once the body rotates the corner
    is no longer a point of the body at all. That version was deleted rather than kept as an option.

    Args:
        obj_path: path to the ``<body>_collision.obj`` mesh.
    """
    points = []
    with open(obj_path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                points.append([float(x) for x in line.split()[1:4]])
    return torch.tensor(points, dtype=torch.float32)


def pad_point_clouds(clouds: list[torch.Tensor]) -> torch.Tensor:
    """Stack point clouds of different lengths into (B, max_len, 3) by repeating each cloud's first vertex.

    The padding has to survive being rotated by the body's pose, and the obvious fills do not.
    ``+inf`` becomes NaN -- :func:`quat_apply` forms cross products and ``inf - inf`` is NaN, which
    propagates through the min and poisons every body narrower than the widest one (measured
    2026-09-21: the shorter collision meshes read NaN, and a NaN clearance fails a gate by
    accident). Zeros are no safer: a padded zero is a real coordinate that drags the minimum below
    the mesh. A repeated vertex is already a point of the body, so it cannot move its minimum.

    Args:
        clouds: one ``(V_i, 3)`` tensor per body.
    """
    width = max(cloud.shape[0] for cloud in clouds)
    padded = torch.empty((len(clouds), width, 3), dtype=clouds[0].dtype)
    for i, cloud in enumerate(clouds):
        padded[i, : cloud.shape[0]] = cloud
        padded[i, cloud.shape[0]:] = cloud[0]
    return padded


def mesh_lowest_point(body_pos_w: torch.Tensor, body_quat_w: torch.Tensor,
                      ids: list[int], corners: torch.Tensor) -> torch.Tensor:
    """World position of each selected body's lowest collision-mesh vertex, shape (N, B, 3) [m].

    The same rotation :func:`mesh_min_z` reads, kept as a point because a clearance alone does not
    locate a contact: the deepest vertex is the geometric candidate for where the body touches, so
    it is also what a contact-point velocity has to be taken at.

    Args:
        body_pos_w: (N, num_bodies, 3) world positions.
        body_quat_w: (N, num_bodies, 4) world orientations, xyzw.
        ids: body column indices to measure.
        corners: (len(ids), K, 3) link-frame points of those bodies -- a collision mesh's vertices,
            padded to a common K by :func:`pad_point_clouds`.
    """
    k = corners.shape[1]
    n, nb = body_pos_w.shape[0], len(ids)
    pos = body_pos_w[:, ids][:, :, None, :].expand(n, nb, k, 3).reshape(-1, 3)
    quat = body_quat_w[:, ids][:, :, None, :].expand(n, nb, k, 4).reshape(-1, 4)
    pts = corners[None].expand(n, nb, k, 3).reshape(-1, 3)
    world = (pos + quat_apply(quat, pts)).reshape(n, nb, k, 3)
    lowest = world[..., 2].argmin(dim=-1)
    return world.gather(-2, lowest[..., None, None].expand(n, nb, 1, 3)).squeeze(-2)


def mesh_min_z(body_pos_w: torch.Tensor, body_quat_w: torch.Tensor,
               ids: list[int], corners: torch.Tensor) -> torch.Tensor:
    """Lowest world z of the selected bodies' collision meshes, shape (N,) [m].

    Contact force says a body is loaded; it does not say what it is loaded against. The body origin
    is not enough either (a mesh can sit above its own origin), so the mesh points are rotated by
    the live pose and the minimum world z is read: ground is z=0, so a negative value is mesh
    through the floor.

    Args:
        body_pos_w: (N, num_bodies, 3) world positions.
        body_quat_w: (N, num_bodies, 4) world orientations, xyzw.
        ids: body column indices to measure.
        corners: (len(ids), K, 3) link-frame points of those bodies -- a collision mesh's vertices,
            padded to a common K by :func:`pad_point_clouds`.
    """
    return mesh_lowest_point(body_pos_w, body_quat_w, ids, corners)[..., 2]


def contact_point_velocity(com_lin_vel_w: torch.Tensor, ang_vel_w: torch.Tensor,
                           com_pos_w: torch.Tensor, point_pos_w: torch.Tensor) -> torch.Tensor:
    """Velocity of a point rigidly attached to a body: ``v_com + ω × (p − p_com)``, (N, B, 3) [m/s].

    The reference point is the **COM**, and that is not a detail: in this framework
    ``body_lin_vel_w`` aliases ``body_com_lin_vel_w`` while ``body_pos_w`` gives the link origin.
    Pairing those two mixes reference points and mis-states the ``ω × r`` term by
    ``ω × (origin − com)`` for every body whose mass is offset from its link origin -- the normal
    case, and exactly why a foot *origin* speed could not answer "is the contact point sliding": a
    foot rolling over its toe moves its origin a lot while its contact point stands still.

    Args:
        com_lin_vel_w: (N, B, 3) world linear velocity of each body's COM [m/s].
        ang_vel_w: (N, B, 3) world angular velocity [rad/s].
        com_pos_w: (N, B, 3) world COM position [m].
        point_pos_w: (N, B, 3) world position of the point on the body [m].

    ponytail: the point is taken to be the deepest collision-mesh vertex -- a geometric guess at
    where contact is, with a ceiling of mesh resolution plus one control step of pose lag. Upgrade
    path is the contact pair from a ``force_matrix_w`` sensor, which both locates the real point and
    separates ground contact from self-collision.
    """
    return com_lin_vel_w + torch.cross(ang_vel_w, point_pos_w - com_pos_w, dim=-1)


def target_vertex_delta(jacobian_w: torch.Tensor, joint_error: torch.Tensor,
                        offset_w: torch.Tensor) -> torch.Tensor:
    """Where a body point goes if the joints reach their targets, to first order, (N, B, 3) [m].

    The step that separates "the target itself holds the foot down" from "the actuator does": a
    target error the Jacobian says would lift the sole, against a sole that stays low, is an actuator
    that cannot follow; a target error that would not lift it either is a target that never asked for
    height.

    Args:
        jacobian_w: (N, B, 6, J) world Jacobian of the bodies, as ``body_link_jacobian_w`` gives it.
        joint_error: (N, 1, J) or (N, B, J) joint target minus actual position [rad], aligned with the
            Jacobian's DoF axis -- leading base-DoF columns first, then joints in ``joint_names``
            order, so a caller that has no base target pads those columns with zeros (the reading
            then means "these joints met their targets and the base did not move").
        offset_w: (N, B, 3) vector from the body's link origin to the point, in world [m].

    ponytail: first order in the joint error, one step, no contact. It is a direction-and-order
    reading, valid while that error stays small (measured here at 0.01-0.26 rad), not the pose the
    target would settle into -- that would need the targets replayed through a solver, a different
    instrument.
    """
    linear, rotation = target_vertex_delta_parts(jacobian_w, joint_error, offset_w)
    return linear + rotation


def target_vertex_delta_parts(jacobian_w: torch.Tensor, joint_error: torch.Tensor,
                              offset_w: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """:func:`target_vertex_delta` split into its two terms, each (N, B, 3) [m].

    The split is not cosmetic: the linear term is mirror-invariant under a left/right swap of a
    mirrored body, the rotation term is not (it carries the offset and the roll), so only the split
    can say whether a difference between two mirrored legs comes from the motion or from the
    estimator. Measured 2026-09-23 on lizard2: the left and right front legs' joint targets are
    mirror images and their meshes are the same shape, yet the predicted clearances came out with
    opposite signs -- so the term that flips had to be identified before the reading could be used.

    Args:
        jacobian_w: (N, B, 6, J) world Jacobian of the bodies, as ``body_link_jacobian_w`` gives it.
        joint_error: (N, 1, J) or (N, B, J) joint target minus actual position [rad].
        offset_w: (N, B, 3) vector from the body's link origin to the point, in world [m].
    """
    delta = (jacobian_w @ joint_error.unsqueeze(-1)).squeeze(-1)  # (N, B, 6)
    return delta[..., :3], torch.cross(delta[..., 3:], offset_w, dim=-1)


def yaw_frame_offset(root_pos_w: torch.Tensor, root_quat_w: torch.Tensor,
                     body_pos_w: torch.Tensor) -> torch.Tensor:
    """Body positions relative to the root, in the yaw-aligned gravity frame, (N, B, 3) [m].

    The frame the reward kernel and the acceptance metrics already read, so a fore-aft trajectory
    here and a forward speed there are one coordinate system: ``[..., 0]`` fore-aft, ``[..., 1]``
    lateral, ``[..., 2]`` up. Pitch and roll are projected out on purpose -- a pitching gait must
    not read as fore-aft travel.

    Args:
        root_pos_w: (N, 3) root world position.
        root_quat_w: (N, 4) root world orientation, xyzw.
        body_pos_w: (N, B, 3) body world positions.
    """
    delta = body_pos_w - root_pos_w[:, None, :]
    yaw = yaw_quat(root_quat_w).unsqueeze(1).expand(-1, delta.shape[1], -1)
    return quat_apply_inverse(yaw, delta)

