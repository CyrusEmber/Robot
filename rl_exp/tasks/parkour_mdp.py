# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Position-task command and reward terms for the parkour line (Rudin et al.
2022a task description, Parkour in the Wild reward table).

The position command resamples a target pose (r*, psi*, t*) around the robot;
t* doubles as the resampling timer. Rewards follow the paper's fine-tuning
table (weights wired in the env cfg from parkour_params.yaml); deviations are
declared in parkour/v1/PLAN.md and the params yaml comments.
"""

from __future__ import annotations

import torch

from isaaclab.envs import mdp
from isaaclab.managers import CommandTerm, CommandTermCfg, ManagerTermBase, SceneEntityCfg
from isaaclab.utils.configclass import configclass
from isaaclab.utils.math import quat_apply_inverse, wrap_to_pi

if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be executed directly.")


def _yaw_from_quat(quat: torch.Tensor) -> torch.Tensor:
    """Yaw angle [rad] from (x, y, z, w) quaternions, shape (N,)."""
    return torch.atan2(
        2.0 * (quat[:, 0] * quat[:, 3] + quat[:, 1] * quat[:, 2]),
        1.0 - 2.0 * (quat[:, 2] ** 2 + quat[:, 3] ** 2),
    )


@configclass
class PositionCommandCfg(CommandTermCfg):
    """Configuration for :class:`PositionCommand`.

    The base ``resampling_time_range`` is a placeholder: the actual per-command
    budget t* is drawn in :meth:`PositionCommand._resample_command` and written
    over ``time_left`` (the base ``_resample`` runs first, then delegates).
    """

    asset_name: str = "robot"
    """Name of the scene entity the command targets."""

    target_distance_range: tuple[float, float] = (2.0, 8.0)
    """Target distance sampling range [m], from the current base pose."""

    heading_span: float = 0.785
    """Sampling cone half-width [rad] around the current base yaw."""

    heading_jitter: float = 0.5
    """Target heading jitter [rad] around the travel direction."""

    speed_range: tuple[float, float] = (0.5, 2.0)
    """Desired-speed sampling range [m/s]; budget = distance / speed."""

    budget_range: tuple[float, float] = (2.0, 18.0)
    """Clamped time-budget range [s] (episode is 20 s)."""

    pos_threshold: float = 0.25
    """Arrival position threshold [m] (paper S_L)."""

    heading_threshold: float = 0.5
    """Arrival heading threshold [rad] (paper S_L)."""

    tile_half_margin: float = 1.5
    """Keep targets this far inside the terrain tile border [m]."""


class PositionCommand(CommandTerm):
    """Goal-conditioned position task: (r*, psi*, t*) waypoint resampling.

    Command tensor (per env): [delta_r_base_x, delta_r_base_y, delta_heading,
    t_star] -- the base-frame target displacement, heading error, and the
    remaining time budget. Arrival (paper S_L: position within
    ``pos_threshold`` AND heading within ``heading_threshold``) resamples the
    command immediately; budget expiry resamples through the base-class
    ``time_left`` timer.
    """

    def __init__(self, cfg: PositionCommandCfg, env):
        super().__init__(cfg, env)
        self.robot = env.scene[cfg.asset_name]
        n = self.num_envs
        self._target_pos_w = torch.zeros(n, 3, device=self.device)
        self._target_heading_w = torch.zeros(n, device=self.device)
        self._arrived = torch.zeros(n, dtype=torch.bool, device=self.device)
        self.metrics["position_error"] = torch.zeros(n, device=self.device)
        self.metrics["heading_error"] = torch.zeros(n, device=self.device)
        self.metrics["success"] = torch.zeros(n, device=self.device)
        self.metrics["last_outcome"] = torch.zeros(n, device=self.device)

    @property
    def command(self) -> torch.Tensor:
        delta = self._target_pos_w - self.robot.data.root_pos_w.torch
        delta_base = quat_apply_inverse(self.robot.data.root_quat_w.torch, delta)[:, :2]
        yaw = _yaw_from_quat(self.robot.data.root_quat_w.torch)
        heading_err = wrap_to_pi(self._target_heading_w - yaw)
        return torch.cat(
            [delta_base, heading_err.unsqueeze(-1), self.time_left.unsqueeze(-1)], dim=-1
        )

    def _resample_command(self, env_ids):
        n = len(env_ids)
        cfg = self.cfg
        # outcome bookkeeping for the command being replaced
        self.metrics["last_outcome"][env_ids] = self._arrived[env_ids].float()
        self._arrived[env_ids] = False
        # sample distance and direction around the current base pose
        base_pos = self.robot.data.root_pos_w.torch[env_ids, :2]
        base_yaw = _yaw_from_quat(self.robot.data.root_quat_w.torch[env_ids])
        dist = torch.empty(n, device=self.device).uniform_(*cfg.target_distance_range)
        rel_dir = torch.empty(n, device=self.device).uniform_(-cfg.heading_span, cfg.heading_span)
        abs_dir = base_yaw + rel_dir
        target_xy = base_pos + dist.unsqueeze(-1) * torch.stack(
            [torch.cos(abs_dir), torch.sin(abs_dir)], dim=-1
        )
        # clamp inside the assigned terrain tile (curriculum may move robots
        # between tiles; env_origins tracks the current one)
        origins = self._env.scene.terrain.env_origins[env_ids, :2]
        half = 8.0 - cfg.tile_half_margin
        target_xy = torch.clamp(target_xy, origins - half, origins + half)
        # budget from the post-clamp distance
        dist_actual = torch.linalg.norm(target_xy - base_pos, dim=-1)
        speed = torch.empty(n, device=self.device).uniform_(*cfg.speed_range)
        budget = torch.clamp(dist_actual / speed, *cfg.budget_range).clamp(min=0.5)
        self.time_left[env_ids] = budget
        self._target_pos_w[env_ids, :2] = target_xy
        self._target_pos_w[env_ids, 2] = 0.0
        self._target_heading_w[env_ids] = abs_dir + torch.empty(
            n, device=self.device
        ).uniform_(-cfg.heading_jitter, cfg.heading_jitter)

    def _update_command(self):
        delta = self._target_pos_w - self.robot.data.root_pos_w.torch
        dist = torch.linalg.norm(delta[:, :2], dim=-1)
        yaw = _yaw_from_quat(self.robot.data.root_quat_w.torch)
        heading_err = wrap_to_pi(self._target_heading_w - yaw)
        arrived = (dist < self.cfg.pos_threshold) & (heading_err.abs() < self.cfg.heading_threshold)
        newly = arrived & ~self._arrived
        self._arrived |= arrived
        resample_ids = newly.nonzero().flatten()
        if len(resample_ids) > 0:
            self._resample(resample_ids)

    def _update_metrics(self):
        delta = self._target_pos_w - self.robot.data.root_pos_w.torch
        dist = torch.linalg.norm(delta[:, :2], dim=-1)
        yaw = _yaw_from_quat(self.robot.data.root_quat_w.torch)
        heading_err = wrap_to_pi(self._target_heading_w - yaw).abs()
        self.metrics["position_error"][:] = dist
        self.metrics["heading_error"][:] = heading_err
        self.metrics["success"][:] = (
            (dist < self.cfg.pos_threshold) & (heading_err < self.cfg.heading_threshold)
        ).float()


# --- task rewards (paper Table 2; weights in the env cfg) ---


def track_position(env, command_name: str, gate: str = "none") -> torch.Tensor:
    """Linear position reward ``1 - 0.5 * ||r_xy - r*_xy||`` (paper Table 2).

    Args:
        env: The environment instance.
        command_name: Name of the :class:`PositionCommand` term.
        gate: ``"t_star_lt_1"`` applies the paper's literal 1_{t*<1} gate
            (reward only in the final second); ``"none"`` rewards the whole
            approach phase (declared deviation -- the literal gate leaves the
            approach without position incentive).

    Returns:
        Reward per env, shape (num_envs,).
    """
    cmd = env.command_manager.get_command(command_name)
    raw = 1.0 - 0.5 * torch.linalg.norm(cmd[:, :2], dim=-1)
    if gate == "t_star_lt_1":
        raw = raw * (cmd[:, 3] < 1.0).float()
    return raw


def track_heading(env, command_name: str, gate: str = "none") -> torch.Tensor:
    """Linear heading reward ``1 - 0.5 * ||psi - psi*||`` (paper Table 2).

    Args:
        env: The environment instance.
        command_name: Name of the :class:`PositionCommand` term.
        gate: Same semantics as :func:`track_position`.

    Returns:
        Reward per env, shape (num_envs,).
    """
    cmd = env.command_manager.get_command(command_name)
    raw = 1.0 - 0.5 * cmd[:, 2].abs()
    if gate == "t_star_lt_1":
        raw = raw * (cmd[:, 3] < 1.0).float()
    return raw


def don_t_wait(env, speed_threshold: float = 0.2) -> torch.Tensor:
    """Paper ``Don't wait`` penalty: 1(||v_b|| < threshold), speed in [m/s].

    Args:
        env: The environment instance.
        speed_threshold: Standing-still speed threshold [m/s] (paper 0.2).

    Returns:
        Penalty indicator per env, shape (num_envs,).
    """
    lin_vel = env.scene["robot"].data.root_lin_vel_b.torch
    return (torch.linalg.norm(lin_vel, dim=-1) < speed_threshold).float()


def stand_at_target(env, command_name: str) -> torch.Tensor:
    """Paper ``Stand at target``: S_L * ||q - q_d||, joint deviation [rad] at target.

    Args:
        env: The environment instance.
        command_name: Name of the :class:`PositionCommand` term.

    Returns:
        Penalty per env, shape (num_envs,).
    """
    robot = env.scene["robot"]
    cmd = env.command_manager.get_command(command_name)
    arrived = (
        (torch.linalg.norm(cmd[:, :2], dim=-1) < 0.25) & (cmd[:, 2].abs() < 0.5)
    ).float()
    deviation = torch.linalg.norm(
        robot.data.joint_pos.torch - robot.data.default_joint_pos.torch, dim=-1
    )
    return arrived * deviation


def feet_excess_force(env, sensor_cfg: SceneEntityCfg, threshold: float = 700.0) -> torch.Tensor:
    """Paper ``Feet force``: sum over feet of max(||F_f|| - threshold, 0)^2, forces in [N].

    Args:
        env: The environment instance.
        sensor_cfg: Contact-force sensor on the feet.
        threshold: Per-foot force threshold [N] (paper 700).

    Returns:
        Penalty per env, shape (num_envs,).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    forces = sensor.data.net_forces_w.torch[:, sensor_cfg.body_ids, :]
    excess = torch.clamp(torch.linalg.norm(forces, dim=-1) - threshold, min=0.0)
    return excess.square().sum(dim=-1)


