# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Baseline recipe elements and declarations, independent of main-line imports."""

import pathlib

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import RewardTermCfg as RewTerm, SceneEntityCfg

from rl_exp.tasks import baseline_env_cfg, baseline_mdp, recipe_params
from rl_exp.tasks.play_utils import apply_play_wiring
from rl_exp.tasks.recipe_factory import make_class

_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]


def _doc(cfg) -> dict:
    return recipe_params.load(cfg.params_line, cfg.params_version)


def baseline_robot(cfg) -> None:
    """The shared frozen asset, with implicit PD at the physics rate (sampled 50 Hz explicit
    torque PD is unstable on the spine)."""
    params = _doc(cfg)
    robot_params = params["robot"]
    actuators = {
        group_name: ImplicitActuatorCfg(
            joint_names_expr=group_params["joint_patterns"],
            stiffness=group_params["stiffness"],
            damping=group_params["damping"],
            effort_limit=group_params["effort_limit"],
            velocity_limit=group_params["velocity_limit"],
            armature=group_params["armature"],
        )
        for group_name, group_params in params["actuators"].items()
    }
    cfg.scene.robot = ArticulationCfg(
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


def baseline_actions(cfg) -> None:
    """The deployed two-group split, frozen: a baseline training against a different action
    interface cannot answer a question about this robot as deployed."""
    action_params = _doc(cfg)["action"]
    cfg.actions = baseline_env_cfg.BaselineActionsCfg()
    for term_name in ("joint_pos_legs", "joint_pos_spine"):
        term = getattr(cfg.actions, term_name)
        term.scale = action_params[f"{term_name.removeprefix('joint_pos_')}_scale"]
        term.use_default_offset = action_params["use_default_offset"]


def baseline_flat_ground(cfg) -> None:
    """Flat ground is the whole point: no generator, and no scanner (it scans a constant)."""
    cfg.scene.terrain.terrain_type = "plane"
    cfg.scene.terrain.terrain_generator = None
    cfg.scene.height_scanner = None


def baseline_proprio_obs(cfg) -> None:
    """One group of seven proprio terms. ``height_scan`` is the only removal, and observation
    noise is a randomization like any other -- switched off rather than left to the default."""
    cfg.observations.policy.height_scan = None
    cfg.observations.policy.enable_corruption = False


def baseline_timing(cfg) -> None:
    """50 Hz control over a 20 s episode, from the line's yaml."""
    sim_params = _doc(cfg)["sim"]
    cfg.decimation = sim_params["decimation"]
    cfg.episode_length_s = sim_params["episode_length_s"]
    cfg.sim.dt = sim_params["dt"]
    cfg.sim.render_interval = cfg.decimation


def baseline_fixed_command(cfg) -> None:
    """A command *point*, with both switches that can rewrite one turned off explicitly:
    ``heading_command`` would rewrite ``ang_vel_z`` from the heading error, and
    ``rel_standing_envs`` would zero that fraction of envs while they still collect tracking
    reward. ``baseline_probe`` reads the issued tensor rather than trusting this."""
    cmd_params = _doc(cfg)["commands"]
    ranges = cfg.commands.base_velocity.ranges
    ranges.lin_vel_x = tuple(cmd_params["lin_vel_x"])
    ranges.lin_vel_y = tuple(cmd_params["lin_vel_y"])
    ranges.ang_vel_z = tuple(cmd_params["ang_vel_z"])
    cfg.commands.base_velocity.heading_command = cmd_params["heading_command"]
    cfg.commands.base_velocity.rel_standing_envs = cmd_params["rel_standing_envs"]


def baseline_rewards(cfg) -> None:
    """Seven terms; the rest removed by name, not by omission -- the framework base registers ten
    and this recipe keeps four of them (the other three are the ones it replaces or adds)."""
    params = _doc(cfg)
    reward_params = params["rewards"]
    scale_params = params["params"]
    base_name = params["robot"]["base_body_name"]

    cfg.rewards.track_lin_vel_xy_exp = None
    cfg.rewards.track_lin_vel_xy_miki = RewTerm(
        func=baseline_mdp.track_lin_vel_xy_miki,
        weight=reward_params["track_lin_vel_xy_miki"],
        params={"command_name": "base_velocity", "sigma_sq": scale_params["miki_sigma_sq"]},
    )
    cfg.rewards.track_ang_vel_z_exp.weight = reward_params["track_ang_vel_z_exp"]
    cfg.rewards.track_ang_vel_z_exp.params["std"] = scale_params["track_std"]
    cfg.rewards.lin_vel_z_l2.weight = reward_params["lin_vel_z_l2"]
    cfg.rewards.action_rate_l2.weight = reward_params["action_rate_l2"]
    cfg.rewards.dof_torques_l2.weight = reward_params["dof_torques_l2"]
    cfg.rewards.undesired_contacts.weight = reward_params["undesired_contacts"]
    cfg.rewards.undesired_contacts.params["sensor_cfg"] = SceneEntityCfg(
        "contact_forces", body_names=params["names"]["undesired_contact_body_names"]
    )
    cfg.rewards.belly_contact_force = RewTerm(
        func=baseline_mdp.belly_contact_force,
        weight=reward_params["belly_contact_force"],
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[base_name]),
            "force_scale": scale_params["belly_force_scale"],
        },
    )
    for term_name in ("ang_vel_xy_l2", "dof_acc_l2", "feet_air_time", "flat_orientation_l2", "dof_pos_limits"):
        setattr(cfg.rewards, term_name, None)


