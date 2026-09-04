# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Parkour line expert environments (Parkour in the Wild, position-task experts).

Independent snapshot (teacher discipline): this module inherits ONLY the
framework base class ``LocomotionVelocityRoughEnvCfg`` -- never any
lizard-family intermediate class -- so the parkour distillation pipeline
keeps a stable expert recipe while the lizard family stays the live
experiment bed (two prior incidents, see the task-creator skill pitfalls).
Robot, actions, terrain scaling, height scanner and domain-randomization
wiring are copied in here (frozen); numeric values come from
rl_exp/versions/lizard/parkour/parkour_params.yaml (line dev SSOT; frozen
per version at freeze time).

Deviations from the paper (declared, parkour/v1/PLAN.md section 2):
- expert perception = single fine height scan (stock 1.6 x 1.0 m @ 0.1 m =
  187 pts ~= the paper's fine Em at lizard scale); coarse Em + lidar scan
  are post-M1 upgrades if the climb expert starves for far field
- reward Table 2 wired with gate="none" (the 1_{t*<1} table is a FINE-TUNING
  table; from-scratch experts need the approach incentive, debt note H6)
- no base-contact termination (paper literal termination list: tilt +
  joint vel limit only; the sprawled body plan makes belly contact legal)
"""

from __future__ import annotations

import pathlib

import yaml

import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.envs import mdp
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.terrains import TerrainGeneratorCfg
from isaaclab.utils.configclass import configclass

from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    ActionsCfg,
    CommandsCfg,
    LocomotionVelocityRoughEnvCfg,
    ObservationsCfg,
    RewardsCfg,
    TerminationsCfg,
)
from isaaclab_tasks.utils import preset

from rl_exp.tasks import parkour_mdp
from rl_exp.tasks.play_utils import apply_play_wiring

if __name__ == "__main__":
    raise RuntimeError("This module is not meant to be executed directly.")

_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]


def _load_params() -> dict:
    """Load the parkour line dev-state parameter SSOT."""
    path = _RL_EXP_DIR / "versions" / "lizard" / "parkour" / "parkour_params.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# Climb expert terrain: stairs up + down in one expert (user decision
# 2026-09-04; M3 forks a dedicated Climb-down expert only if descending
# collapses). v3.4 calibration: step tops 0.55 m against the 0.52 m foot
# envelope, 0.7 m step width, 6 m center platform.
PARKOUR_TERRAINS_CLIMB = TerrainGeneratorCfg(
    size=(16.0, 16.0),
    border_width=25.0,
    num_rows=10,
    num_cols=10,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
    curriculum=True,
    sub_terrains={
        "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=0.5,
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "pyramid_stairs_inv": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=0.5,
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
    },
)

_LEG_JOINTS = [".*_haa_joint", ".*_hfe_joint", ".*_kfe_joint"]
_FOOT_JOINTS = [".*_foot_joint"]
_SPINE_JOINTS = ["rear_.*", "tail_.*", "neck.*_yaw_joint", "neck.*_pitch_joint"]


@configclass
class ParkourActionsCfg(ActionsCfg):
    """Joint actions split into legs + spine; spine locked at its rest pose.

    Copied from the teacher snapshot (a cross-file import would couple this
    line's recipe to the teacher file's evolution). Legs ordered before spine
    keeps the concatenated 26-dim action layout identical to the articulation
    tree order, so ``last_action`` keeps the family layout.
    """

    joint_pos = None
    joint_pos_legs = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=_LEG_JOINTS + _FOOT_JOINTS,
        scale=0.5,
        use_default_offset=True,
    )
    joint_pos_spine = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=_SPINE_JOINTS,
        scale=0.0,
        use_default_offset=True,
    )


@configclass
class ParkourCommandsCfg(CommandsCfg):
    """Position task (r*, psi*, t*): replaces the velocity command."""

    base_velocity = None
    position = parkour_mdp.PositionCommandCfg(
        class_type=parkour_mdp.PositionCommand,
        asset_name="robot",
        resampling_time_range=(18.0, 18.0),  # placeholder; overridden per command
    )


@configclass
class ParkourPolicyCfg(ObservationsCfg.PolicyCfg):
    """Expert policy obs: paper Table 3 expert column (single group).

    Inherits the stock proprio terms (noise stripped at runtime -- the expert
    is a privileged teacher) and the stock height scan (cleaned at runtime);
    appends the position command. Layout: 3+3+3+26+26+26+187+4 = 278.
    """

    velocity_commands = None
    position_commands = ObsTerm(
        func=mdp.generated_commands, params={"command_name": "position"}
    )


@configclass
class ParkourObservationsCfg(ObservationsCfg):
    """Observations for the parkour experts (single policy group)."""

    policy: ParkourPolicyCfg = ParkourPolicyCfg()


@configclass
class ParkourRewardsCfg(RewardsCfg):
    """Paper Table 2 (weights from parkour_params.yaml at runtime)."""

    # stock terms replaced by the paper table
    track_lin_vel_xy_exp = None
    track_ang_vel_z_exp = None
    lin_vel_z_l2 = None
    ang_vel_xy_l2 = None
    dof_torques_l2 = None
    dof_acc_l2 = None
    action_rate_l2 = None
    feet_air_time = None
    undesired_contacts = None
    flat_orientation_l2 = None
    dof_pos_limits = None

    # -- task --
    track_position = RewTerm(
        func=parkour_mdp.track_position, weight=10.0, params={"command_name": "position"}
    )
    track_heading = RewTerm(
        func=parkour_mdp.track_heading, weight=5.0, params={"command_name": "position"}
    )
    don_t_wait = RewTerm(func=parkour_mdp.don_t_wait, weight=-1.0)
    stand_at_target = RewTerm(
        func=parkour_mdp.stand_at_target, weight=-0.5, params={"command_name": "position"}
    )
    termination_penalty = RewTerm(
        func=parkour_mdp.termination_penalty,
        weight=-2.0e3,
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=_LEG_JOINTS + _FOOT_JOINTS),
            "gravity_z_limit": 0.707,
            "joint_vel_limit": 10.0,
        },
    )
    # -- regularization (paper Table 2) --
    joint_vel_l2 = RewTerm(func=mdp.joint_vel_l2, weight=-1.0e-3)
    # reconstructed PD torques: stock joint_torques_l2 reads applied_torque,
    # which is all-zero for implicit actuators (see parkour_mdp._pd_torque)
    joint_torques_l2 = RewTerm(func=parkour_mdp.joint_torques_l2_pd, weight=-1.0e-5)
    joint_vel_exceed_legs = RewTerm(
        func=parkour_mdp.joint_vel_exceed,
        weight=-1.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=_LEG_JOINTS), "limit": 10.0},
    )
    joint_vel_exceed_feet = RewTerm(
        func=parkour_mdp.joint_vel_exceed,
        weight=-1.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=_FOOT_JOINTS), "limit": 6.0},
    )
    torque_exceed_legs = RewTerm(
        func=parkour_mdp.torque_exceed,
        weight=-0.2,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=_LEG_JOINTS), "limit": 180.0},
    )
    torque_exceed_feet = RewTerm(
        func=parkour_mdp.torque_exceed,
        weight=-0.2,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=_FOOT_JOINTS), "limit": 70.0},
    )
    base_acc_l2 = RewTerm(func=parkour_mdp.base_acc_l2, weight=-1.0e-3)
    feet_acc_l1 = RewTerm(
        func=parkour_mdp.FeetAccPenalty,
        weight=-2.0e-3,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot")},
    )
    action_rate_paper = RewTerm(func=mdp.action_rate_l2, weight=-1.0e-2)
    feet_excess_force = RewTerm(
        func=parkour_mdp.feet_excess_force,
        weight=-1.0e-5,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"), "threshold": 700.0},
    )
    undesired_contacts_paper = RewTerm(
        func=mdp.undesired_contacts,
        weight=-1.0,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=[".*_hfe", ".*_kfe"]), "threshold": 1.0},
    )


@configclass
class ParkourTerminationsCfg(TerminationsCfg):
    """Paper termination list: tilt (alpha > 135 deg) + joint vel limit.

    No base-contact termination (paper literal; sprawled body plan).
    """

    base_contact = None
    tilt = DoneTerm(func=parkour_mdp.tilt_terminate, params={"gravity_z_limit": 0.707})
    joint_vel_limit_legs = DoneTerm(
        func=parkour_mdp.joint_vel_limit_terminate,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=_LEG_JOINTS), "limit": 10.0},
    )
    joint_vel_limit_feet = DoneTerm(
        func=parkour_mdp.joint_vel_limit_terminate,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=_FOOT_JOINTS), "limit": 6.0},
    )


@configclass
class ParkourClimbEnvCfg(LocomotionVelocityRoughEnvCfg):
    """Climb expert: position-task stairs (up + down), v3.4 terrain calibration.

    M1 scope: no terrain curriculum yet (spawn at the easiest row); the
    M2 milestone adds a position-task terrain-levels curriculum.
    """

    def __post_init__(self):
        super().__post_init__()
        params = _load_params()
        robot_params = params["robot"]
        actuator_params = params["actuators"]
        action_params = params["action"]
        sim_params = params["sim"]
        names_params = params["names"]
        dr_params = params["domain_randomization"]
        cmd_params = params["commands"]
        rw_params = params["rewards"]
        term_params = params["terminations"]
        feet_params = params["feet"]
        base_name = robot_params["base_body_name"]

        # --- robot (frozen snapshot; numeric values from the SSOT yaml) ---
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

        # --- actions: legs live, spine locked (scale 0 -> PD holds rest pose) ---
        self.actions = ParkourActionsCfg()
        self.actions.joint_pos_legs.scale = action_params["legs_scale"]
        self.actions.joint_pos_legs.use_default_offset = action_params["use_default_offset"]
        self.actions.joint_pos_spine.use_default_offset = action_params["use_default_offset"]

        # --- MDP cfg classes (structure; numbers below) ---
        self.commands = ParkourCommandsCfg()
        self.observations = ParkourObservationsCfg()
        self.rewards = ParkourRewardsCfg()
        self.terminations = ParkourTerminationsCfg()

        # --- timing from SSOT (before the scanner period so it uses final values) ---
        self.decimation = sim_params["decimation"]
        self.episode_length_s = sim_params["episode_length_s"]
        self.sim.dt = sim_params["dt"]
        self.sim.render_interval = self.decimation

        # --- terrain + spawn ---
        self.scene.terrain.terrain_type = "generator"
        self.scene.terrain.terrain_generator = PARKOUR_TERRAINS_CLIMB
        # replaced AFTER super(): the stock post-init clears the curriculum flag
        # when no terrain-levels term exists (known pit) -- reset it explicitly
        self.scene.terrain.terrain_generator.curriculum = True
        self.scene.terrain.max_init_terrain_level = 0  # M1: easiest row only

        # --- perceptive scanner: lizard prim path + policy-rate update ---
        # stock pattern is already 1.6 x 1.0 m @ 0.1 m = 187 pts (paper fine Em)
        self.scene.height_scanner.prim_path = "{ENV_REGEX_NS}/Robot/Geometry/base_link"
        self.scene.height_scanner.update_period = self.decimation * self.sim.dt

        # --- observations: the expert is a privileged teacher -- clean proprio ---
        self.observations.policy.base_lin_vel.noise = None
        self.observations.policy.base_ang_vel.noise = None
        self.observations.policy.projected_gravity.noise = None
        self.observations.policy.joint_pos.noise = None
        self.observations.policy.joint_vel.noise = None
        self.observations.policy.height_scan.noise = None

        # --- commands: numeric ranges from SSOT ---
        cmd = self.commands.position
        cmd.target_distance_range = tuple(cmd_params["target_distance_range"])
        cmd.heading_span = cmd_params["heading_span"]
        cmd.heading_jitter = cmd_params["heading_jitter"]
        cmd.speed_range = tuple(cmd_params["speed_range"])
        cmd.budget_range = tuple(cmd_params["budget_range"])
        cmd.pos_threshold = cmd_params["pos_threshold"]
        cmd.heading_threshold = cmd_params["heading_threshold"]
        cmd.tile_half_margin = cmd_params["tile_half_margin"]

        # --- rewards: weights + body names + gate from SSOT ---
        rw = self.rewards
        rw.track_position.weight = rw_params["track_position"]
        rw.track_position.params["gate"] = rw_params["track_gate"]
        rw.track_heading.weight = rw_params["track_heading"]
        rw.track_heading.params["gate"] = rw_params["track_gate"]
        rw.don_t_wait.weight = rw_params["don_t_wait"]
        rw.don_t_wait.params["speed_threshold"] = feet_params["don_t_wait_speed"]
        rw.stand_at_target.weight = rw_params["stand_at_target"]
        rw.termination_penalty.weight = rw_params["termination_penalty"]
        rw.termination_penalty.params["gravity_z_limit"] = term_params["tilt_gravity_z_limit"]
        rw.joint_vel_l2.weight = rw_params["joint_vel_l2"]
        rw.joint_torques_l2.weight = rw_params["joint_torques_l2"]
        rw.joint_vel_exceed_legs.weight = rw_params["joint_vel_exceed"]
        rw.joint_vel_exceed_feet.weight = rw_params["joint_vel_exceed"]
        rw.torque_exceed_legs.weight = rw_params["torque_exceed"]
        rw.torque_exceed_feet.weight = rw_params["torque_exceed"]
        rw.base_acc_l2.weight = rw_params["base_acc_l2"]
        rw.base_acc_l2.params["asset_cfg"] = SceneEntityCfg("robot", body_names=[base_name])
        rw.feet_acc_l1.weight = rw_params["feet_acc_l1"]
        rw.action_rate_paper.weight = rw_params["action_rate_l2"]
        rw.feet_excess_force.weight = rw_params["feet_excess_force"]
        rw.feet_excess_force.params["threshold"] = feet_params["force_threshold"]
        rw.feet_excess_force.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["foot_body_names"]
        )
        rw.feet_acc_l1.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["foot_body_names"]
        )
        rw.undesired_contacts_paper.weight = rw_params["undesired_contacts"]
        rw.undesired_contacts_paper.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["collision_body_names"]
        )

        # --- terminations: thresholds from SSOT ---
        self.terminations.tilt.params["gravity_z_limit"] = term_params["tilt_gravity_z_limit"]

        # --- domain randomization (frozen wiring; ranges from the SSOT yaml) ---
        self.events.physics_material.params["static_friction_range"] = tuple(dr_params["friction_static"])
        self.events.physics_material.params["dynamic_friction_range"] = tuple(dr_params["friction_dynamic"])
        self.events.physics_material.params["restitution_range"] = tuple(dr_params["friction_restitution"])
        self.events.physics_material.params["num_buckets"] = dr_params["friction_num_buckets"]
        self.events.add_base_mass.params["asset_cfg"] = SceneEntityCfg("robot", body_names=[base_name])
        self.events.add_base_mass.params["mass_distribution_params"] = tuple(dr_params["mass_scale"])
        self.events.add_base_mass.params["operation"] = "scale"
        self.events.add_base_mass.params["distribution"] = "log_uniform"
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
        self.events.base_external_force_torque.params["asset_cfg"] = SceneEntityCfg(
            "robot", body_names=[base_name]
        )
        self.events.base_external_force_torque.params["force_range"] = tuple(dr_params["external_force_range"])
        self.events.base_external_force_torque.params["torque_range"] = tuple(dr_params["external_torque_range"])
        self.events.push_robot.params["velocity_range"] = {
            axis: tuple(rng) for axis, rng in dr_params["push_velocity_range"].items()
        }
        self.events.reset_base.params["pose_range"]["z"] = tuple(dr_params["reset_height_range"])

        # --- curriculum: none in M1 (terrain rows stay ordered, spawn at row 0) ---
        self.curriculum.terrain_levels = None


@configclass
class ParkourClimbEnvCfg_PLAY(ParkourClimbEnvCfg):
    """Play variant: smaller terrain grid, curriculum off, randomization off."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see
        # play_utils; dependency-free so this snapshot keeps its discipline)
        apply_play_wiring(self)
