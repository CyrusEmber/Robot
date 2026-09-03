# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Privileged observation terms for the lizard teacher policy (Miki et al. 2022 style).

These expose simulation ground truth to the teacher ACTOR. The distilled
student never sees them; they define what the belief encoder must infer.

The v3 section at the bottom carries the anti-collapse package (plan
versions/lizard/v3/PLAN.md): c_k curriculum state + readers, c_k-scaled
penalty and DR wrappers, tilt termination, and the anti-drag foot-clearance
reward. The v5 section below it adds the reward-side anti-collapse package
(plan versions/lizard/v5/PLAN.md): EP-style linear velocity tracking,
c_k-scaled foot-slide (r_slip) and undesired-contact (r_co) penalties, and
the constant-weight belly-contact force penalty.
"""

from __future__ import annotations

import torch
import warp as wp

from isaaclab.envs import mdp
from isaaclab.managers import CurriculumTermCfg, ManagerTermBase, ObservationTermCfg, SceneEntityCfg
from isaaclab.utils.configclass import configclass
from isaaclab.utils.math import quat_apply_inverse, yaw_quat
from isaaclab.utils.warp.kernels import raycast_mesh_masked_kernel

# ponytail: RayCaster is deliberately NOT imported at module top. This module is
# imported by env cfgs during hydra compose (pre-AppLauncher); a top-level
# `from isaaclab.sensors.ray_caster import RayCaster` drags in
# isaaclab.sim.simulation_context -> isaacsim -> pip usd-core pxr, which poisons
# sys.modules["pxr"] before Kit starts and breaks omni.kit.usd.mdl
# ("extension class wrapper for base class TfNotice has not been created yet").
# Import it lazily at runtime instead (FootContactNormalsTerm.__init__).

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
    # the physx view readback lands on CPU; observations concatenate on the
    # simulation device, so the cache must move there once
    cached = torch.stack(cols, dim=1).to(asset.device)
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
        from isaaclab.sensors.ray_caster import RayCaster  # lazy: see module-top note

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

    def __call__(
        self,
        env,
        mesh_prim_path: str = "/World/ground",
        max_distance: float = 2.0,
        start_offset: float = 0.5,
    ) -> torch.Tensor:
        # buffers and mesh handle are built once in __init__ from the same cfg
        # params; the manager passes them here again per call and they must
        # stay in the signature for the term-cfg parameter validation
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


# --- v3: anti-collapse package (plan versions/lizard/v3/PLAN.md D1-D4) ---


def init_ck(env, env_ids, c0: float, decay: float, steps_per_iteration: int) -> None:
    """Startup event: stash the c_k schedule params on the env (yaml SSOT).

    Args:
        env: The environment instance.
        env_ids: Unused (event-term call convention carries it).
        c0: Curriculum start value in (0, 1).
        decay: Per-iteration exponent, c_{k+1} = c_k**decay (paper: 0.98).
        steps_per_iteration: Policy steps per PPO iteration; must equal the
            runner's ``num_steps_per_env`` (asserted by check_obs_layout.py).
    """
    env._lizard_ck_params = {
        "c0": float(c0),
        "decay": float(decay),
        "steps_per_iteration": int(steps_per_iteration),
    }


def ck_value(env) -> float:
    """Current c_k, a pure function of ``env.common_step_counter``.

    c_k = c0 ** (decay ** iteration) with iteration = policy steps //
    steps_per_iteration. Pure-function derivation avoids the update-ordering
    hazard (rewards compute BEFORE interval events fire inside env.step).
    Without ``init_ck`` (PLAY/eval harness never wires it), returns 1.0.
    Training restart-from-scratch reheats the warm-up (documented, not fixed).
    """
    params = getattr(env, "_lizard_ck_params", None)
    if params is None:
        return 1.0
    iteration = env.common_step_counter // params["steps_per_iteration"]
    return params["c0"] ** (params["decay"] ** iteration)


def _ck_scale_range(rng, ck: float, anchor: float) -> tuple[float, float]:
    """Scale a (lo, hi) range toward ``anchor`` by c_k (paper: DR from small to full).

    ``anchor`` is the no-randomization identity: 1.0 for multiplicative scale
    operations, 0.0 for additive ones, the midpoint for absolute ranges.
    """
    lo, hi = float(rng[0]), float(rng[1])
    return (anchor + (lo - anchor) * ck, anchor + (hi - anchor) * ck)


# D3: penalty terms x c_k (q_dacc / torque / omega_xy; the plan's fourth term
# feet_slide does not exist in this task's reward set -- F3 documents the erratum)


def joint_acc_l2_ck(env, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """``joint_acc_l2`` penalty scaled by c_k."""
    return mdp.joint_acc_l2(env, asset_cfg) * ck_value(env)


def joint_torques_l2_ck(env, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """``joint_torques_l2`` penalty scaled by c_k."""
    return mdp.joint_torques_l2(env, asset_cfg) * ck_value(env)


def ang_vel_xy_l2_ck(env, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """``ang_vel_xy_l2`` penalty scaled by c_k."""
    return mdp.ang_vel_xy_l2(env, asset_cfg) * ck_value(env)


# D1: tilt termination (repo convention: upright -> projected_gravity_b z = -1)


def tilt_terminate(env, gravity_z_limit: float = -0.6) -> torch.Tensor:
    """Terminate when the body tilts past ``gravity_z_limit`` (upright is -1).

    Args:
        env: The environment instance.
        gravity_z_limit: projected_gravity_b z threshold; -0.6 is ~53 deg
            (estimate, yaml ablation knob -- the paper gives no number).
    """
    robot = env.scene["robot"]
    return robot.data.projected_gravity_b[:, 2] > gravity_z_limit


# D2: anti-drag foot clearance reward (deliberate inversion of the paper's r_fc
# which penalizes swing feet flying TOO HIGH; v3 penalizes swing feet BELOW
# terrain + clearance -- see PLAN v3.1 D2 for the semantics discussion)


class FootClearanceReward(FootContactNormalsTerm):
    """r_fc: penalize swing feet closer than ``clearance`` to their terrain.

    Reuses the frozen per-foot vertical-raycast infrastructure of
    :class:`FootContactNormalsTerm` (subclassing keeps the v2 term untouched).
    Per foot: hinge = clamp(terrain_z + clearance - foot_z, min=0), masked to
    swinging feet (contact-state proxy); env value = mean over feet. A missed
    ray (foot over a >max_distance hole) costs nothing.
    Shape: (num_envs,).
    """

    def __call__(
        self,
        env,
        sensor_cfg: SceneEntityCfg,
        clearance: float = 0.2,
        contact_threshold: float = 1.0,
        mesh_prim_path: str = "/World/ground",
        max_distance: float = 2.0,
        start_offset: float = 0.5,
    ) -> torch.Tensor:
        """Compute the anti-drag penalty.

        Args:
            env: The environment instance.
            sensor_cfg: Contact-force sensor on the feet (swing detection).
            clearance: Required swing clearance above local terrain [m].
            contact_threshold: Contact force norm threshold [N].
            mesh_prim_path: Terrain mesh registered in ``RayCaster.meshes``.
            max_distance: Raycast range [m].
            start_offset: Ray start height above the foot [m].
        """
        # parent call repopulates the shared hit buffers (normals discarded)
        super().__call__(env, mesh_prim_path, max_distance, start_offset)
        terrain_z = self._hits_t[:, :, 2]
        foot_z = self.robot.data.body_pos_w.torch[:, self.foot_ids, 2]
        sensor = env.scene.sensors[sensor_cfg.name]
        forces = sensor.data.net_forces_w.torch[:, sensor_cfg.body_ids, :]
        contact = torch.linalg.norm(forces, dim=-1) > contact_threshold
        gap = terrain_z + clearance - foot_z
        # ray miss -> hit z = inf -> no penalty (foot is over a deep hole)
        gap = torch.where(torch.isinf(terrain_z), torch.full_like(gap, -1.0e9), gap)
        return (torch.clamp(gap, min=0.0) * (~contact).float()).mean(dim=-1)


# D4: reset-mode, c_k-scaled domain randomization wrappers. Each subclasses the
# stock term and scales the distribution range toward the operation's identity
# (scale ops anchor at 1.0, add ops at 0.0) before delegating.


class randomize_rigid_body_mass_ck(mdp.randomize_rigid_body_mass):
    """Body-mass DR with the scale range pulled toward 1.0 by c_k."""

    def __call__(self, env, env_ids, asset_cfg, mass_distribution_params, operation, distribution="uniform",
                 recompute_inertia=True, min_mass=1e-6):
        scaled = _ck_scale_range(mass_distribution_params, ck_value(env), 1.0)
        return super().__call__(
            env, env_ids, asset_cfg, scaled, operation, distribution, recompute_inertia, min_mass
        )


class randomize_rigid_body_com_ck(mdp.randomize_rigid_body_com):
    """Base CoM offset DR with the per-axis ranges pulled toward 0 by c_k."""

    def __call__(self, env, env_ids, com_range, asset_cfg):
        ck = ck_value(env)
        scaled = {axis: _ck_scale_range(rng, ck, 0.0) for axis, rng in com_range.items()}
        return super().__call__(env, env_ids, scaled, asset_cfg)


class randomize_rigid_body_inertia_ck(mdp.randomize_rigid_body_inertia):
    """Diagonal-inertia DR with the scale range pulled toward 1.0 by c_k."""

    def __call__(self, env, env_ids, asset_cfg, inertia_distribution_params, operation="add",
                 distribution="uniform", diagonal_only=True):
        scaled = _ck_scale_range(inertia_distribution_params, ck_value(env), 1.0)
        return super().__call__(env, env_ids, asset_cfg, scaled, operation, distribution, diagonal_only)


class randomize_actuator_gains_ck(mdp.randomize_actuator_gains):
    """PD-gain DR with the scale ranges pulled toward 1.0 by c_k."""

    def __call__(self, env, env_ids, asset_cfg, stiffness_distribution_params=None,
                 damping_distribution_params=None, operation="abs", distribution="uniform"):
        ck = ck_value(env)
        scaled_k = (
            _ck_scale_range(stiffness_distribution_params, ck, 1.0) if stiffness_distribution_params is not None else None
        )
        scaled_d = (
            _ck_scale_range(damping_distribution_params, ck, 1.0) if damping_distribution_params is not None else None
        )
        return super().__call__(env, env_ids, asset_cfg, scaled_k, scaled_d, operation, distribution)


class randomize_joint_parameters_ck(mdp.randomize_joint_parameters):
    """Joint friction/armature DR with the add ranges pulled toward 0 by c_k."""

    def __call__(self, env, env_ids, asset_cfg, friction_distribution_params=None,
                 armature_distribution_params=None, lower_limit_distribution_params=None,
                 upper_limit_distribution_params=None, operation="abs", distribution="uniform"):
        ck = ck_value(env)
        scaled_f = (
            _ck_scale_range(friction_distribution_params, ck, 0.0) if friction_distribution_params is not None else None
        )
        scaled_a = (
            _ck_scale_range(armature_distribution_params, ck, 0.0) if armature_distribution_params is not None else None
        )
        return super().__call__(
            env, env_ids, asset_cfg, scaled_f, scaled_a,
            lower_limit_distribution_params, upper_limit_distribution_params, operation, distribution,
        )


# --- v5: reward-side anti-collapse package (plan versions/lizard/v5/PLAN.md) ---
# v3/v4 converged to a foot-pad creeping optimum: no reward pays for swinging,
# the exp tracking kernel lets |v_cmd| < 0.5 commands freeload at a standstill,
# belly contact is free, and r_fc shipped with an inverted sign. v5 closes the
# four holes at once (user decision 2026-09-03).


def track_lin_vel_xy_lin(env, command_name: str,
                         asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
                         min_speed: float = 0.1) -> torch.Tensor:
    """Normalized linear velocity tracking (Cheng et al. 2023, Eq. 2 form).

    r = min(<v_cmd_hat, v_yaw>, |v_cmd|) / max(|v_cmd|, min_speed) per env:
    standing = 0, reversal < 0, tracking = 1, overspeed capped at 1. The inner
    product is taken in the yaw-aligned gravity frame (same metric as the exp
    kernel it replaces -- roll/pitch must not inflate the projection).
    Shape: (num_envs,).
    """
    asset = env.scene[asset_cfg.name]
    vel_yaw = quat_apply_inverse(yaw_quat(asset.data.root_quat_w.torch), asset.data.root_lin_vel_w.torch)[:, :2]
    cmd = env.command_manager.get_command(command_name)[:, :2]
    speed = torch.linalg.norm(cmd, dim=-1)
    speed_c = torch.clamp(speed, min=min_speed)
    proj = (cmd * vel_yaw).sum(dim=-1) / speed_c
    return torch.clamp(proj, max=speed_c) / speed_c


def feet_slide_ck(env, sensor_cfg: SceneEntityCfg,
                  asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """r_slip (paper S7): penalize contact-foot sliding speed, scaled by c_k.

    Paper form: -c_k * sum over contact feet of |v_f|^2. Contact = net force
    norm > 1 N over the history window; v_f = tangential (xy) foot velocity.
    Local copy of the stock velocity-mdp ``feet_slide`` (which uses the
    unsquared norm): importing ``isaaclab_tasks.velocity.mdp`` from this
    module would risk the P001 pxr-poisoning import chain.
    Shape: (num_envs,).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    contacts = (
        sensor.data.net_forces_w_history.torch[:, :, sensor_cfg.body_ids, :].norm(dim=-1).max(dim=1)[0] > 1.0
    )
    asset = env.scene[asset_cfg.name]
    body_vel = asset.data.body_lin_vel_w.torch[:, asset_cfg.body_ids, :2]
    return torch.sum(body_vel.square().sum(dim=-1) * contacts, dim=1) * ck_value(env)


