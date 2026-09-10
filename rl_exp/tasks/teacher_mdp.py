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
the constant-weight belly-contact force penalty. The v11 section adds the
joint particle terrain curriculum (plan versions/lizard/v11/PLAN.md):
ParticleVelocityCommand + JointSIRTerrainCurriculum.
"""

from __future__ import annotations

import math

import torch
import warp as wp

from isaaclab.envs import mdp
from isaaclab.envs.mdp.commands import UniformVelocityCommand, UniformVelocityCommandCfg
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
    """Episode success = survived to timeout AND walked >= ratio x the
    distance commanded over a full episode (terminal-episode stand-in for
    the paper's per-state-transition Tr)."""
    soft_edge: float = 0.05
    """Band-edge softening width [success-rate units]; keeps a gradient."""
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
    ``eval_every`` policy iterations the per-row success rates measured
    since the last block set the weights (1 inside the band, 0 outside,
    linear across the soft edges), particles are resampled proportionally,
    random-walked to adjacent rows and partly redrawn from a replay pool.
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
        # weights over rows, episode/success counters, replay history pool
        rows = torch.arange(self._num_rows, dtype=torch.long, device=device)
        self._particles = [rows.clone() for _ in range(self._num_types)]
        self._weights = [
            torch.full((self._num_rows,), 1.0 / self._num_rows, device=device) for _ in range(self._num_types)
        ]
        self._episodes = [torch.zeros(self._num_rows, device=device) for _ in range(self._num_types)]
        self._successes = [torch.zeros(self._num_rows, device=device) for _ in range(self._num_types)]
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
            succeeded = env.reset_time_outs[ids] & (walked >= self.cfg.success_ratio * commanded)
            for t in torch.unique(types):
                t = int(t)
                mask = types == t
                self._episodes[t].index_add_(0, rows[mask], torch.ones(int(mask.sum()), device=rows.device))
                self._successes[t].index_add_(0, rows[mask], succeeded[mask].float())
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
        """Band indicator with soft edges: 1 inside [lo, hi], 0 outside
        [lo - soft_edge, hi + soft_edge], linear in between."""
        lo, hi = self.cfg.band
        eps = self.cfg.soft_edge
        up = ((p_hat - (lo - eps)) / eps).clamp(0.0, 1.0)
        down = (((hi + eps) - p_hat) / eps).clamp(0.0, 1.0)
        return torch.minimum(up, down)

    def _resample(self) -> None:
        """One SIR block: weights from the band, resample, random walk, replay."""
        n = self._num_rows
        for t in range(self._num_types):
            episodes = self._episodes[t]
            successes = self._successes[t]
            p_hat = successes / episodes.clamp(min=1.0)
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
            successes.zero_()


# --- v11: joint particle terrain curriculum (plan versions/lizard/v11/PLAN.md) ---
# Lee et al. 2020 (arXiv:2010.11251) Alg. S1 generalized to a JOINT particle
# (terrain param combo, velocity bucket) over a frozen param-sampled grid
# (param_grid_terrain.py builds the grid; sub-terrain names encode the combo).
# Measurement returns to the paper's per-state-transition Tr (Eq. 2/3/7),
# replacing the v5.5 binary terminal proxy (family PLAN ledger #15, option a).
# Extensions beyond the paper (attribution, v11 PLAN section 9): velocity in
# the particle (the paper samples commands randomly and keeps them out), the
# frozen param grid, the band-empty directional fallback (cold start = all
# particles on the easiest combo with velocity buckets cycled -- no near-flat
# or low-speed bias; v11.1 PLAN erratum). The v5 SpawnWeightSIRTerrainCurriculum
# above stays FROZEN for v5-v10 reproducibility; this section is add-only.

JOINT_SIR_TERM = "joint_sir"
"""Curriculum term name for the joint SIR (v11.1).

``ParticleVelocityCommand._resample_command`` looks the term up by this
name, and the V11 env cfg wiring + ``check_obs_layout.py`` reference the
same constant, so a rename cannot silently decouple the particle velocity
from the curriculum (a stale name silently falls back to uniform commands).
"""


class ParticleVelocityCommand(UniformVelocityCommand):
    """Velocity command whose lin_vel_x comes from the joint SIR particle.

    The joint curriculum term sets :attr:`desired_vel` for the resetting envs
    at ITS compute hook -- ``ManagerBasedRLEnv._reset_idx`` calls the
    curriculum manager (:369) BEFORE the command manager reset (:394), so this
    term's :meth:`_resample_command` reads the fresh particle values; the
    ordering is load-bearing (v11 PLAN section 4.2). Where no curriculum term
    exists (PLAY variants) or the buffer is unset (-1), lin_vel_x falls back
    to the stock uniform range sample.

    Also accumulates the paper's per-step traversability label (Eq. 2):
    ``nu = 1`` iff the base velocity projected on the commanded direction
    exceeds ``v_pr_threshold`` [m/s] (signed projection -- reversal drift
    scores 0; overspeed is not penalized). The curriculum term reads
    ``_nu_sum``/``_step_count`` for the ended episodes at its hook, before
    :meth:`reset` zeroes them. Mid-episode resampling must stay disabled
    (``resampling_time_range=(1e9, 1e9)`` in the V11 wiring) so a whole
    episode keeps one particle pairing.
    """

    cfg: ParticleVelocityCommandCfg

    def __init__(self, cfg: ParticleVelocityCommandCfg, env):
        super().__init__(cfg, env)
        self._nu_sum = torch.zeros(self.num_envs, device=self.device)

    def _update_metrics(self):
        super()._update_metrics()
        cmd_xy = self.vel_command_b[:, :2]
        cmd_norm = torch.linalg.norm(cmd_xy, dim=-1)
        v_pr = (self.robot.data.root_lin_vel_b.torch[:, :2] * cmd_xy).sum(-1) / cmd_norm.clamp_min(1e-6)
        nu = (v_pr > self.cfg.v_pr_threshold) & (cmd_norm > 1e-6)
        self._nu_sum += nu.float()

    def reset(self, env_ids=None):
        extras = super().reset(env_ids)
        if env_ids is None:
            env_ids = slice(None)
        self._nu_sum[env_ids] = 0.0
        return extras

    def _resample_command(self, env_ids):
        super()._resample_command(env_ids)
        sir_cfg = getattr(self._env.curriculum_manager.cfg, JOINT_SIR_TERM, None)
        if sir_cfg is None:
            return
        desired = sir_cfg.func.desired_vel[env_ids]
        jitter = (torch.rand_like(desired) * 2.0 - 1.0) * self.cfg.command_jitter
        # sentinel is desired_vel's -1 init; 0.0 is a legal bucket (v11.1 --
        # the old ``> 0.0`` test would have swallowed a 0.0 bucket into the
        # uniform fallback)
        self.vel_command_b[env_ids, 0] = torch.where(
            desired >= 0.0, (desired + jitter).clamp_min(0.0), self.vel_command_b[env_ids, 0]
        )


@configclass
class ParticleVelocityCommandCfg(UniformVelocityCommandCfg):
    """Configuration for :class:`ParticleVelocityCommand`.

    Field values come from the version yaml ``v11.velocity_command`` section
    (SSOT).
    """

    class_type: type = ParticleVelocityCommand
    v_pr_threshold: float = 0.2
    """Per-step traversability label threshold [m/s] (paper Eq. 2)."""
    command_jitter: float = 0.1
    """Uniform jitter [m/s] around the particle's bucket value."""


@configclass
class JointSIRTerrainCurriculumCfg(CurriculumTermCfg):
    """Configuration for :class:`JointSIRTerrainCurriculum`.

    Field values come from the version yaml ``v11.terrain_curriculum``
    section (SSOT); ``check_obs_layout.py`` asserts the wiring matches the
    yaml and that ``steps_per_iteration`` equals the runner's
    ``num_steps_per_env``.
    """

    command_name: str = "base_velocity"
    """Velocity command term providing the Eq. 2 label sums."""
    band: tuple[float, float] = (0.5, 0.9)
    """Per-trajectory Tr band (paper Eq. 4/5)."""
    velocity_buckets: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
    """lin_vel_x bucket values [m/s] -- the joint particle's velocity axis."""
    particles_per_type: int = 16
    """Particles per terrain type (paper: 10; raised for the joint space)."""
    eval_every: int = 10
    """Policy iterations between SIR resamples (paper N_evaluate)."""
    n_traj_min: int = 6
    """Min trajectories per (combo, bucket) pair to update its weight."""
    p_transition: float = 0.8
    """Single-axis random-walk probability (one param axis or velocity)."""
    p_replay: float = 0.05
    """Replay-memory redraw probability."""
    maintain_mass: float = 0.1
    """Band-empty fallback share kept on learned pairs (v11 PLAN 4.1)."""
    steps_per_iteration: int = 24
    """Policy steps per PPO iteration; must equal runner num_steps_per_env."""


class JointSIRTerrainCurriculum(ManagerTermBase):
    """Joint SIR terrain curriculum over (param combo, velocity bucket) pairs.

    Grid wiring: ``param_grid_terrain.build_param_grid_terrain_cfg`` expands
    every parameter combination into one sub-terrain named
    ``<type>|<lvl>_<lvl>...`` (0-based levels, yaml axis order; ``flat`` has
    no axes). This term re-parses those names, replicates the
    TerrainGenerator column split (terrain_generator.py:243-247) at combo
    granularity, and owns, per terrain type: particles (pair indices),
    weights, episode / in-band / Tr counters and a replay history pool.

    Per reset: book-keep ended episodes (per-trajectory Tr = the command
    term's Eq. 2 label sum / step count), then respawn the resetting envs on
    a particle of their type -- terrain slot from the particle's combo,
    lin_vel_x from its velocity bucket (written to :attr:`desired_vel`,
    consumed by :class:`ParticleVelocityCommand`).

    Every ``eval_every`` policy iterations: weight = fraction of the pair's
    trajectories with per-trajectory Tr inside the band (paper Eq. 7),
    particles resampled proportionally, random-walked one axis (params or
    velocity), partly redrawn from the replay pool. Band-empty fallback
    routes by direction (v11 PLAN 4.1): mixed learned/unlearned concentrates
    on the frontier with a small maintenance share on learned pairs;
    all-learned and all-failed (cold start) stay uniform (paper semantics,
    and the v5.4 withdrawal precedent for cold start).

    The returned dict is logged per key as ``Curriculum/joint_sir/<key>``:
    ``frontier_max_v`` (mean over types of the fastest bucket on the current
    particles -- the progress metric replacing ``terrain_levels``), 
    ``particle_entropy`` (distribution health, 0 = collapse onto one pair),
    ``tr_mean`` (mean per-trajectory Tr over the last block).
    """

    cfg: JointSIRTerrainCurriculumCfg

    def __init__(self, cfg: JointSIRTerrainCurriculumCfg, env):
        super().__init__(cfg, env)
        terrain = env.scene.terrain
        gen_cfg = terrain.cfg.terrain_generator
        if gen_cfg is None or terrain.terrain_origins is None:
            raise ValueError("JointSIRTerrainCurriculum needs terrain_type 'generator' with terrain origins.")
        origins = terrain.terrain_origins
        self._num_rows = int(origins.shape[0])
        num_cols = int(origins.shape[1])
        device = origins.device
        # parse combo names -> (type, levels); column -> sub-terrain index,
        # replicating TerrainGenerator's curriculum split verbatim
        # (terrain_generator.py:243-247)
        names = list(gen_cfg.sub_terrains.keys())
        proportions = [float(sub.proportion) for sub in gen_cfg.sub_terrains.values()]
        total = sum(proportions)
        cum = []
        acc = 0.0
        for p in proportions:
            acc += p / total
            cum.append(acc)
        col_sub = []
        for col in range(num_cols):
            frac = col / num_cols + 0.001
            col_sub.append(next(i for i, c in enumerate(cum) if frac < c))
        col_sub = torch.tensor(col_sub, dtype=torch.long, device=device)
        # types in first-appearance order; per type: combo level tuples
        self._types: list[str] = []
        type_combos: dict[str, list[tuple[int, ...]]] = {}
        for name in names:
            type_name, _, lvl_str = name.partition("|")
            levels = tuple(int(x) for x in lvl_str.split("_")) if lvl_str else ()
            type_combos.setdefault(type_name, []).append(levels)
            if type_name not in self._types:
                self._types.append(type_name)
        self._velocity = torch.tensor(cfg.velocity_buckets, dtype=torch.float, device=device)
        n_v = len(cfg.velocity_buckets)
        self._n_v = n_v
        # per-type state: level counts, pair count, column slots, SIR state
        self._n_levels: list[list[int]] = []
        self._n_pairs: list[int] = []
        self._combo_cols: list[list[torch.Tensor]] = []
        self._particles: list[torch.Tensor] = []
        self._weights: list[torch.Tensor] = []
        self._episodes: list[torch.Tensor] = []
        self._in_band: list[torch.Tensor] = []
        self._tr_sum: list[torch.Tensor] = []
        self._history: list[torch.Tensor] = []
        n_part = cfg.particles_per_type
        for type_name in self._types:
            combos = type_combos[type_name]
            n_axes = len(combos[0])
            n_levels = [max(lv[a] for lv in combos) + 1 for a in range(n_axes)]
            if math.prod(n_levels) != len(combos):
                raise ValueError(
                    f"terrain type {type_name!r}: combos are not the full parameter "
                    "product (param_grid_terrain.py must enumerate itertools.product)"
                )
            combo_cols = []
            for i, name in enumerate(names):
                if name.partition("|")[0] != type_name:
                    continue
                cols = (col_sub == i).nonzero().flatten()
                if cols.numel() == 0:
                    raise ValueError(f"combo {name!r} owns no column; raise terrain_grid.num_cols")
                combo_cols.append(cols)
            n_pairs = len(combos) * n_v
            self._n_levels.append(n_levels)
            self._n_pairs.append(n_pairs)
            self._combo_cols.append(combo_cols)
            # cold start: all particles on the easiest combo (levels all 0),
            # velocity buckets cycled
            pairs = torch.arange(n_part, device=device) % n_v
            self._particles.append(pairs)
            self._weights.append(torch.full((n_pairs,), 1.0 / n_pairs, device=device))
            self._episodes.append(torch.zeros(n_pairs, device=device))
            self._in_band.append(torch.zeros(n_pairs, device=device))
            self._tr_sum.append(torch.zeros(n_pairs, device=device))
            self._history.append(pairs.clone())
        # env -> type follows the importer's initial column assignment, so
        # per-type env traffic follows the generator's type proportions (the
        # paper's fixed per-type trajectory share)
        col_type = torch.empty(num_cols, dtype=torch.long, device=device)
        for col in range(num_cols):
            col_type[col] = self._types.index(names[int(col_sub[col])].partition("|")[0])
        self._env_type = col_type[terrain.terrain_types.long()]
        self._env_pair = torch.full((env.num_envs,), -1, dtype=torch.long, device=device)
        self.desired_vel = torch.full((env.num_envs,), -1.0, device=device)
        self._next_eval_step = self.cfg.eval_every * self.cfg.steps_per_iteration
        self._tr_block_sum = 0.0
        self._tr_block_count = 0
        self._last_tr_mean = 0.0
        self._cmd_term = None

    def __call__(self, env, env_ids) -> dict[str, float]:
        """Book-keep ended episodes, resample on block boundaries, respawn."""
        terrain = env.scene.terrain
        # 1) measure the episodes that just ended (episode_length_buf > 0
        # skips the initial full reset, where no episode ran)
        real = env.episode_length_buf[env_ids] > 0
        if bool(real.any()):
            cmd = self._command_term(env)
            ids = env_ids[real]
            tr = cmd._nu_sum[ids] / cmd._step_count[ids].clamp_min(1.0)
            pairs = self._env_pair[ids]
            types = self._env_type[ids]
            lo, hi = self.cfg.band
            in_band = (tr >= lo) & (tr <= hi)
            self._tr_block_sum += float(tr.sum())
            self._tr_block_count += int(tr.numel())
            for t in torch.unique(types):
                t = int(t)
                mask = types == t
                ones = torch.ones(int(mask.sum()), device=tr.device)
                self._episodes[t].index_add_(0, pairs[mask], ones)
                self._in_band[t].index_add_(0, pairs[mask], in_band[mask].float())
                self._tr_sum[t].index_add_(0, pairs[mask], tr[mask])
        # 2) block evaluation: every eval_every policy iterations
        if env.common_step_counter >= self._next_eval_step:
            self._resample_all()
            block = self.cfg.eval_every * self.cfg.steps_per_iteration
            self._next_eval_step = (env.common_step_counter // block + 1) * block
            self._tr_block_sum = 0.0
            self._tr_block_count = 0
        # 3) respawn the resetting envs on their type's particle set
        types = self._env_type[env_ids]
        for t in torch.unique(types):
            ti = int(t)
            ids = env_ids[types == t]
            particles = self._particles[ti]
            pick = particles[torch.randint(particles.numel(), (ids.numel(),), device=particles.device)]
            combos = pick // self._n_v
            for c in torch.unique(combos):
                sel = ids[combos == c]
                cols = self._combo_cols[ti][int(c)]
                col = cols[torch.randint(cols.numel(), (sel.numel(),), device=cols.device)]
                row = torch.randint(self._num_rows, (sel.numel(),), device=cols.device)
                terrain.terrain_levels[sel] = row
                terrain.terrain_types[sel] = col
                terrain.env_origins[sel] = terrain.terrain_origins[row, col]
            self._env_pair[ids] = pick
            self.desired_vel[ids] = self._velocity[pick % self._n_v]
        return self._metrics()

    def _command_term(self, env):
        if self._cmd_term is None:
            term = env.command_manager.get_term(self.cfg.command_name)
            if not hasattr(term, "_nu_sum"):
                raise ValueError(
                    f"command term '{self.cfg.command_name}' has no Eq. 2 label sums; "
                    "JointSIRTerrainCurriculum needs ParticleVelocityCommand"
                )
            self._cmd_term = term
        return self._cmd_term

    def _resample_all(self) -> None:
        """One SIR block per type: Eq. 7 weights, resample, walk, replay.

        Pairs below n_traj_min keep their previous weight AND their counters,
        accumulating evidence across blocks until they settle (v11.1: the
        unconditional counter reset starved low-traffic pairs -- .1-proportion
        types average ~6.1 episodes/particle/block at the 4096-env run size,
        so their sparse pairs would otherwise sit at the uniform prior
        forever and the SIR would degrade to a random walk for them).
        """
        n_part = self.cfg.particles_per_type
        for ti in range(len(self._types)):
            episodes = self._episodes[ti]
            in_band = self._in_band[ti]
            tr_sum = self._tr_sum[ti]
            settled = episodes >= self.cfg.n_traj_min
            measured = in_band / episodes.clamp_min(1.0)
            # unsettled pairs keep their previous weight (and their counters)
            weights = torch.where(settled, measured, self._weights[ti])
            total = float(weights.sum())
            if total <= 0.0:
                weights = self._fallback_weights(ti, episodes, tr_sum)
                total = float(weights.sum())
            weights = weights / total
            self._weights[ti] = weights
            particles = torch.multinomial(weights, n_part, replacement=True)
            particles = self._walk(ti, particles)
            pool = self._history[ti]
            replay = torch.rand(n_part, device=particles.device) < self.cfg.p_replay
            if bool(replay.any()):
                pick = torch.randint(pool.numel(), (int(replay.sum()),), device=particles.device)
                particles[replay] = pool[pick]
            self._particles[ti] = particles
            self._history[ti] = torch.cat([pool, particles])
            episodes[settled] = 0
            in_band[settled] = 0
            tr_sum[settled] = 0

    def _fallback_weights(self, ti: int, episodes: torch.Tensor, tr_sum: torch.Tensor) -> torch.Tensor:
        """Band-empty routing by direction (v11 PLAN 4.1).

        Mixed learned/unlearned: concentrate the mass on the frontier (unlearned
        pairs one axis-step from learned ones) with a small maintenance share
        on the learned pairs. All-learned and all-failed (cold start) stay
        uniform -- the paper's semantics, and the v5.4 withdrawal precedent
        (no home-made cold-start criterion).
        """
        n_pairs = self._n_pairs[ti]
        uniform = torch.full((n_pairs,), 1.0 / n_pairs, device=episodes.device)
        measured = episodes >= self.cfg.n_traj_min
        if not bool(measured.any()):
            return uniform
        _, hi = self.cfg.band
        learned = measured & (tr_sum / episodes.clamp_min(1.0) >= hi)
        if bool(learned.all()) or not bool(learned.any()):
            return uniform
        frontier = torch.zeros_like(learned)
        for pair in learned.nonzero().flatten().tolist():
            for nb in self._neighbors(ti, pair):
                frontier[nb] = True
        frontier &= ~learned
        if not bool(frontier.any()):
            frontier = ~learned
        weights = torch.zeros(n_pairs, device=episodes.device)
        weights[learned] = self.cfg.maintain_mass / int(learned.sum())
        weights[frontier] += (1.0 - self.cfg.maintain_mass) / int(frontier.sum())
        return weights

    def _neighbors(self, ti: int, pair: int) -> list[int]:
        """Pair indices one axis-step away (single param axis or velocity)."""
        n_v = self._n_v
        n_levels = self._n_levels[ti]
        c, v = divmod(pair, n_v)
        levels = self._decode_levels(ti, c)
        out = []
        for a, lvl in enumerate(levels):
            for d in (-1, 1):
                nl = list(levels)
                nl[a] = max(0, min(n_levels[a] - 1, lvl + d))
                if nl != list(levels):
                    out.append(self._encode_combo(ti, nl) * n_v + v)
        if v > 0:
            out.append(c * n_v + v - 1)
        if v < n_v - 1:
            out.append(c * n_v + v + 1)
        return out

    def _walk(self, ti: int, particles: torch.Tensor) -> torch.Tensor:
        """Random walk: one axis (params or velocity) +-1 level, clamped."""
        n_levels = self._n_levels[ti]
        n_axes = len(n_levels)
        n_v = self._n_v
        n = particles.numel()
        move = torch.rand(n, device=particles.device) < self.cfg.p_transition
        axis = torch.randint(0, n_axes + 1, (n,), device=particles.device)
        direction = torch.randint(0, 2, (n,), device=particles.device) * 2 - 1
        out = particles.clone()
        for i in range(n):
            if not bool(move[i]):
                continue
            c, v = divmod(int(particles[i]), n_v)
            if int(axis[i]) == n_axes:
                v = max(0, min(n_v - 1, v + int(direction[i])))
            else:
                levels = self._decode_levels(ti, c)
                a = int(axis[i])
                levels[a] = max(0, min(n_levels[a] - 1, levels[a] + int(direction[i])))
                c = self._encode_combo(ti, levels)
            out[i] = c * n_v + v
        return out

    def _decode_levels(self, ti: int, combo: int) -> list[int]:
        """Combo index -> axis levels (mixed radix, last axis fastest)."""
        levels = []
        for n in reversed(self._n_levels[ti]):
            levels.append(combo % n)
            combo //= n
        return list(reversed(levels))

    def _encode_combo(self, ti: int, levels: list[int]) -> int:
        """Axis levels -> combo index (mixed radix, last axis fastest)."""
        combo = 0
        for lvl, n in zip(levels, self._n_levels[ti]):
            combo = combo * n + lvl
        return combo

    def _metrics(self) -> dict[str, float]:
        n_part = self.cfg.particles_per_type
        fmv = []
        ent = []
        for ti in range(len(self._types)):
            vs = self._velocity[self._particles[ti] % self._n_v]
            fmv.append(float(vs.max()) if vs.numel() else 0.0)
            hist = torch.bincount(self._particles[ti], minlength=self._n_pairs[ti]).float()
            p = hist / hist.sum().clamp_min(1.0)
            nz = p[p > 0]
            ent.append(float(-(nz * nz.log()).sum()) / max(math.log(n_part), 1e-9))
        if self._tr_block_count > 0:
            self._last_tr_mean = self._tr_block_sum / self._tr_block_count
        return {
            "frontier_max_v": sum(fmv) / len(fmv),
            "particle_entropy": sum(ent) / len(ent),
            "tr_mean": self._last_tr_mean,
        }
