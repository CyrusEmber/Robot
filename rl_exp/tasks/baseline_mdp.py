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

``test_baseline_mdp.py`` pins this line's mathematical and sensor/frame contracts.
It does not import the teacher: intentional changes to main must not redefine this line.
"""

import torch

from isaaclab.managers import ManagerTermBase, SceneEntityCfg, TerminationTermCfg
from isaaclab.utils.math import quat_apply_inverse, yaw_quat


class ContactLoadDwellTerm(ManagerTermBase):
    """Terminate once a guarded body presses the ground for ``dwell_s``.

    On flat ground the head chain has no business touching the floor at all, so the criterion is
    *contact*, not weight-bearing: a vertical reaction above ``load_n`` newtons ends the episode,
    with ``dwell_s`` defaulting to 0 -- the first frame it presses. The 1 N threshold is the same
    one this file's ``base_contact`` termination uses and the one the evaluator calls "in contact"
    when it reads a rollout, so "touch" means one thing on this line. v1's trained checkpoint is
    the case the guard exists for: ``neck_pitch`` carried 82-90 N (11.6-12.8% of the 706 N body
    weight) while the head scraped the floor, and nothing stopped it. An earlier draft waited for
    10% of body weight held 0.5 s, which contact chatter defeats -- the same rollout never held it
    for more than 0.22 s while sitting above the threshold on two thirds of its frames.

    Only the vertical component is read. A floor contact pushes up, while the self-contacts a
    flailing fresh policy produces are mostly lateral, and this term has no contact-pair filter to
    separate them with -- that separation is a diagnose-side job, not a training-side one.

    The counter clears when the press clears and on every episode reset -- ``TerminationManager``
    calls ``reset(env_ids)`` on stateful terms, the same contract ``teacher_mdp.RollOverTerm``
    relies on (this module keeps its own copy: intentional changes to main must not redefine this
    line).
    """

    def __init__(self, cfg: TerminationTermCfg, env):
        super().__init__(cfg, env)
        ids = cfg.params["sensor_cfg"].body_ids
        self._ids = torch.tensor(ids, dtype=torch.long, device=env.device)
        self._steps = torch.zeros(env.num_envs, dtype=torch.long, device=env.device)

    def __call__(self, env, sensor_cfg: SceneEntityCfg, load_n: float = 1.0,
                 dwell_s: float = 0.0) -> torch.Tensor:
        forces = env.scene[sensor_cfg.name].data.net_forces_w.torch[:, self._ids, 2]
        pressed = (forces > load_n).any(dim=1)
        self._steps = torch.where(pressed, self._steps + 1, torch.zeros_like(self._steps))
        return self._steps >= max(1, int(round(dwell_s / env.step_dt)))

    def reset(self, env_ids=None) -> None:
        if env_ids is None:
            self._steps.zero_()
        else:
            self._steps[env_ids] = 0


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

    Forward is relative to the current yaw, not a fixed world heading. A robot moving
    along its own heading at the commanded speed earns full linear tracking credit;
    yaw drift is reported separately by the baseline evaluator.

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
