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
import warp as wp

from isaaclab.managers import ManagerTermBase, ObservationTermCfg, SceneEntityCfg
from isaaclab.sensors.ray_caster import RayCaster
from isaaclab.utils.warp.kernels import raycast_mesh_masked_kernel

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


def foot_contact_forces(env, sensor_cfg: SceneEntityCfg) -> torch.Tensor:
    """Ground-truth foot contact force vectors [N], world frame.

    Miki et al. 2022 privileged info: contact forces. One 3-vector per foot.
    Shape: (num_envs, 3 * num_feet).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    forces = sensor.data.net_forces_w.torch[:, sensor_cfg.body_ids, :]
    return forces.reshape(forces.shape[0], -1)


def thigh_shank_contacts(env, sensor_cfg: SceneEntityCfg, threshold: float = 1.0) -> torch.Tensor:
    """Binary contact flags of thigh (HFE) and shank (KFE) links.

    Miki et al. 2022 privileged info: thigh and shank contact.
    Shape: (num_envs, 2 * num_legs).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    forces = sensor.data.net_forces_w.torch[:, sensor_cfg.body_ids, :]
    contact = torch.linalg.norm(forces, dim=-1) > threshold
    return contact.float()


def base_external_wrench(env, asset_cfg: SceneEntityCfg) -> torch.Tensor:
    """Persistent external force + torque on the base [N, N*m], body frame.

    Miki et al. 2022 privileged info: external forces and torques. Reads the
    same wrench composer that ``apply_external_force_torque`` writes into, so
    this is exactly the wrench the simulation applies. Zero when the event is
    disabled (PLAY variant).
    Shape: (num_envs, 6).
    """
    asset = env.scene[asset_cfg.name]
    body_ids = asset_cfg.body_ids
    idx = body_ids[0] if isinstance(body_ids, list) else 0
    force = asset.permanent_wrench_composer.out_force_b.torch[:, idx, :]
    torque = asset.permanent_wrench_composer.out_torque_b.torch[:, idx, :]
    return torch.cat([force, torque], dim=-1)


def foot_friction_truth(env, asset_cfg: SceneEntityCfg) -> torch.Tensor:
    """Per-foot static friction coefficient (post material randomization).

    Miki et al. 2022 privileged info: friction coefficients. The physics
    material event bucket-randomizes friction PER SHAPE at startup only, so
    the readback is cached on the env at first call; the PLAY variant never
    randomizes and reads the default material instead.
    Shape: (num_envs, num_feet).
    """
    asset = env.scene[asset_cfg.name]
    cached = getattr(env, "_lizard_foot_friction", None)
    if cached is not None:
        return cached
    # per-body shape counts: framework workaround (same as
    # mdp.events randomize_rigid_body_material); shapes are laid out per link
    # in link order in the material buffer
    num_shapes_per_body = []
    for link_path in asset.root_view.link_paths[0]:
        link_view = asset._physics_sim_view.create_rigid_body_view(link_path)
        num_shapes_per_body.append(link_view.max_shapes)
    materials = wp.to_torch(asset.root_view.get_material_properties())
    cols = []
    for body_id in asset_cfg.body_ids:
        start_idx = sum(num_shapes_per_body[:body_id])
        end_idx = start_idx + num_shapes_per_body[body_id]
        cols.append(materials[:, start_idx:end_idx, 0].mean(dim=1))
    cached = torch.stack(cols, dim=1)
    env._lizard_foot_friction = cached
    return cached


class FootContactNormalsTerm(ManagerTermBase):
    """Per-foot terrain surface normals via vertical raycast (stateful term).

    Miki et al. 2022 privileged info: contact normals. One ray per foot,
    launched from ``start_offset`` above the foot straight down against the
    terrain mesh that the height scanner already registered in
    ``RayCaster.meshes``. Normals are world frame; zero when no hit within
    ``max_distance``.
    Shape: (num_envs, 3 * num_feet).
    """

    def __init__(self, cfg: ObservationTermCfg, env):
        super().__init__(cfg, env)
        self.robot = env.scene["robot"]
        self.foot_ids, _ = self.robot.find_bodies(".*_foot")
        device = self.robot.device
        mesh_path = cfg.params.get("mesh_prim_path", "/World/ground")
        # the height scanner must have registered the terrain mesh already
        # (scene sensors initialize before observation-manager terms)
        if (mesh_path, device) in RayCaster.meshes:
            mesh = RayCaster.meshes[(mesh_path, device)]
        else:
            matches = [m for key, m in RayCaster.meshes.items() if key[0] == mesh_path]
            if not matches:
                raise RuntimeError(
                    f"FootContactNormalsTerm: terrain mesh '{mesh_path}' is not registered"
                    " in RayCaster.meshes. The scene needs a height scanner over the same"
                    " mesh, and scene sensors must initialize before observation terms."
                )
            # device-string formatting mismatch fallback (same prim, any device key)
            mesh = matches[0]
        self._mesh_id = mesh.id
        self._num_envs = env.scene.num_envs
        self._num_feet = len(self.foot_ids)
        self._max_dist = float(cfg.params.get("max_distance", 2.0))
        self._start_offset = float(cfg.params.get("start_offset", 0.5))
        # persistent torch buffers + zero-copy warp views
        shape = (self._num_envs, self._num_feet)
        self._starts_t = torch.zeros(*shape, 3, device=device)
        self._dirs_t = torch.zeros(*shape, 3, device=device)
        self._hits_t = torch.zeros(*shape, 3, device=device)
        self._dist_t = torch.zeros(*shape, device=device)
        self._normals_t = torch.zeros(*shape, 3, device=device)
        self._starts_w = wp.from_torch(self._starts_t).view(wp.vec3f)
        self._dirs_w = wp.from_torch(self._dirs_t).view(wp.vec3f)
        self._hits_w = wp.from_torch(self._hits_t).view(wp.vec3f)
        self._dist_w = wp.from_torch(self._dist_t)
        self._normals_w = wp.from_torch(self._normals_t).view(wp.vec3f)
        self._env_mask = wp.full((self._num_envs,), True, dtype=wp.bool, device=device)

    def __call__(self, env, **kwargs) -> torch.Tensor:
        foot_pos = self.robot.data.body_pos_w.torch[:, self.foot_ids, :]
        self._starts_t.copy_(foot_pos)
        self._starts_t[:, :, 2] += self._start_offset
        self._dirs_t.zero_()
        self._dirs_t[:, :, 2] = -1.0
        self._normals_t.zero_()
        wp.launch(
            raycast_mesh_masked_kernel,
            dim=(self._num_envs, self._num_feet),
            inputs=[
                self._mesh_id,
                self._env_mask,
                self._starts_w,
                self._dirs_w,
                self._max_dist,
                int(False),
                int(True),
                self._hits_w,
                self._dist_w,
                self._normals_w,
            ],
            device=self.robot.device,
        )
        return self._normals_t.reshape(self._num_envs, -1)