def baseline_base_contact(cfg) -> None:
    """On flat ground base contact means the robot is down, so "survival" has a definition and
    belly-sliding forward -- which the tracking term would pay for -- is a failure."""
    cfg.terminations.base_contact.params["sensor_cfg"] = SceneEntityCfg(
        "contact_forces", body_names=[_doc(cfg)["robot"]["base_body_name"]]
    )
    cfg.terminations.base_contact.params["threshold"] = _doc(cfg)["terminations"]["base_contact_threshold"]


def baseline_no_curriculum(cfg) -> None:
    """``terrain_levels`` is the framework base's only curriculum term; the staged speed and
    terrain curricula are other lines' code and do not exist here."""
    cfg.curriculum.terrain_levels = None


def baseline_no_dr(cfg) -> None:
    """Every randomization event the framework base registers, named and removed -- except the one
    that also happens to be the joint reset.

    Deleting the c_k clock alone would leave them at full strength -- and two of them (the
    interval wrench and the interval velocity push) are not c_k-gated at all, so they would never
    have annealed in the first place. ``reset_base`` must stay: it is what places the robot, and
    its own ranges are zeroed axis by axis (whatever axes the base declares) so the spawn is a
    deterministic pose rather than a hidden randomization.

    ``reset_robot_joints`` stays too, pinned instead of randomized, because in this IsaacLab it is
    the *only* writer of joint state at reset: ``InteractiveScene.reset(env_ids)`` calls
    ``Articulation.reset(env_ids)``, which clears actuator state and the two wrench composers and
    nothing else (``isaaclab_physx/assets/articulation/articulation.py``), so with this event gone
    a respawned env keeps whatever joint positions and velocities the last episode ended with --
    the robot is re-placed at the default height carrying a stale pose. The event's own numbers are
    ``reset_joints_by_scale``'s, where ``rand*(upper-lower)+lower`` gives the bound exactly when both
    ends are equal (``isaaclab/utils/math.py``): ``(1.0, 1.0)`` is the default pose, ``(0.0, 0.0)``
    is zero velocity. So this term carries the reset, not randomization -- pinned, it does not
    belong in the removal list, and a future wish to randomize the initial pose belongs in a term of
    its own (the v12 line's ``reset_joints_by_offset`` package) rather than as a re-scaling here.
    Verified empirically (and kept verified) by ``rl_exp/tools/verify/reset_check.py``.
    """
    for event_name in (
        "physics_material",  # ground friction buckets
        "add_base_mass",  # base mass scale (framework default: +-25%)
        "base_com",  # base CoM offset
        "base_external_force_torque",  # interval wrench, 4-8 s
        "push_robot",  # interval velocity push, 3-6 s
    ):
        setattr(cfg.events, event_name, None)
    cfg.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
    cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)
    reset_params = cfg.events.reset_base.params
    for range_key in ("pose_range", "velocity_range"):
        for axis in list(reset_params.get(range_key, {})):
            reset_params[range_key][axis] = (0.0, 0.0)


BASELINE_RECIPES: dict[str, dict] = {
    "v1": {
        "elements": (
            "baseline_robot",
            "baseline_actions",
            "baseline_flat_ground",
            "baseline_proprio_obs",
            "baseline_timing",
            "baseline_fixed_command",
            "baseline_rewards",
            "baseline_base_contact",
            "baseline_no_curriculum",
            "baseline_no_dr",
        ),
        # PLAY keeps every wire the recipe built (its ``reset_base`` is the framework stock one,
        # zeroed by the recipe itself); the shared wiring is the whole evaluation variant.
        "play_elements": (),
        # ``baseline_timing`` restates the framework stock values on purpose: it PINS them, so a
        # framework default that moves shows up as this recipe's difference from its base
        # instead of silently carrying the recipe along. An element whose value equals the
        # base's moves no field, which the attribution check would read as a dead declaration.
        "pins": ("baseline_timing",),
        # no curriculum at all on this line: the declaration is False for both kinds, and
        # ``baseline_no_curriculum`` is what makes it so.
        "declares": (False, False),
        # no curriculum to climb a range either, so the range is never "pinned for evaluation":
        # the yaml's own window is what both kinds use.
        "pins_full_range": (False, False),
        "train": "Lizard-Baseline-Flat-v1",
        "play": "Lizard-Baseline-Flat-Play-v1",
    },
}

ELEMENTS = {
    name: globals()[name]
    for entry in BASELINE_RECIPES.values()
    for kind in ("elements", "play_elements")
    for name in entry[kind]
}
"""Every element the table names, train and play alike: one lookup, so a play-only element is not
a KeyError waiting for the first PLAY variant that needs one."""


def recipe_class(version: str, *, play: bool = False, name: str) -> type:
    """Construct the baseline class from its own declaration and shared factory."""
    entry = BASELINE_RECIPES[version]

    def apply(cfg):
        for element in entry["elements"]:
            ELEMENTS[element](cfg)
        if play:
            apply_play_wiring(cfg)
            for element in entry["play_elements"]:
                ELEMENTS[element](cfg)

    statements = {
        "REQUIRES_CURRICULUM_STATE": entry["declares"][int(play)],
        "PLAY_PINS_COMMAND_RANGE": entry["pins_full_range"][int(play)],
    }
    return make_class(
        baseline_env_cfg.BaselineWiringCfg, name=name, version=entry.get("params_version", version),
        statements=statements, apply=apply,
        description=f"lizard/baseline/{version}{'/play' if play else ''}, built from its declared elements.",
    )
