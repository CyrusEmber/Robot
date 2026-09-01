# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard (26-joint) flat-ground velocity tracking.

Built directly on :class:`LocomotionVelocityRoughEnvCfg` (no intermediate robot
base class). Robot geometry comes from rl_exp/versions/lizard/lizard.urdf (SSOT, Blender
generated: 16 leg joints HAA/HFE/KFE/FOOT x4 + 10 spine joints), control
parameters from rl_exp/versions/lizard/lizard_params.yaml (SSOT).

Domain randomization (mass/CoM/inertia/friction/actuator gains/joint
parameters/external forces/pushes) is configured in the SSOT yaml and wired
here so the policy cannot memorize a single dynamics realization.
"""

import pathlib

import yaml

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import LocomotionVelocityRoughEnvCfg
from isaaclab_tasks.utils import preset

from rl_exp.tasks.play_utils import apply_play_wiring

# this file lives at rl_exp/tasks/lizard_env_cfg.py -> exp root is parents[1]
_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]

# family namespace layer: frozen recipes live under versions/<family>/<version>/
# (teacher_env_cfg.py keeps its own copy of this constant -- loud failure on
# drift: a wrong path raises at cfg construction, never silently trains stale)
_VERSION_FAMILY = "lizard"


def _load_params(version: str | None = None) -> dict:
    """Load the lizard SSOT yaml.

    Args:
        version: Version name (e.g. "v0") to read the FROZEN copy under
            ``rl_exp/versions/<family>/<version>/lizard_params.yaml``, or None to
            read the live dev yaml (``versions/<family>/lizard_params.yaml``). Versioned runs must always pass their own
            version so dev-yaml edits can never drift a frozen recipe.
    """
    if version is None:
        path = _RL_EXP_DIR / "versions" / _VERSION_FAMILY / "lizard_params.yaml"
    else:
        path = _RL_EXP_DIR / "versions" / _VERSION_FAMILY / version / "lizard_params.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@configclass
class LizardFlatEnvCfg(LocomotionVelocityRoughEnvCfg):
    """26-joint lizard on flat ground, full domain randomization."""

    # param generation: None = live dev yaml (family experiments);
    # a frozen version ("v0", "v1", ...) reads versions/<family>/<version>/lizard_params.yaml
    params_version = None

    def __post_init__(self):
        super().__post_init__()
        params = _load_params(self.params_version)
        robot_params = params["robot"]
        actuator_params = params["actuators"]
        action_params = params["action"]
        sim_params = params["sim"]
        names_params = params["names"]
        dr_params = params["domain_randomization"]

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

        base_name = robot_params["base_body_name"]
        self.scene.robot = ArticulationCfg(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=sim_utils.UsdFileCfg(
                usd_path=str(_RL_EXP_DIR / robot_params["usd_path"]),
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

        # action space from SSOT (single joint term; the curriculum variant splits it)
        self.actions.joint_pos.scale = action_params["legs_scale"]
        self.actions.joint_pos.use_default_offset = action_params["use_default_offset"]

        # flat task: no terrain, no height scan, no terrain curriculum
        self.scene.terrain.terrain_type = "plane"
        self.scene.terrain.terrain_generator = None
        self.scene.height_scanner = None
        self.observations.policy.height_scan = None
        self.curriculum.terrain_levels = None

        # timing from SSOT
        self.decimation = sim_params["decimation"]
        self.episode_length_s = sim_params["episode_length_s"]
        self.sim.dt = sim_params["dt"]
        self.sim.render_interval = self.decimation

        # reward body-name patterns from SSOT
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

        # command ranges from SSOT
        self.commands.base_velocity.ranges.lin_vel_x = tuple(params["commands"]["lin_vel_x"])
        self.commands.base_velocity.ranges.lin_vel_y = tuple(params["commands"]["lin_vel_y"])
        self.commands.base_velocity.ranges.ang_vel_z = tuple(params["commands"]["ang_vel_z"])

        # --- domain randomization (ranges live in the SSOT yaml) ---
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


@configclass
class LizardFlatEnvCfg_PLAY(LizardFlatEnvCfg):
    """Play variant: no randomization, no pushes, fixed full command ranges."""

    def __post_init__(self):
        super().__post_init__()
        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)
