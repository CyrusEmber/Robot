# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Privileged observation terms for the lizard teacher policy (Miki et al. 2022 style).

These expose simulation ground truth to the teacher ACTOR. The distilled
student never sees them; they define what the belief encoder must infer.
"""

from __future__ import annotations

import torch
from isaaclab.managers import SceneEntityCfg

if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be executed directly.")


def foot_contact_bools(env, sensor_cfg: SceneEntityCfg, threshold: float = 1.0) -> torch.Tensor:
    """Foot contact flags (1.0 = in contact) from net contact force norm [N].

    Shape: (num_envs, num_resolved_bodies).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    forces = sensor.data.net_forces_w.torch[:, sensor_cfg.body_ids, :]
    contact = torch.linalg.norm(forces, dim=-1) > threshold
    return contact.float()


def feet_air_time(env, sensor_cfg: SceneEntityCfg) -> torch.Tensor:
    """Current air time of the resolved feet bodies [s] (0 while in contact).

    Shape: (num_envs, num_resolved_bodies). Requires
    ``ContactSensorCfg.track_air_time = True`` (the velocity task default).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    return sensor.data.current_air_time.torch[:, sensor_cfg.body_ids]


def body_mass_truth(env, asset_cfg: SceneEntityCfg) -> torch.Tensor:
    """Per-body ground-truth mass [kg] (post domain randomization).

    Shape: (num_envs, num_resolved_bodies).
    """
    asset = env.scene[asset_cfg.name]
    return asset.data.body_mass.torch[:, asset_cfg.body_ids]
