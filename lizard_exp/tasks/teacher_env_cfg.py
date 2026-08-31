# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard teacher environment (Miki et al. 2022, two-phase pipeline, Phase 1).

Independent frozen snapshot of the lizard setup: this file inherits ONLY the
framework base class ``LocomotionVelocityRoughEnvCfg`` -- never any
lizard-family intermediate class -- so the Phase 2 distillation keeps a stable
teacher recipe while the lizard family keeps evolving as the live experiment
bed (plan §4.1). Robot, terrain scaling, height scanner and the
domain-randomization wiring are copied in here (frozen); numeric values still
come from lizard_exp/lizard_params.yaml (single source of truth).

The teacher ACTOR receives privileged simulation ground truth (Miki et al.
2022): clean height scan, true base velocities, foot contact flags, swing
durations and per-body mass on top of the noisy proprioceptive observations.
Rewards stay at the baseline (no incentive patches): if the teacher still
collapses under privilege, the incentive-escape-hatch hypothesis is confirmed
and the parked reward fixes get re-applied (plan §2.3).
"""

import pathlib

import yaml

import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import RayCasterCfg, patterns
from isaaclab.terrains import TerrainGeneratorCfg
from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    ActionsCfg,
    LocomotionVelocityRoughEnvCfg,
)
from isaaclab_tasks.utils import preset

from lizard_exp.tasks import teacher_mdp
from lizard_exp.tasks.play_utils import apply_play_wiring

# this file lives at lizard_exp/tasks/teacher_env_cfg.py -> exp root is parents[1]
_LIZARD_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]



def _load_params(version: str) -> dict:
    """Load the frozen lizard_params.yaml copy of ``version`` (never the dev yaml)."""
    path = _LIZARD_EXP_DIR / "versions" / version / "lizard_params.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# frozen snapshot of the lizard-scaled rough terrains (16 m tiles, ~2x stock
# obstacle sizes for the 3.6 m body). Deliberately NOT imported from the lizard
# family: family retunes must not silently change the teacher recipe.
# curriculum=True restores stock rough semantics (rows ordered easy -> hard).
# The family loses this flag by replacing the generator after the base
# __post_init__ has already set it on the stock cfg object.
TEACHER_TERRAINS_CFG = TerrainGeneratorCfg(
    size=(16.0, 16.0),
    border_width=25.0,
    num_rows=10,
    num_cols=20,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
    curriculum=True,
    sub_terrains={
        "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=0.2,
            step_height_range=(0.08, 0.35),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "pyramid_stairs_inv": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=0.2,
            step_height_range=(0.08, 0.35),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "boxes": terrain_gen.MeshRandomGridTerrainCfg(
            proportion=0.2, grid_width=0.9, grid_height_range=(0.08, 0.3), platform_width=4.0
        ),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=0.2, noise_range=(0.04, 0.2), noise_step=0.04, border_width=0.5
        ),
        "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.4), platform_width=4.0, border_width=0.5
        ),
        "hf_pyramid_slope_inv": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.4), platform_width=4.0, border_width=0.5
        ),
    },
)


@configclass
class TeacherActionsCfg(ActionsCfg):
    """Joint actions split into legs + spine; spine locked at its rest pose.

    Legs ordered before spine keeps the concatenated 26-dim action layout
    identical to the articulation tree order, so the observation terms
    (incl. ``last_action``) keep the family layout and Phase 2 can unlock the
    spine without changing the observation structure.
    """

    joint_pos = None
    joint_pos_legs = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*_haa_joint", ".*_hfe_joint", ".*_kfe_joint", ".*_foot_joint"],
        scale=0.5,
        use_default_offset=True,
    )
    joint_pos_spine = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=["rear_.*", "tail_.*", "neck.*_yaw_joint", "neck.*_pitch_joint"],
        scale=0.0,
        use_default_offset=True,
    )


# Per-version privileged-term spec: the SINGLE source of truth for what
# separates two teacher recipes at code level. Baseline privileged terms
# (contact flags, air time, per-body mass, true velocities) belong to every
# version and are wired unconditionally; only the incremental terms live
# here. DISCIPLINE: a term's implementation is frozen once shipped -- newer
# versions may only ADD terms, and old recipes strip the additions again.
TEACHER_PRIVILEGED_SPEC: dict[str, set[str]] = {
    "v1": set(),
    "v2": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
}


@configclass
class LizardRoughTeacherEnvCfg(LocomotionVelocityRoughEnvCfg):
    """Teacher: perceptive + privileged actor, baseline rewards (Lizard-Rough-v2).

    Privileged obs per Miki et al. 2022 table + two legacy extras (true base
    velocity, per-body mass); full layout table in FAMILY.md. Obs dim 308.

    ``params_version`` is a plain class attribute (NOT a configclass field, so
    it is never deep-copied): the latest recipe lives here, and per-version
    subclasses below override it for working-tree reproducibility -- running
    an old task id must always rebuild the old recipe, never silently pick
    up code drift from newer versions. Which incremental terms a version
    includes is governed by ``TEACHER_PRIVILEGED_SPEC`` above.
    """

    # v2 = latest (paper-aligned privileged obs); see versions/v2/NOTES.md
    params_version = "v2"

    def __post_init__(self):
        super().__post_init__()
        if self.params_version not in TEACHER_PRIVILEGED_SPEC:
            raise ValueError(
                f"Unknown teacher params_version '{self.params_version}';"
                f" known: {sorted(TEACHER_PRIVILEGED_SPEC)}"
            )
        params = _load_params(self.params_version)
        robot_params = params["robot"]
        actuator_params = params["actuators"]
        action_params = params["action"]
        sim_params = params["sim"]
        names_params = params["names"]
        dr_params = params["domain_randomization"]
        base_name = robot_params["base_body_name"]

        # --- robot (frozen snapshot; numeric values from the SSOT yaml) ---
        # implicit PD on purpose: the drive runs inside the physics solver at
        # the physics rate (200 Hz). Sampled 50 Hz explicit torque PD is
        # unstable for the low-inertia spine joints.
        actuators = {
            group_name: ImplicitActuatorCfg(
                joint_names_expr=group_params["joint_patterns"],
                stiffness=group_params["stiffness"],
                damping=group_params["damping"],
                effort_limit=group_params["effort_limit"],
                velocity_limit=group_params["velocity_limit"],
                armature=group_params["armature"],
            )
            for group_name, group_params in actuator_params.items()
        }
        self.scene.robot = ArticulationCfg(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=sim_utils.UsdFileCfg(
                usd_path=str(_LIZARD_EXP_DIR / robot_params["usd_path"]),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    disable_gravity=False,
                    retain_accelerations=False,
                    linear_damping=0.0,
                    angular_damping=0.0,
                    max_linear_velocity=1000.0,
                    max_angular_velocity=1000.0,
                    max_depenetration_velocity=1.0,
                ),
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=False,
                    solver_position_iteration_count=8,
                    solver_velocity_iteration_count=0,
                ),
            ),
            init_state=ArticulationCfg.InitialStateCfg(
                pos=(0.0, 0.0, robot_params["base_init_height"]),
                joint_pos=params["default_joint_pos"],
            ),
            actuators=actuators,
            soft_joint_pos_limit_factor=0.95,
        )

        # --- actions: legs live, spine locked (scale 0 -> PD holds rest pose) ---
        self.actions = TeacherActionsCfg()
        self.actions.joint_pos_legs.scale = action_params["legs_scale"]
        self.actions.joint_pos_legs.use_default_offset = action_params["use_default_offset"]
        self.actions.joint_pos_spine.use_default_offset = action_params["use_default_offset"]

        # --- timing from SSOT (before the scanner period so it uses final values) ---
        self.decimation = sim_params["decimation"]
        self.episode_length_s = sim_params["episode_length_s"]
        self.sim.dt = sim_params["dt"]
        self.sim.render_interval = self.decimation

        # --- terrain + perceptive scanner (frozen snapshot) ---
        self.scene.terrain.terrain_type = "generator"
        self.scene.terrain.terrain_generator = TEACHER_TERRAINS_CFG
        self.scene.terrain.max_init_terrain_level = 5
        # bodies live under the importer's Geometry scope (flattened USD:
        # /Robot/Geometry/base_link); the base task assumes /Robot/base.
        # Pattern covers the full leg span (feet at |x| up to ~1.4 m), 0.2 m
        # resolution -> 15x9 = 135 points.
        self.scene.height_scanner = RayCasterCfg(
            prim_path="{ENV_REGEX_NS}/Robot/Geometry/base_link",
            offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
            ray_alignment="yaw",
            pattern_cfg=patterns.GridPatternCfg(resolution=0.2, size=[2.8, 1.6]),
            debug_vis=False,
            mesh_prim_paths=["/World/ground"],
        )
        # scanner at the policy rate: same cadence the base class gives the
        # stock scanner (the family replacement accidentally leaves 0 -> 200 Hz)
        self.scene.height_scanner.update_period = self.decimation * self.sim.dt

        # --- rewards / terminations: lizard body-name patterns from SSOT ---
        self.rewards.feet_air_time.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["foot_body_names"]
        )
        self.rewards.undesired_contacts.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["undesired_contact_body_names"]
        )
        # the base task assumes the anymal base body is called "base" (termination term)
        self.terminations.base_contact.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=[base_name]
        )

        # --- commands: paper-faithful local override (plan §4.3); the yaml
        # keeps the wide lizard ambition ranges for the family tasks ---
        self.commands.base_velocity.ranges.lin_vel_x = (-1.0, 1.0)
        self.commands.base_velocity.ranges.lin_vel_y = (-0.5, 0.5)
        self.commands.base_velocity.ranges.ang_vel_z = (-1.0, 1.0)

        # --- domain randomization (frozen wiring; ranges from the SSOT yaml) ---
        # ground friction (startup, bucketed materials)
        self.events.physics_material.params["static_friction_range"] = tuple(dr_params["friction_static"])
        self.events.physics_material.params["dynamic_friction_range"] = tuple(dr_params["friction_dynamic"])
        self.events.physics_material.params["restitution_range"] = tuple(dr_params["friction_restitution"])
        self.events.physics_material.params["num_buckets"] = dr_params["friction_num_buckets"]
        # base mass: log-uniform relative scale (geometric mean 1.0)
        self.events.add_base_mass.params["asset_cfg"] = SceneEntityCfg("robot", body_names=[base_name])
        self.events.add_base_mass.params["mass_distribution_params"] = tuple(dr_params["mass_scale"])
        self.events.add_base_mass.params["operation"] = "scale"
        self.events.add_base_mass.params["distribution"] = "log_uniform"
        # per-limb mass: wider relative range on every non-base body
        self.events.randomize_limb_mass = EventTerm(
            func=mdp.randomize_rigid_body_mass,
            mode="startup",
            params={
                "asset_cfg": SceneEntityCfg("robot", body_names=dr_params["limb_body_names"]),
                "mass_distribution_params": tuple(dr_params["mass_scale_limbs"]),
                "operation": "scale",
                "distribution": "log_uniform",
            },
        )
        # base CoM offset (same preset wrapping as the base cfg: off on newton)
        self.events.base_com = preset(
            default=EventTerm(
                func=mdp.randomize_rigid_body_com,
                mode="startup",
                params={
                    "asset_cfg": SceneEntityCfg("robot", body_names=[base_name]),
                    "com_range": {axis: tuple(rng) for axis, rng in dr_params["com_range"].items()},
                },
            ),
            newton_mjwarp=None,
        )
        # body inertia: relative scale on the diagonal terms
        self.events.randomize_inertia = EventTerm(
            func=mdp.randomize_rigid_body_inertia,
            mode="startup",
            params={
                "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
                "inertia_distribution_params": tuple(dr_params["inertia_scale"]),
                "operation": "scale",
                "distribution": "log_uniform",
                "diagonal_only": True,
            },
        )
        # actuator PD gains: relative scale (implicit actuators -> startup only)
        self.events.randomize_actuator_gains = EventTerm(
            func=mdp.randomize_actuator_gains,
            mode="startup",
            params={
                "asset_cfg": SceneEntityCfg("robot"),
                "stiffness_distribution_params": tuple(dr_params["stiffness_scale"]),
                "damping_distribution_params": tuple(dr_params["damping_scale"]),
                "operation": "scale",
                "distribution": "log_uniform",
            },
        )
        # joint friction + armature: absolute add (startup only, CPU tensors)
        self.events.randomize_joint_params = EventTerm(
            func=mdp.randomize_joint_parameters,
            mode="startup",
            params={
                "asset_cfg": SceneEntityCfg("robot"),
                "friction_distribution_params": tuple(dr_params["joint_friction_add"]),
                "armature_distribution_params": tuple(dr_params["joint_armature_add"]),
                "operation": "add",
                "distribution": "uniform",
            },
        )
        # persistent external wrench + velocity pushes (72 kg scale)
        self.events.base_external_force_torque.params["asset_cfg"] = SceneEntityCfg(
            "robot", body_names=[base_name]
        )
        self.events.base_external_force_torque.params["force_range"] = tuple(dr_params["external_force_range"])
        self.events.base_external_force_torque.params["torque_range"] = tuple(dr_params["external_torque_range"])
        self.events.push_robot.params["velocity_range"] = {
            axis: tuple(rng) for axis, rng in dr_params["push_velocity_range"].items()
        }
        # spawn height jitter: survive imperfect initialization drops
        self.events.reset_base.params["pose_range"]["z"] = tuple(dr_params["reset_height_range"])

        # --- privileged observations (plan §4.2): ground truth for the ACTOR ---
        # privilege 1: clean height scan (no observation noise, clip kept)
        self.observations.policy.height_scan = ObsTerm(
            func=mdp.height_scan,
            params={"sensor_cfg": SceneEntityCfg("height_scanner")},
            clip=(-1.0, 1.0),
        )
        # privilege 2: true base velocities (the proprioceptive terms carry
        # sensor noise; these are the ground-truth counterparts)
        self.observations.policy.base_lin_vel_true = ObsTerm(func=mdp.base_lin_vel)
        self.observations.policy.base_ang_vel_true = ObsTerm(func=mdp.base_ang_vel)
        # privilege 3: foot contact flags, swing durations, per-body mass
        self.observations.policy.foot_contact = ObsTerm(
            func=teacher_mdp.foot_contact_bools,
            params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"), "threshold": 1.0},
        )
        self.observations.policy.feet_air_time = ObsTerm(
            func=teacher_mdp.feet_air_time,
            params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot")},
        )
        self.observations.policy.body_mass = ObsTerm(
            func=teacher_mdp.body_mass_truth,
            params={"asset_cfg": SceneEntityCfg("robot", body_names=".*")},
        )
        # privilege 4 (v2, Miki et al. 2022 table completion): contact force
        # vectors, contact normals, per-foot friction, thigh/shank contact
        # flags, persistent external wrench -- see FAMILY.md obs layout table
        self.observations.policy.foot_contact_forces = ObsTerm(
            func=teacher_mdp.foot_contact_forces,
            params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot")},
        )
        self.observations.policy.foot_contact_normals = ObsTerm(
            func=teacher_mdp.FootContactNormalsTerm,
            params={"mesh_prim_path": "/World/ground", "max_distance": 2.0, "start_offset": 0.5},
        )
        self.observations.policy.foot_friction = ObsTerm(
            func=teacher_mdp.foot_friction_truth,
            params={"asset_cfg": SceneEntityCfg("robot", body_names=".*_foot")},
        )
        self.observations.policy.thigh_shank_contacts = ObsTerm(
            func=teacher_mdp.thigh_shank_contacts,
            params={
                "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[".*_hfe", ".*_kfe"]),
                "threshold": 1.0,
            },
        )
        self.observations.policy.base_external_wrench = ObsTerm(
            func=teacher_mdp.base_external_wrench,
            params={"asset_cfg": SceneEntityCfg("robot", body_names=[base_name])},
        )
        # strip the incremental terms this recipe's version does not include
        # (TEACHER_PRIVILEGED_SPEC governs; keeps old recipes reproducible)
        allowed = TEACHER_PRIVILEGED_SPEC[self.params_version]
        every = set().union(*TEACHER_PRIVILEGED_SPEC.values())
        for term_name in sorted(every - allowed):
            setattr(self.observations.policy, term_name, None)


@configclass
class LizardRoughTeacherEnvCfg_PLAY(LizardRoughTeacherEnvCfg):
    """Play variant: smaller terrain grid, curriculum off, randomization off."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils;
        # play_utils is deliberately dependency-free so the teacher snapshot keeps
        # its zero-family-import discipline)
        apply_play_wiring(self)


@configclass
class LizardRoughTeacherEnvCfg_V1(LizardRoughTeacherEnvCfg):
    """v1 recipe, reproducible from the working tree (obs 266).

    The one-line override is the whole point of the spec structure:
    TEACHER_PRIVILEGED_SPEC["v1"] = set() makes the base class strip every
    incremental term, so this class needs no hand-maintained stripping list.
    """

    params_version = "v1"


@configclass
class LizardRoughTeacherEnvCfg_V1_PLAY(LizardRoughTeacherEnvCfg_V1):
    """v1 play variant: obs 266, no randomization, curriculum off."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)