def joint_vel_exceed(env, asset_cfg: SceneEntityCfg, limit: float) -> torch.Tensor:
    """Paper ``Joint vel. limit``: sum over joints of max(|q_dot| - limit, 0) [rad/s].

    Args:
        env: The environment instance.
        asset_cfg: Articulation filtered to the joint group (legs / feet).
        limit: Velocity limit [rad/s] of the group.

    Returns:
        Penalty per env, shape (num_envs,).
    """
    asset = env.scene[asset_cfg.name]
    joint_vel = asset.data.joint_vel.torch[:, asset_cfg.joint_ids]
    return torch.clamp(joint_vel.abs() - limit, min=0.0).sum(dim=-1)


def _pd_torque(env, asset_cfg: SceneEntityCfg) -> torch.Tensor:
    """Reconstruct actuator torques from the PD model, shape (num_envs, n_joints).

    Implicit actuators hide the applied torque from the data API (stock
    ``joint_torques_l2`` reads ``applied_torque``, which is all-zero for
    implicit drives) and the solver clips at the effort limit internally.
    Reconstructing ``tau = K * (q* - q) - D * q_dot`` gives the pre-clip
    torque the paper's Torque/Torque-limit terms penalize. ``K``/``D`` come
    from the sim (they reflect startup gain randomization).
    """
    asset = env.scene[asset_cfg.name]
    ids = asset_cfg.joint_ids
    target = asset.data.joint_pos_target.torch[:, ids]
    pos = asset.data.joint_pos.torch[:, ids]
    vel = asset.data.joint_vel.torch[:, ids]
    stiffness = asset.data.joint_stiffness.torch[:, ids]
    damping = asset.data.joint_damping.torch[:, ids]
    return stiffness * (target - pos) - damping * vel