def undesired_contacts_ck(env, threshold: float, sensor_cfg: SceneEntityCfg) -> torch.Tensor:
    """``undesired_contacts`` penalty scaled by c_k (paper r_co semantics)."""
    return mdp.undesired_contacts(env, threshold, sensor_cfg) * ck_value(env)


def belly_contact_force(env, sensor_cfg: SceneEntityCfg, force_scale: float) -> torch.Tensor:
    """Continuous belly-contact penalty proportional to the net contact force.

    A flat-belly robot carries ~body weight through the base (72 kg x 9.81 ~
    706 N) -> penalty ~1.0 per step at weight 1.0 and ``force_scale`` = 706;
    a normal stance keeps the base off the ground -> 0. Deliberately NOT
    c_k-scaled: lying flat must never become free as the curriculum anneals.
    Shape: (num_envs,).
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    forces = sensor.data.net_forces_w.torch[:, sensor_cfg.body_ids, :]
    return torch.linalg.norm(forces, dim=-1).sum(dim=-1) / force_scale


# --- v5.3: SIR terrain curriculum (plan versions/lizard/v5/PLAN.md) ---
# Lee et al. 2020 (Miki's teacher paper, Algorithm S1 + Table S3), discrete
# adaptation on the pre-generated terrain grid. Particle = (terrain type,
# difficulty row); the grid is FROZEN (rows = difficulty particles via
# curriculum=True generation, columns = interchangeable instances) and the
# sampler only redistributes spawn traffic -- the single user-approved
# deviation from the paper, which regenerates terrain per particle draw.


@configclass
class SIRTerrainCurriculumCfg(CurriculumTermCfg):
    """Configuration for :class:`SpawnWeightSIRTerrainCurriculum`.

    Field values come from the version yaml ``v5.terrain_curriculum``
    section (SSOT); ``check_obs_layout.py`` asserts the wiring matches the
    yaml and that ``steps_per_iteration`` equals the runner's
    ``num_steps_per_env``.
    """

    command_name: str = "base_velocity"
    """Velocity command term providing each episode's commanded distance."""
    band: tuple[float, float] = (0.5, 0.9)
    """Target success-rate band: rows inside it keep sampling weight (Eq. 7)."""
    eval_every: int = 10
    """Policy iterations between SIR resamples (paper N_evaluate)."""
    n_traj_min: int = 6
    """Min episodes per particle row to update its weight (paper N_traj);
    rows with less traffic keep their previous weight."""
    p_transition: float = 0.8
    """Random-walk probability: the particle moves to an adjacent row."""
    p_replay: float = 0.05
    """Replay probability: the particle is redrawn from the history pool."""
    success_ratio: float = 0.5
    """Episode progress score = clamp(displacement / (ratio x commanded
    full-episode distance), 0, 1) x survival-time fraction; the band acts
    on the per-row MEAN score (stand-in for the paper's per-transition Tr)."""
    soft_edge: float = 0.05
    """Above-band edge softening width [score units]; the below-band weight
    is linear in the score (cold-start gradient), so no soft edge there."""
    steps_per_iteration: int = 24
    """Policy steps per PPO iteration; must equal runner num_steps_per_env."""


