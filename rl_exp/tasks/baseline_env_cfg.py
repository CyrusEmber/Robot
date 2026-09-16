# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Flat-ground walking baseline: fixed low-speed forward command, nothing else.

Built directly on :class:`LocomotionVelocityRoughEnvCfg` and on framework MDP terms
only. It imports no other recipe module -- not the family base, not the teacher snapshot,
not ``teacher_mdp`` -- so "the baseline recipe" is a file you can read end to end instead
of the residue of six generations of inheritance. The two kernels it needs from the
shared, actively-mutated ``teacher_mdp.py`` are re-implemented in
:mod:`rl_exp.tasks.baseline_mdp` (with a test that catches drift).

What is missing is missing on purpose, and every absence is written here rather than
inherited:

* no terrain generator, no height scanner, no foot-ring sensors, no privileged
  observation group -- flat ground is the whole point, and the policy group already
  carries exactly the 7 proprio terms (3+3+3+3+26+26+26 = 90 dims);
* no curriculum of any kind (``terrain_levels`` removed; the staged speed curriculum
  belongs to other lines and simply does not exist here);
* no domain randomization, and no pushes: "no curriculum" and "no DR" are independent
  decisions, so every randomization event the framework base registers is set to None
  explicitly. Deleting the c_k clock alone would leave them running at full strength,
  and two of them (the interval wrench and the interval velocity push) are not c_k-gated
  at all -- they would never have annealed in the first place.

The command is a fixed point, and the two switches that can rewrite a "fixed" command
are turned off explicitly (``heading_command``, ``rel_standing_envs``). ``baseline_probe``
reads the issued command tensor rather than trusting the config, because a config that
*says* 0.5 m/s and a command manager that issues something else look identical here.
"""

import pathlib
from typing import ClassVar

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    ActionsCfg,
    LocomotionVelocityRoughEnvCfg,
)

from rl_exp.tasks import baseline_mdp, recipe_params
from rl_exp.tasks.play_utils import apply_play_wiring

# this file lives at rl_exp/tasks/baseline_env_cfg.py -> exp root is parents[1]
_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]

# family-relative handle of this recipe line: the one place that answers "whose line is
# this", used both here for the parameter path and by the gates for the lock routing
_LINE_KEY = "lizard/baseline"
_DEFAULT_VERSION = "v1"


def _load_params(version: str | None = None) -> dict:
    """Load this line's parameter SSOT.

    Args:
        version: a frozen version handle (``"v1"``) to read that version's frozen copy, or
            None for the live dev yaml. Always pass the cfg's own ``params_version``: a
            version-stamped task that read the dev yaml would be pinned to a mutable file.

    Returns:
        The resolved parameters of this line, as this caller's own tree -- the line shares the
        one loader now, so it also gets the parse cache every other line had.
    """
    return recipe_params.load(_LINE_KEY, version)


@configclass
class BaselineActionsCfg(ActionsCfg):
    """The deployed two-group action split, frozen.

    Legs are ordered before spine so the concatenated 26-dim action layout equals the
    articulation tree order -- the same layout the observations (``last_action``) assume.
    The split exists because the platform's interface is split; it is frozen here rather
    than simplified to one group, since a baseline that trains against a different action
    interface cannot answer a question about this robot as deployed.

    ``joint_pos`` (the single-group base term) is removed: leaving it in place would add
    26 more action dims driven by the same joints.
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
        joint_names=["chest_.*", "neck_.*", "tail[0-9]_.*"],
        scale=0.25,
        use_default_offset=True,
    )


