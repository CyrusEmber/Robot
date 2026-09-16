# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""The two reward kernels this line cannot import.

The baseline line's reason to exist is a frozen, enumerable dependency surface, so it
owns its own copies of the two terms it needs from the family's ``teacher_mdp.py`` -- a
shared file that three other versions have already mutated. Depending on it at runtime
would put an unknowable amount of someone else's in-flight work inside "the baseline
recipe", which is exactly what this line was created to stop.

A copy drifts, so ``test_baseline_mdp.py`` asserts these agree numerically with the
originals over random inputs. That test imports ``teacher_mdp`` on purpose: a test-only
import catches drift without putting the shared file on the training path.
"""

import torch

from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.math import quat_apply_inverse, yaw_quat


def miki_tracking_kernel(
    cmd_xy: torch.Tensor, vel_yaw_xy: torch.Tensor, sigma_sq: float = 0.25
) -> torch.Tensor:
    """Symmetric 2D velocity-tracking kernel ``exp(-||dv||^2 / sigma_sq)``.

    The error is the FULL 2D vector, so overspeed, underspeed, lateral drift and
    standstill all lose credit -- unlike a one-sided kernel, which scores standing still
    the same as being badly off in the rewarded direction.

    Args:
        cmd_xy: commanded velocity [m/s], shape (N, 2).
        vel_yaw_xy: base velocity in the yaw-aligned gravity frame [m/s], shape (N, 2).
        sigma_sq: kernel bandwidth [m^2/s^2].

    Returns:
        Shape (N,) in [0, 1].
    """
    return torch.exp(-(cmd_xy - vel_yaw_xy).square().sum(dim=-1) / sigma_sq)


def track_lin_vel_xy_miki(
    env,
    command_name: str,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
    sigma_sq: float = 0.25,
) -> torch.Tensor:
    """Linear-velocity tracking in the yaw-aligned gravity frame.

    The frame is the point: the error is taken against the commanded direction, so
    walking fast in whatever direction the robot happens to be facing does not earn
    tracking credit. With a fixed forward command that is the quantity "walk forward at
    0.5 m/s" actually means.

    Args:
        env: the manager-based env.
        command_name: velocity command term name.
        asset_cfg: articulation to read.
        sigma_sq: kernel bandwidth [m^2/s^2].

    Returns:
        Shape (num_envs,).
    """
    asset = env.scene[asset_cfg.name]
    vel_yaw = quat_apply_inverse(
        yaw_quat(asset.data.root_quat_w.torch), asset.data.root_lin_vel_w.torch
    )[:, :2]
    cmd = env.command_manager.get_command(command_name)[:, :2]
    return miki_tracking_kernel(cmd, vel_yaw, sigma_sq)


def belly_contact_force(env, sensor_cfg: SceneEntityCfg, force_scale: float) -> torch.Tensor:
    """Continuous base-contact penalty proportional to the net contact force.

    Unlike a thresholded contact penalty this has no dead zone: a graze costs less than
    full weight-bearing but nothing is free, so the gradient survives the moment the
    belly touches down. With ``force_scale`` = nominal body weight (72 kg x 9.81 ~
    706 N), a flat belly carrying the robot scores ~1.0 per step at weight -0.5.

    Args:
        env: the manager-based env.
        sensor_cfg: contact sensor whose body ids are read (resolved against the sensor,
            not the articulation -- the two body orderings are not guaranteed to match).
        force_scale: normalization force [N].

    Returns:
        Shape (num_envs,).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    forces = sensor.data.net_forces_w.torch[:, sensor_cfg.body_ids, :]
    return torch.linalg.norm(forces, dim=-1).sum(dim=-1) / force_scale