class SpawnWeightSIRTerrainCurriculum(ManagerTermBase):
    """Sequential-importance-resampling terrain curriculum on a fixed grid.

    Each sub-terrain type keeps ``num_rows`` particles (one per difficulty
    row). Envs belong to ONE type -- fixed by the importer's initial column
    assignment, so per-type env traffic follows the generator's column
    proportions, like the paper's fixed per-type trajectory share. On every
    env reset the env respawns on a row drawn uniformly from its type's
    particle set (column = random instance of the type). Every
    ``eval_every`` policy iterations the per-row mean progress scores
    measured since the last block set the weights (1 inside the band,
    soft edge above it, linear in the score below it -- the cold-start
    gradient), particles are resampled proportionally, random-walked to
    adjacent rows and partly redrawn from a replay pool.
    """

    cfg: SIRTerrainCurriculumCfg

    def __init__(self, cfg: SIRTerrainCurriculumCfg, env):
        super().__init__(cfg, env)
        terrain = env.scene.terrain
        gen_cfg = terrain.cfg.terrain_generator
        if gen_cfg is None or terrain.terrain_origins is None:
            raise ValueError("SpawnWeightSIRTerrainCurriculum needs terrain_type 'generator' with terrain origins.")
        origins = terrain.terrain_origins
        self._num_rows = int(origins.shape[0])
        num_cols = int(origins.shape[1])
        # column -> sub-terrain type, replicating TerrainGenerator's
        # curriculum split verbatim (normalized-proportion cumsum with the
        # +0.001 boundary epsilon, terrain_generator.py:243-247)
        proportions = [float(sub.proportion) for sub in gen_cfg.sub_terrains.values()]
        total = sum(proportions)
        cum = []
        acc = 0.0
        for p in proportions:
            acc += p / total
            cum.append(acc)
        sub_index = []
        for col in range(num_cols):
            frac = col / num_cols + 0.001
            sub_index.append(next(i for i, c in enumerate(cum) if frac < c))
        self._num_types = len(proportions)
        device = origins.device
        self._type_cols = [
            torch.tensor([c for c in range(num_cols) if sub_index[c] == t], dtype=torch.long, device=device)
            for t in range(self._num_types)
        ]
        col_type = torch.tensor(sub_index, dtype=torch.long, device=device)
        self._env_type = col_type[terrain.terrain_types.long()]
        # SIR state per type: particle rows (a multiset after resampling),
        # weights over rows, episode/score accumulators, replay history pool
        rows = torch.arange(self._num_rows, dtype=torch.long, device=device)
        self._particles = [rows.clone() for _ in range(self._num_types)]
        self._weights = [
            torch.full((self._num_rows,), 1.0 / self._num_rows, device=device) for _ in range(self._num_types)
        ]
        self._episodes = [torch.zeros(self._num_rows, device=device) for _ in range(self._num_types)]
        self._scores = [torch.zeros(self._num_rows, device=device) for _ in range(self._num_types)]
        # history starts at the uniform initial sample (paper line 1)
        self._history = [rows.clone() for _ in range(self._num_types)]
        self._next_eval_step = self.cfg.eval_every * self.cfg.steps_per_iteration

    def __call__(self, env, env_ids) -> torch.Tensor:
        """Book-keep ended episodes, resample on block boundaries, respawn.

        Runs from ``ManagerBasedRLEnv._reset_idx`` BEFORE ``scene.reset``
        (manager_based_rl_env.py:369 vs :371), so the final episode states
        (position, timeout flag, spawn origin) are still readable. The
        return value stays the scalar mean terrain level: the stock
        ``terrain_levels_vel`` logged the same key, and the train-probe
        reads ``Curriculum/terrain_levels``.
        """
        terrain = env.scene.terrain
        # 1) measure the episodes that just ended (episode_length_buf > 0
        #    skips the initial full reset, where no episode ran)
        real = env.episode_length_buf[env_ids] > 0
        if bool(real.any()):
            ids = env_ids[real]
            rows = terrain.terrain_levels[ids].long()
            types = self._env_type[ids]
            walked = torch.linalg.norm(
                env.scene["robot"].data.root_pos_w.torch[ids, :2] - terrain.env_origins[ids, :2], dim=1
            )
            commanded = torch.linalg.norm(
                env.command_manager.get_command(self.cfg.command_name)[ids, :2], dim=1
            ) * env.max_episode_length_s
            # v5.4 per-episode progress score in [0, 1]: displacement credit
            # (full at success_ratio x the commanded distance, linear below),
            # survival-time weighted. The survival factor cancels tumble
            # slides (rolling 3 m down the inverted stairs is displacement
            # without locomotion); the linear-below credit keeps early-fall
            # partial progress -- from-scratch policies fail everywhere and
            # a binary predicate would zero every weight, flattening the
            # cold start to uniform sampling with no difficulty gradient
            # (closer to the paper's per-transition Tr expectation, F3-7).
            progress = (walked / (self.cfg.success_ratio * commanded).clamp(min=1.0)).clamp(max=1.0)
            survival = (env.episode_length_buf[ids] / env.max_episode_length).clamp(max=1.0)
            score = progress * survival
            for t in torch.unique(types):
                t = int(t)
                mask = types == t
                self._episodes[t].index_add_(0, rows[mask], torch.ones(int(mask.sum()), device=rows.device))
                self._scores[t].index_add_(0, rows[mask], score[mask])
        # 2) block evaluation: every eval_every policy iterations
        if env.common_step_counter >= self._next_eval_step:
            self._resample()
            block = self.cfg.eval_every * self.cfg.steps_per_iteration
            self._next_eval_step = (env.common_step_counter // block + 1) * block
        # 3) respawn the resetting envs on their type's particle set
        types = self._env_type[env_ids]
        for t in torch.unique(types):
            t = int(t)
            ids = env_ids[types == t]
            particles = self._particles[t]
            rows = particles[torch.randint(particles.numel(), (ids.numel(),), device=particles.device)]
            cols = self._type_cols[t][torch.randint(self._type_cols[t].numel(), (ids.numel(),), device=particles.device)]
            terrain.terrain_levels[ids] = rows
            terrain.terrain_types[ids] = cols
            terrain.env_origins[ids] = terrain.terrain_origins[rows, cols]
        return terrain.terrain_levels.float().mean()

    def _measurement_prob(self, p_hat: torch.Tensor) -> torch.Tensor:
        """Measurement weight from the per-row mean progress score.

        Inside the band: 1. Above the band: soft edge to 0 (mastered rows
        fade out, paper semantics). BELOW the band: linear in the score
        instead of the paper's hard 0 -- a from-scratch policy scores near
        zero on every row, so the hard indicator would zero every weight
        and drop the whole cold start to the uniform fallback (no difficulty
        gradient). Linear-below keeps "less failed" rows (= easier terrain)
        measurably heavier, bootstrapping the band from underneath.
        """
        lo, hi = self.cfg.band
        eps = self.cfg.soft_edge
        low = (p_hat / lo).clamp(0.0, 1.0)
        up = ((hi + eps - p_hat) / eps).clamp(0.0, 1.0)
        return torch.minimum(low, up)

    def _resample(self) -> None:
        """One SIR block: weights from the band, resample, random walk, replay."""
        n = self._num_rows
        for t in range(self._num_types):
            episodes = self._episodes[t]
            p_hat = self._scores[t] / episodes.clamp(min=1.0)
            measured = self._measurement_prob(p_hat)
            # rows with insufficient traffic keep their previous weight
            weights = torch.where(episodes >= self.cfg.n_traj_min, measured, self._weights[t])
            total = float(weights.sum())
            if total > 0.0:
                weights = weights / total
            else:
                # whole type outside the band (e.g. flat once mastered):
                # re-explore uniformly, paper-style fallback
                weights = torch.full_like(weights, 1.0 / n)
            self._weights[t] = weights
            # resample n particles (with replacement) proportional to weight
            rows = torch.multinomial(weights, n, replacement=True)
            # transition model: random walk to an adjacent row, clamped
            move = torch.rand(n, device=rows.device) < self.cfg.p_transition
            direction = torch.randint(0, 2, (n,), device=rows.device) * 2 - 1
            rows = (rows + move * direction).clamp(0, n - 1)
            # replay memory: redraw a fraction uniformly from the history pool
            pool = self._history[t]
            replay = torch.rand(n, device=rows.device) < self.cfg.p_replay
            if bool(replay.any()):
                pick = torch.randint(pool.numel(), (int(replay.sum()),), device=rows.device)
                rows[replay] = pool[pick]
            self._particles[t] = rows
            self._history[t] = torch.cat([pool, rows])
            episodes.zero_()
            self._scores[t].zero_()
