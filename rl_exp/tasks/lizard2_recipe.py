# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Lizard2 recipe elements and declarations, independent of main-line imports.

Self-contained by contract: no other recipe line is imported, and the shared, actively-mutated
``teacher_mdp.py`` is not imported either. The three kernels this family's recipe needs live
below as verbatim copies (``miki_tracking_kernel`` / ``track_lin_vel_xy_miki`` /
``belly_contact_force``) -- same code, same numbers, written here because this line has no module
of its own to import them from. They are NOT pinned by the other line's drift test; nothing here
notices if ``teacher_mdp`` changes. The sibling line's fourth copy (``ContactLoadDwellTerm``) is
not needed here: this family's only version is v1, whose yaml declares no
``terminations.contact_load_guard``, so the term it guards could never be built.
"""

import pathlib

import torch

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.envs import mdp
from isaaclab.managers import (
    RewardTermCfg as RewTerm,
    SceneEntityCfg,
    TerminationTermCfg as DoneTerm,
)
from isaaclab.utils.math import quat_apply_inverse, yaw_quat

from rl_exp.tasks import lizard2_env_cfg, recipe_params
from rl_exp.tasks.play_utils import apply_play_wiring
from rl_exp.tasks.recipe_factory import make_class

_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]


def _doc(cfg) -> dict:
    return recipe_params.load(cfg.params_line, cfg.params_version)


# ---------------------------------------------------------------------------------------------
# The kernels, copied rather than imported (see the module docstring).
# ---------------------------------------------------------------------------------------------
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
    yaw drift is reported separately by the evaluator.

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


# ---------------------------------------------------------------------------------------------
# Elements: one function per declared behaviour, applied in table order.
# ---------------------------------------------------------------------------------------------
def lizard2_robot(cfg) -> None:
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


def lizard2_actions(cfg) -> None:
    """The deployed two-group split, frozen: a reference run training against a different action
    interface cannot answer a question about this robot as deployed.

    Which joints each group drives is a parameter, but its *absence* is not an accident: a yaml
    without ``action.joints`` keeps the class default (this line's v1 does, because v1 is frozen).
    A version that wants a narrower interface declares it -- the blade joints could lose command
    authority while the feet keep their PD."""
    action_params = _doc(cfg)["action"]
    cfg.actions = lizard2_env_cfg.Lizard2ActionsCfg()
    for term_name, group in (("joint_pos_legs", "legs"), ("joint_pos_spine", "spine")):
        term = getattr(cfg.actions, term_name)
        term.scale = action_params[f"{term_name.removeprefix('joint_pos_')}_scale"]
        term.use_default_offset = action_params["use_default_offset"]
        if "joints" in action_params:
            term.joint_names = list(action_params["joints"][group])


def lizard2_flat_ground(cfg) -> None:
    """Flat ground is the whole point: no generator, and no scanner (it scans a constant)."""
    cfg.scene.terrain.terrain_type = "plane"
    cfg.scene.terrain.terrain_generator = None
    cfg.scene.height_scanner = None


def lizard2_proprio_obs(cfg) -> None:
    """One group of seven proprio terms. ``height_scan`` is the only removal, and observation
    noise is a randomization like any other -- switched off rather than left to the default."""
    cfg.observations.policy.height_scan = None
    cfg.observations.policy.enable_corruption = False


def lizard2_timing(cfg) -> None:
    """50 Hz control over a 20 s episode, from the line's yaml."""
    sim_params = _doc(cfg)["sim"]
    cfg.decimation = sim_params["decimation"]
    cfg.episode_length_s = sim_params["episode_length_s"]
    cfg.sim.dt = sim_params["dt"]
    cfg.sim.render_interval = cfg.decimation


def lizard2_velocity_command(cfg) -> None:
    """A command *range*, landed exactly as the yaml wrote it: ``lin_vel_x`` ``[0.0, 2.0]`` m/s,
    with ``lin_vel_y`` and ``ang_vel_z`` fixed at 0.0. Nothing here rewrites or narrows it -- the
    framework's own command term already carries a 10 s resampling window, so a 20 s episode holds
    two commands and the transition between them is graded too. This element's whole job is to copy
    the yaml's ranges onto the command manager.

    ``heading_command`` and ``rel_standing_envs`` are off explicitly, because either can rewrite the
    issued command at runtime: ``heading_command`` would rewrite ``ang_vel_z`` from the heading
    error, and ``rel_standing_envs`` would zero that fraction of envs while they still collect
    tracking reward. The startup probe reads the issued tensor rather than trusting this."""
    cmd_params = _doc(cfg)["commands"]
    ranges = cfg.commands.base_velocity.ranges
    ranges.lin_vel_x = tuple(cmd_params["lin_vel_x"])
    ranges.lin_vel_y = tuple(cmd_params["lin_vel_y"])
    ranges.ang_vel_z = tuple(cmd_params["ang_vel_z"])
    cfg.commands.base_velocity.heading_command = cmd_params["heading_command"]
    cfg.commands.base_velocity.rel_standing_envs = cmd_params["rel_standing_envs"]


def lizard2_rewards(cfg) -> None:
    """Seven terms; the rest removed by name, not by omission -- the framework base registers ten
    and this recipe keeps four of them (the other three are the ones it replaces or adds)."""
    params = _doc(cfg)
    reward_params = params["rewards"]
    scale_params = params["params"]
    base_name = params["robot"]["base_body_name"]

    cfg.rewards.track_lin_vel_xy_exp = None
    cfg.rewards.track_lin_vel_xy_miki = RewTerm(
        func=track_lin_vel_xy_miki,
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
        func=belly_contact_force,
        weight=reward_params["belly_contact_force"],
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[base_name]),
            "force_scale": scale_params["belly_force_scale"],
        },
    )
    for term_name in ("ang_vel_xy_l2", "dof_acc_l2", "feet_air_time", "flat_orientation_l2", "dof_pos_limits"):
        setattr(cfg.rewards, term_name, None)