def joint_torques_l2_pd(env, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """Paper ``Torque``: ||tau||^2 [N^2 m^2], reconstructed PD torques."""
    return _pd_torque(env, asset_cfg).square().sum(dim=-1)


def torque_exceed(env, asset_cfg: SceneEntityCfg, limit: float) -> torch.Tensor:
    """Paper ``Torque limit``: sum over joints of max(|tau| - limit, 0) [N*m].

    Args:
        env: The environment instance.
        asset_cfg: Articulation filtered to the joint group (legs / feet).
        limit: Effort limit [N*m] of the group.

    Returns:
        Penalty per env, shape (num_envs,).
    """
    return torch.clamp(_pd_torque(env, asset_cfg).abs() - limit, min=0.0).sum(dim=-1)


def base_acc_l2(env, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """Paper ``Base acc.``: ||v_dot||^2 + 0.02 * ||omega_dot||^2 of the resolved bodies [m/s^2, rad/s^2].

    Uses ``body_com_acc_w`` (the fork has no ``root_lin_acc_b``); wire
    ``asset_cfg`` to the base body.

    Args:
        env: The environment instance.
        asset_cfg: Articulation filtered to the base body.

    Returns:
        Penalty per env, shape (num_envs,).
    """
    asset = env.scene[asset_cfg.name]
    acc = asset.data.body_com_acc_w.torch[:, asset_cfg.body_ids, :]  # (N, B, 6)
    lin = acc[..., 0:3]
    ang = acc[..., 3:6]
    return lin.square().sum(dim=(-1, -2)) + 0.02 * ang.square().sum(dim=(-1, -2))


class FeetAccPenalty(ManagerTermBase):
    """Paper ``Feet acc.``: sum over feet of ||v_dot_f|| [m/s^2].

    Stateful finite difference of the foot body velocities (articulation data
    carries no body accelerations). Shape: (num_envs,).
    """

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self.robot = env.scene["robot"]
        self.foot_ids, _ = self.robot.find_bodies(".*_foot")
        self._prev_vel = torch.zeros(
            env.scene.num_envs, len(self.foot_ids), 3, device=self.robot.device
        )

    def __call__(self, env, sensor_cfg: SceneEntityCfg) -> torch.Tensor:
        """Compute the penalty.

        Args:
            env: The environment instance.
            sensor_cfg: Contact-force sensor on the feet (foot body resolution).
        """
        vel = self.robot.data.body_lin_vel_w.torch[:, self.foot_ids, :]
        acc = (vel - self._prev_vel) / env.step_dt
        self._prev_vel.copy_(vel)
        return acc.norm(dim=-1).sum(dim=-1)


def termination_penalty(
    env,
    asset_cfg: SceneEntityCfg,
    gravity_z_limit: float = 0.707,
    joint_vel_limit: float = 10.0,
) -> torch.Tensor:
    """Paper ``Termination`` reward: 1_{alpha>135 deg} + 1_{q_dot > limit}.

    Fires on the same conditions as the termination terms (tilt past
    ``gravity_z_limit`` in projected_gravity_b z, any joint velocity over
    ``joint_vel_limit``); the DoneTerms end the episode, this term carries the
    paper's -2e3 penalty on the final step.

    Args:
        env: The environment instance.
        asset_cfg: Articulation filtered to the velocity-limited joints.
        gravity_z_limit: Projected-gravity z threshold (0.707 = 45 deg tilt =
            the paper's alpha > 135 deg).
        joint_vel_limit: Joint velocity limit [rad/s].

    Returns:
        Penalty per env, shape (num_envs,).
    """
    robot = env.scene["robot"]
    tilted = (robot.data.projected_gravity_b.torch[:, 2] > gravity_z_limit).float()
    joint_vel = robot.data.joint_vel.torch[:, asset_cfg.joint_ids]
    over_speed = (joint_vel.abs() > joint_vel_limit).any(dim=-1).float()
    return tilted + over_speed


def tilt_terminate(env, gravity_z_limit: float = 0.707) -> torch.Tensor:
    """Terminate on tilt: projected_gravity_b z above ``gravity_z_limit``.

    The paper's 1_{alpha>135 deg} (alpha = angle between base z-axis and
    gravity) equals projected_gravity_b[:, 2] > 0.707 (45 deg tilt).

    Args:
        env: The environment instance.
        gravity_z_limit: Projected-gravity z threshold (0.707 = 45 deg).

    Returns:
        Termination flags per env, shape (num_envs,).
    """
    robot = env.scene["robot"]
    return robot.data.projected_gravity_b.torch[:, 2] > gravity_z_limit


def joint_vel_limit_terminate(env, asset_cfg: SceneEntityCfg, limit: float) -> torch.Tensor:
    """Terminate when any resolved joint velocity exceeds ``limit`` [rad/s].

    Args:
        env: The environment instance.
        asset_cfg: Articulation filtered to the joint group (legs / feet).
        limit: Velocity limit [rad/s] of the group.

    Returns:
        Termination flags per env, shape (num_envs,).
    """
    asset = env.scene[asset_cfg.name]
    joint_vel = asset.data.joint_vel.torch[:, asset_cfg.joint_ids]
    return (joint_vel.abs() > limit).any(dim=-1)