@configclass
class BaselineFlatEnvCfg(LocomotionVelocityRoughEnvCfg):
    """Flat ground, fixed 0.5 m/s forward, no curriculum, no randomization."""

    # declared owner and version: the pair every gate routes by. ClassVar on purpose --
    # a plain member becomes a dataclass field and would change the config snapshot.
    params_line: ClassVar[str] = _LINE_KEY
    params_version = _DEFAULT_VERSION

    def __post_init__(self):
        super().__post_init__()
        params = _load_params(self.params_version)
        robot_params = params["robot"]
        actuator_params = params["actuators"]
        action_params = params["action"]
        sim_params = params["sim"]
        names_params = params["names"]
        cmd_params = params["commands"]
        reward_params = params["rewards"]
        term_params = params["terminations"]
        scale_params = params["params"]
        base_name = robot_params["base_body_name"]

        # --- robot: the shared, frozen asset -------------------------------------
        # implicit PD on purpose: the drive runs inside the physics solver at the physics
        # rate (200 Hz); sampled 50 Hz explicit torque PD is unstable on the spine.
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

        # --- action interface: frozen split and scales ---------------------------
        self.actions = BaselineActionsCfg()
        self.actions.joint_pos_legs.scale = action_params["legs_scale"]
        self.actions.joint_pos_spine.scale = action_params["spine_scale"]
        for term_name in ("joint_pos_legs", "joint_pos_spine"):
            getattr(self.actions, term_name).use_default_offset = action_params["use_default_offset"]

        # --- flat ground, and no scanner at all ----------------------------------
        self.scene.terrain.terrain_type = "plane"
        self.scene.terrain.terrain_generator = None
        self.scene.height_scanner = None

        # --- observations: proprio only, corruption off explicitly ---------------
        # the policy group already carries exactly the 7 proprio terms; height_scan is
        # the only removal. Observation noise is a randomization like any other, so it is
        # switched off here rather than left to the group's default.
        self.observations.policy.height_scan = None
        self.observations.policy.enable_corruption = False

        # --- timing from SSOT ----------------------------------------------------
        self.decimation = sim_params["decimation"]
        self.episode_length_s = sim_params["episode_length_s"]
        self.sim.dt = sim_params["dt"]
        self.sim.render_interval = self.decimation

        # --- fixed command: a point, with both rewriting switches off ------------
        self.commands.base_velocity.ranges.lin_vel_x = tuple(cmd_params["lin_vel_x"])
        self.commands.base_velocity.ranges.lin_vel_y = tuple(cmd_params["lin_vel_y"])
        self.commands.base_velocity.ranges.ang_vel_z = tuple(cmd_params["ang_vel_z"])
        self.commands.base_velocity.heading_command = cmd_params["heading_command"]
        self.commands.base_velocity.rel_standing_envs = cmd_params["rel_standing_envs"]

        # --- rewards: seven terms, everything else removed by name ---------------
        # named removals, not "the ones I forgot": the base registers ten reward terms
        # and this recipe keeps four of them.
        self.rewards.track_lin_vel_xy_exp = None  # replaced by the yaw-frame kernel
        self.rewards.track_lin_vel_xy_miki = RewTerm(
            func=baseline_mdp.track_lin_vel_xy_miki,
            weight=reward_params["track_lin_vel_xy_miki"],
            params={"command_name": "base_velocity", "sigma_sq": scale_params["miki_sigma_sq"]},
        )
        self.rewards.track_ang_vel_z_exp.weight = reward_params["track_ang_vel_z_exp"]
        self.rewards.track_ang_vel_z_exp.params["std"] = scale_params["track_std"]
        self.rewards.lin_vel_z_l2.weight = reward_params["lin_vel_z_l2"]
        self.rewards.action_rate_l2.weight = reward_params["action_rate_l2"]
        self.rewards.dof_torques_l2.weight = reward_params["dof_torques_l2"]
        self.rewards.undesired_contacts.weight = reward_params["undesired_contacts"]
        self.rewards.undesired_contacts.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["undesired_contact_body_names"]
        )
        self.rewards.belly_contact_force = RewTerm(
            func=baseline_mdp.belly_contact_force,
            weight=reward_params["belly_contact_force"],
            params={
                "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[base_name]),
                "force_scale": scale_params["belly_force_scale"],
            },
        )
        for term_name in ("ang_vel_xy_l2", "dof_acc_l2", "feet_air_time", "flat_orientation_l2", "dof_pos_limits"):
            setattr(self.rewards, term_name, None)

        # --- fall termination: base contact ends the episode --------------------
        # on flat ground base contact means the robot is down, so "survival" has a
        # definition and belly-sliding forward (which the tracking term would pay for)
        # is a failure rather than a slow penalty.
        self.terminations.base_contact.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=[base_name]
        )
        self.terminations.base_contact.params["threshold"] = term_params["base_contact_threshold"]

        # --- no curriculum -------------------------------------------------------
        # terrain_levels is the framework base's only curriculum term; the staged speed
        # and terrain curricula are added by other lines' code and are absent here.
        self.curriculum.terrain_levels = None

        # --- no domain randomization: every base event named and removed ---------
        # the two interval events are the reason this cannot be done by deleting the c_k
        # clock: they are not c_k-gated, so they would run at full strength forever.
        for event_name in (
            "physics_material",  # ground friction buckets
            "add_base_mass",  # base mass scale (framework default: +-25%)
            "base_com",  # base CoM offset
            "base_external_force_torque",  # interval wrench, 4-8 s
            "push_robot",  # interval velocity push, 3-6 s
            "reset_robot_joints",  # reset-state joint scaling
        ):
            setattr(self.events, event_name, None)
        # the event that must stay is the one that places the robot; its ranges are
        # zeroed axis by axis (whatever axes the base declares), so the spawn is a
        # deterministic pose rather than a hidden randomization.
        reset_params = self.events.reset_base.params
        for range_key in ("pose_range", "velocity_range"):
            for axis in list(reset_params.get(range_key, {})):
                reset_params[range_key][axis] = (0.0, 0.0)


@configclass
class BaselineFlatEnvCfg_PLAY(BaselineFlatEnvCfg):
    """Play variant: deterministic evaluation wiring (single source: play_utils)."""

    def __post_init__(self):
        super().__post_init__()
        apply_play_wiring(self)