def lizard2_contact_gate(cfg) -> None:
    """Down means the episode is over, and on a flat plane this robot has two ways to be down:
    ``base_link`` touching the ground, and the front chain (``chest_.*``/``neck_.*``) touching it
    face-first.

    Both are the framework's ``illegal_contact`` pointed at the bodies and threshold this line's yaml
    names, so the guard adds no kernel: the threshold is the same 1.0 N as ``base_contact`` (one
    number to reason about), and the dwell question is answered by the contact sensor's own history
    window instead of an added timer. That is why the sibling line's dwell-capable kernel is not
    copied here: it exists there to implement a dwell this line does not declare, and a copy of live
    logic whose parameter is never varied is dead weight.

    The head guard is a *contact* gate, not a load criterion, on purpose: the sibling line's v1 failure
    was a policy bearing weight on its neck in 66% of frames without ever sustaining the load long
    enough for a dwell-based criterion, so a contact gate is the one that cannot be averaged out."""
    terminations = _doc(cfg)["terminations"]
    cfg.terminations.base_contact.params["sensor_cfg"] = SceneEntityCfg(
        "contact_forces", body_names=[_doc(cfg)["robot"]["base_body_name"]]
    )
    cfg.terminations.base_contact.params["threshold"] = terminations["base_contact_threshold"]
    cfg.terminations.head_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces",
                                         body_names=_doc(cfg)["names"]["head_contact_body_names"]),
            "threshold": terminations["head_contact_threshold"],
        },
    )


def lizard2_no_curriculum(cfg) -> None:
    """``terrain_levels`` is the framework base's only curriculum term; the staged speed and
    terrain curricula are other lines' code and do not exist here."""
    cfg.curriculum.terrain_levels = None


def lizard2_no_dr(cfg) -> None:
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


LIZARD2_RECIPES: dict[str, dict] = {
    "v1": {
        "elements": (
            "lizard2_robot",
            "lizard2_actions",
            "lizard2_flat_ground",
            "lizard2_proprio_obs",
            "lizard2_timing",
            "lizard2_velocity_command",
            "lizard2_rewards",
            "lizard2_contact_gate",
            "lizard2_no_curriculum",
            "lizard2_no_dr",
        ),
        # PLAY keeps every wire the recipe built (its ``reset_base`` is the framework stock one,
        # zeroed by the recipe itself); the shared wiring is the whole evaluation variant.
        "play_elements": (),
        # ``lizard2_timing`` restates the framework stock values on purpose: it PINS them, so a
        # framework default that moves shows up as this recipe's difference from its base
        # instead of silently carrying the recipe along. An element whose value equals the
        # base's moves no field, which the attribution check would read as a dead declaration.
        "pins": ("lizard2_timing",),
        # no curriculum at all on this line: the declaration is False for both kinds, and
        # ``lizard2_no_curriculum`` is what makes it so.
        "declares": (False, False),
        # no curriculum to climb a range either, so the range is never "pinned for evaluation":
        # the yaml's own window is what both kinds use.
        "pins_full_range": (False, False),
        "train": "Lizard2-Flat-v1",
        "play": "Lizard2-Flat-Play-v1",
    },
}

ELEMENTS = {
    name: globals()[name]
    for entry in LIZARD2_RECIPES.values()
    for kind in ("elements", "play_elements")
    for name in entry[kind]
}
"""Every element the table names, train and play alike: one lookup, so a play-only element is not
a KeyError waiting for the first PLAY variant that needs one."""


def recipe_class(version: str, *, play: bool = False, name: str) -> type:
    """Construct the lizard2 class from its own declaration and shared factory."""
    entry = LIZARD2_RECIPES[version]

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
        lizard2_env_cfg.Lizard2WiringCfg, name=name, version=entry.get("params_version", version),
        statements=statements, apply=apply,
        description=f"lizard2/main/{version}{'/play' if play else ''}, built from its declared elements.",
    )
