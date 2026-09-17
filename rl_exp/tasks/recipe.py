# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The recipe builder: one env cfg from what a recipe declares (``ARCH_PLAN.md`` 2.4, stage B3).

The class hierarchy expresses a recipe twice over: once as the shared base wiring, and again as a
chain of per-version subclasses whose ``__post_init__`` each overwrite a few fields. The winner
is whichever class the MRO ran last, so "what is v14" is only readable by replaying every body in
the chain -- and a new recipe means a new class.

The builder keeps the shared wiring (an env cfg whose every structural choice resolves from the
version it is handed) and turns the *deltas* into data: an ordered list of named elements per
recipe. That is the whole point of stage B -- a new recipe becomes a declaration, not a subclass.

A recipe is listed here only once its entire delta is declared. Until then the field is ``None``
and the hard-A gate prints it, because a builder that quietly produced "v14 minus whatever I have
not moved yet" would pass every check it was asked to pass.
"""

from __future__ import annotations

import pathlib
from typing import ClassVar

import isaaclab.sim as sim_utils
import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.configclass import configclass

from rl_exp.tasks import baseline_env_cfg, baseline_mdp, components, recipe_params, teacher_mdp
from rl_exp.tasks import curriculum_state as cstate
from rl_exp.tasks import teacher_env_cfg
from rl_exp.tasks.play_utils import apply_play_wiring
from rl_exp.tasks.staged_curriculum import StageCfg, StagedCurriculumTerm, StagedCurriculumTermCfg

# recipe.py lives at rl_exp/tasks/recipe.py -> exp root is parents[1], the same root the line
# modules resolve their asset paths against
_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]


def _doc(cfg) -> dict:
    """This recipe's parameters document.

    Read through the line the cfg declares (``params_line``) and the version it carries, so an
    element cannot read another recipe's numbers by accident -- which is the whole reason the
    version is a field and not a class name.
    """
    return recipe_params.load(cfg.params_line, cfg.params_version)


def v3_contact_headroom(cfg) -> None:
    """PhysX contact buffer headroom (v3.6.1).

    Belly contact is persistent by design once the base-contact termination is gone (a
    flat-belly robot is not tilted, so tilt does not fire either) and the v3 terrain adds
    stepping-stone contact pairs. The stock 2**26 collision stack overflows at 4096 envs and
    PhysX then drops contacts silently, i.e. nondeterministic physics. v1/v2 keep the stock
    value.
    """
    cfg.sim.physics.default.gpu_collision_stack_size = 2**28


def v3_speed_curriculum(cfg) -> None:
    """Staged speed curriculum (v3.6).

    v1's replay showed foot-pad creeping is the optimum at a 1 m/s command cap, so the range
    climbs -1..2 up to 5, gated on success_rate >= 0.8 sustained 120 s: a stage the robot cannot
    track is never applied (user decision 2026-09-01). Stage 0 seeds the cfg range too, so the
    first resamples already match the curriculum.
    """
    cfg.curriculum.speed_curriculum = StagedCurriculumTermCfg(
        func=StagedCurriculumTerm,
        stages=[
            StageCfg(command_ranges={"lin_vel_x": (-1.0, 2.0)}, metric_threshold=0.8, sustain_s=120.0),
            StageCfg(command_ranges={"lin_vel_x": (-1.0, 3.0)}, metric_threshold=0.8, sustain_s=120.0),
            StageCfg(command_ranges={"lin_vel_x": (-1.0, 4.0)}, metric_threshold=0.8, sustain_s=120.0),
            StageCfg(command_ranges={"lin_vel_x": (-1.0, 5.0)}),
        ],
    )


def v3_anti_drag_reward(cfg) -> None:
    """D2: the anti-drag foot-clearance reward replaces ``feet_air_time``.

    The ``feet_air_time`` *observation* term stays (it lives in the priv group) -- only the
    reward is replaced, by one that charges for dragging a foot near the ground.
    """
    rfc = _doc(cfg)["v3"]["r_fc"]
    cfg.rewards.feet_air_time = None
    cfg.rewards.foot_clearance = RewTerm(
        func=teacher_mdp.FootClearanceReward,
        weight=rfc["weight"],
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
            "clearance": rfc["clearance"],
            "contact_threshold": rfc["contact_threshold"],
            "mesh_prim_path": "/World/ground",
            "max_distance": rfc["max_distance"],
            "start_offset": rfc["start_offset"],
        },
    )


def v3_ck_clock(cfg) -> None:
    """D3/D4: the c_k schedule and its in-place function swaps.

    Term names stay stable so the PLAY wiring and the DR event list keep matching -- the swap is
    of ``func`` and ``mode``, never of the term's name. The loop form (rather than a literal per
    term) is also what keeps these recipe-layer swaps out of the family-vs-teacher wiring parity
    text check, which guards the BASE wiring freeze, not version recipes.
    """
    ck = _doc(cfg)["v3"]["curriculum_ck"]
    cfg.events.init_ck = EventTerm(
        func=teacher_mdp.init_ck,
        mode="startup",
        params={
            "c0": ck["c0"],
            "decay": ck["decay"],
            "steps_per_iteration": ck["steps_per_iteration"],
        },
    )
    for name, func in (
        ("dof_acc_l2", teacher_mdp.joint_acc_l2_ck),
        ("dof_torques_l2", teacher_mdp.joint_torques_l2_ck),
        ("ang_vel_xy_l2", teacher_mdp.ang_vel_xy_l2_ck),
    ):
        getattr(cfg.rewards, name).func = func
    # base_com lives inside a preset wrapper; .default is the physx branch
    com_term = cfg.events.base_com.default
    com_term.func = teacher_mdp.randomize_rigid_body_com_ck
    com_term.mode = "reset"
    for name, func in (
        ("add_base_mass", teacher_mdp.randomize_rigid_body_mass_ck),
        ("randomize_limb_mass", teacher_mdp.randomize_rigid_body_mass_ck),
        ("randomize_inertia", teacher_mdp.randomize_rigid_body_inertia_ck),
        ("randomize_actuator_gains", teacher_mdp.randomize_actuator_gains_ck),
        ("randomize_joint_params", teacher_mdp.randomize_joint_parameters_ck),
    ):
        term = getattr(cfg.events, name)
        term.func = func
        term.mode = "reset"


def v4_stock_contact_stack(cfg) -> None:
    """v4 re-tests the stock PhysX contact stack (2**26) on the coarser rubble.

    WARNING (user decision 2026-09-02): inspect the terrain before launching training or tests.
    If the overflow returns (PhysX drops contacts silently, so the physics turn
    nondeterministic), the root cause is contact density -- flat soles on a fine heightfield --
    and not buffer size: do not raise the stack again, simplify the contact geometry instead.
    """
    cfg.sim.physics.default.gpu_collision_stack_size = 2**26


def v5_drops_speed_curriculum(cfg) -> None:
    """v5 removes the staged speed curriculum (v5.0).

    Installed by ``v3_speed_curriculum`` above and taken away here, exactly as the subclass
    chain did it: the staged term is a *field* of the curriculum block, so leaving it out of
    the element list would make the built cfg state ``absent`` where the frozen recipe states
    ``null`` -- and the snapshot keeps those apart on purpose. The reason it goes: stage 0's
    (-1, 2) window kept a 50% standstill-freeload band under the exp kernel, and the linear
    kernel below needs no range gating.
    """
    cfg.curriculum.speed_curriculum = None


def v5_reward_package(cfg) -> None:
    """The reward-side anti-collapse package (v5.0-v5.2).

    v3/v4 trained to a foot-pad creeping optimum (15555 iters, success_rate pinned at the
    standstill freeload baseline, terrain levels frozen at 1.27, foot_clearance reward never
    above 5e-5), so four holes are closed here:

    * the exp tracking kernel let ``|v_cmd| < 0.5`` stand still for half the command
      distribution -- the linear (Cheng et al. 2023 Eq. 2) form scores standing 0 and reversal
      negative;
    * ``r_slip`` charges contact-foot sliding (paper S7, c_k-scaled) -- the only direct
      anti-creeping term, dropped from v3 by an erratum;
    * ``r_co`` narrows to thigh/shank (HFE/KFE) and the base body moves to a dedicated
      continuous belly-force penalty at a *constant* weight (lying flat must never become free
      as c_k anneals), HAA/spine exempt (user decision);
    * both new weights are negative in this recipe's yaml -- v5.0/v5.1 shipped them positive,
      i.e. paying for sliding and belly contact (same bug class as the v3 ``r_fc`` sign flip).
    """
    doc = _doc(cfg)
    v5 = doc["v5"]
    base_name = doc["robot"]["base_body_name"]

    cfg.rewards.track_lin_vel_xy_exp = None
    cfg.rewards.track_lin_vel_xy_lin = RewTerm(
        func=teacher_mdp.track_lin_vel_xy_lin,
        weight=v5["track_goal_vel"]["weight"],
        params={"command_name": "base_velocity", "min_speed": v5["track_goal_vel"]["min_speed"]},
    )
    # both cfgs must be explicit params so the manager resolves body_ids (a defaulted
    # SceneEntityCfg stays unresolved and indexes with body_ids=None)
    cfg.rewards.feet_slide = RewTerm(
        func=teacher_mdp.feet_slide_ck,
        weight=v5["r_slip"]["weight"],
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
            "asset_cfg": SceneEntityCfg("robot", body_names=".*_foot"),
        },
    )
    cfg.rewards.undesired_contacts.func = teacher_mdp.undesired_contacts_ck
    cfg.rewards.belly_contact_force = RewTerm(
        func=teacher_mdp.belly_contact_force,
        weight=v5["belly_contact_force"]["weight"],
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[base_name]),
            "force_scale": v5["belly_contact_force"]["force_scale"],
        },
    )


def v5_sir_terrain_curriculum(cfg) -> None:
    """v5.3: the SIR particle terrain curriculum replaces the stock level walk.

    Lee et al. 2020 Algorithm S1 (discrete adaptation): a particle is (terrain type, difficulty
    row) on the fixed 8-type x 10-row x 20-col grid -- v4's types plus a flat bootstrap column --
    and spawn traffic is redistributed per measured success band. The v3.5 "spawn at the easiest
    row" prerequisite dies here: SIR samples uniformly at start (paper line 1), which is why
    ``components.TERRAIN_BY_RECIPE["v5"]`` carries no start level and why this term owns
    ``terrain_levels`` instead.
    """
    sir = _doc(cfg)["v5"]["terrain_curriculum"]
    cfg.curriculum.terrain_levels = teacher_mdp.SIRTerrainCurriculumCfg(
        func=teacher_mdp.SpawnWeightSIRTerrainCurriculum,
        command_name="base_velocity",
        band=tuple(sir["band"]),
        eval_every=int(sir["eval_every"]),
        n_traj_min=int(sir["n_traj_min"]),
        p_transition=float(sir["p_transition"]),
        p_replay=float(sir["p_replay"]),
        success_ratio=float(sir["success_ratio"]),
        soft_edge=float(sir["soft_edge"]),
        steps_per_iteration=int(sir["steps_per_iteration"]),
    )


def v6_spine_unlock(cfg) -> None:
    """v6.1: the whole spine term (rear + neck + tail, 10 joints) becomes live.

    v1-v5 left ``spine_scale`` at the class default 0.0, so the spine and tail were
    policy-frozen and only wobbled passively under PD 150/10. The value is read from *this*
    recipe's yaml (0.25), and that is what keeps v1-v5 pinned at 0.0: a recipe is the document
    it names, not this element's behaviour. The 26-dim action layout and the obs groups
    (90/208/83) are untouched: only the spine channels start moving.
    """
    cfg.actions.joint_pos_spine.scale = _doc(cfg)["action"]["spine_scale"]


def v11_joint_sir_curriculum(cfg) -> None:
    """v11: the joint (terrain combination, velocity bucket) particle filter replaces the row SIR.

    The v5 scalar-row SIR is dropped first -- a field the frozen v11 recipe states, not a detail
    that can be skipped. The replacement is installed under ``teacher_mdp.JOINT_SIR_TERM`` rather
    than ``terrain_levels``: the command term and ``check_obs_layout`` look the term up by that
    same name (v11.1). Measurement returns to the paper's per-state-transition Tr (Lee et al. 2020
    Eq. 2/3/7, family PLAN ledger #15 option a); velocity enters the particle as a repo extension.
    The param-sampled terrain and the particle-sourced command term are structural and declared in
    ``components.TERRAIN_BY_RECIPE`` / ``components.COMMAND_RANGE``.
    """
    v11 = _doc(cfg)["v11"]
    sir = v11["terrain_curriculum"]
    cfg.curriculum.terrain_levels = None
    setattr(
        cfg.curriculum,
        teacher_mdp.JOINT_SIR_TERM,
        teacher_mdp.JointSIRTerrainCurriculumCfg(
            func=teacher_mdp.JointSIRTerrainCurriculum,
            command_name="base_velocity",
            band=tuple(sir["band"]),
            velocity_buckets=tuple(v11["velocity_buckets"]),
            particles_per_type=int(sir["particles_per_type"]),
            eval_every=int(sir["eval_every"]),
            n_traj_min=int(sir["n_traj_min"]),
            p_transition=float(sir["p_transition"]),
            p_replay=float(sir["p_replay"]),
            maintain_mass=float(sir["maintain_mass"]),
            steps_per_iteration=int(sir["steps_per_iteration"]),
        ),
    )


def v12_reset_robustness(cfg) -> None:
    """v12: the Miki et al. 2022 S8 reset/observation robustness package.

    The audit against the paper's S8 list found three gaps on top of v11, all numbers in the
    recipe's yaml:

    * ``reset_robot_joints`` scales the default pose -- all-zero for this sprawled rig, so it has
      been a silent no-op. It is dropped and replaced by three ``reset_joints_by_offset`` terms
      (legs / feet / spine) that randomize initial position *and* velocity, soft-limit clamped.
    * the base pose/velocity reset ranges move into the yaml (stock base-cfg values until now:
      pose x/y +-0.5 m, yaw +-3.14 rad, 6-axis velocity +-0.5 -- now tunable).
    * occasional foot-friction dips and the per-episode height-ring noise state get their reset
      events. ``components.observations`` owns the four extero terms' func and parameters (the
      ``NoisyFootRing`` + ``sample_ring_noise`` pair), so this element only wires the events --
      extero names, order and the 208 width stay the contract.

    Deliberate deviation (user decision 2026-09-10, no student distillation): the noise rides the
    TEACHER actor, so the priv group stays clean.
    """
    v12 = _doc(cfg)["v12"]
    rr = v12["reset_randomization"]
    hn = v12["height_noise"]

    cfg.events.reset_robot_joints = None
    for name, patterns, key in (
        ("reset_joints_legs", [".*_haa_joint", ".*_hfe_joint", ".*_kfe_joint"], "legs"),
        ("reset_joints_feet", [".*_foot_joint"], "feet"),
        ("reset_joints_spine", ["chest_.*", "neck_.*", "tail[0-9]_.*"], "spine"),
    ):
        setattr(
            cfg.events,
            name,
            EventTerm(
                func=mdp.reset_joints_by_offset,
                mode="reset",
                params={
                    "asset_cfg": SceneEntityCfg("robot", joint_names=patterns),
                    "position_range": tuple(rr["joints"][key]),
                    "velocity_range": tuple(rr["joint_velocity"]),
                },
            ),
        )
    cfg.events.reset_base.params["pose_range"] = {a: tuple(r) for a, r in rr["base_pose_range"].items()}
    cfg.events.reset_base.params["velocity_range"] = {a: tuple(r) for a, r in rr["base_velocity_range"].items()}
    cfg.events.foot_friction_dip = EventTerm(
        func=teacher_mdp.FootFrictionDipTerm,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*_foot"),
            "static_friction_range": tuple(rr["friction_dip"]["static"]),
            "dynamic_ratio_range": tuple(rr["friction_dip"]["dynamic_ratio"]),
            "p_dip": float(rr["friction_dip"]["p_dip"]),
        },
    )
    cfg.events.sample_ring_noise = EventTerm(
        func=teacher_mdp.sample_ring_noise,
        mode="reset",
        params={"ratios": tuple(hn["ratios"])},
    )


def v13_miki_kernel(cfg) -> None:
    """v13: the symmetric Miki et al. 2022 tracking kernel replaces the v5 EP one.

    The v10 diagnosis pinned three holes in ``track_lin_vel_xy_lin``: it scores only the velocity
    projection onto the command axis, so overspeed is free (measured +48..54% at 0.3 m/s while the
    ledger read 1.47/1.5), lateral drift is invisible, and a zero command carries no stop gradient.
    ``exp(-||v_cmd - v_yaw||^2 / 0.25)`` on the full 2D error closes all three. Weight stays 1.5
    (not the paper's 0.75) so the tracking ceiling and penalty ratios stay identical to v10.
    """
    v13 = _doc(cfg)["v13"]["track_goal_vel"]
    cfg.rewards.track_lin_vel_xy_lin = None
    cfg.rewards.track_lin_vel_xy_miki = RewTerm(
        func=teacher_mdp.track_lin_vel_xy_miki,
        weight=v13["weight"],
        params={"command_name": "base_velocity", "sigma_sq": v13["sigma_sq"]},
    )


def v14_head_load(cfg) -> None:
    """v14.3: the front-plant termination becomes a per-step penalty.

    A head-planted pose costs reward but keeps its rollout data, which removes the "sustained
    nose-down attitude on a slope" false-positive surface along with the termination. The roll-over
    fall gate that stops a rolled-onto-side/back pose is owned by ``components.terminations``
    (``components.ROLL_OVER``), not by this element.
    """
    head_load = _doc(cfg)["v14"]["head_load"]
    cfg.rewards.head_load_penalty = RewTerm(
        func=teacher_mdp.head_load_penalty,
        weight=head_load["weight"],
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=tuple(head_load["head_body_names"])),
            "force_scale": head_load["force_scale"],
        },
    )


def play_drops_speed_curriculum(cfg) -> None:
    """Evaluation determinism: a good policy must not have its range widened mid-run."""
    cfg.curriculum.speed_curriculum = None


def play_pins_full_command_range(cfg) -> None:
    """Pin the range the curriculum would have climbed to (see ``components.FULL_FORWARD_RANGE``)."""
    cfg.commands.base_velocity.ranges.lin_vel_x = components.FULL_FORWARD_RANGE


def play_drops_sir_terrain_curriculum(cfg) -> None:
    """Deterministic evaluation: the SIR term would reassign spawn origins per episode from
    replay outcomes, so a replay must keep the terrain assignment it started with."""
    cfg.curriculum.terrain_levels = None


def play_drops_joint_sir_curriculum(cfg) -> None:
    """Deterministic evaluation: the joint SIR reassigns spawn origins *and velocities* per
    episode, so a replay must keep its pairing. The particle command term stays wired and then
    takes its uniform-range fallback, which is what the frozen v11/v12 PLAY recipes do."""
    setattr(cfg.curriculum, teacher_mdp.JOINT_SIR_TERM, None)


# --- the baseline line (flat-ground walking baseline, no ancestry in the teacher line) --------
# Its recipes have no upstream mother (``base.json`` is a lineage root), so "what the recipe is"
# is exactly "what it writes on top of the framework stock cfg" -- which is why the same element
# list is also the declared difference from that stock cfg (hard B).
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
    """Every event the framework base registers, named and removed.

    Deleting the c_k clock alone would leave them at full strength -- and two of them (the
    interval wrench and the interval velocity push) are not c_k-gated at all, so they would never
    have annealed in the first place. ``reset_base`` must stay: it is what places the robot, and
    its own ranges are zeroed axis by axis (whatever axes the base declares) so the spawn is a
    deterministic pose rather than a hidden randomization.
    """
    for event_name in (
        "physics_material",  # ground friction buckets
        "add_base_mass",  # base mass scale (framework default: +-25%)
        "base_com",  # base CoM offset
        "base_external_force_torque",  # interval wrench, 4-8 s
        "push_robot",  # interval velocity push, 3-6 s
        "reset_robot_joints",  # reset-state joint scaling
    ):
        setattr(cfg.events, event_name, None)
    reset_params = cfg.events.reset_base.params
    for range_key in ("pose_range", "velocity_range"):
        for axis in list(reset_params.get(range_key, {})):
            reset_params[range_key][axis] = (0.0, 0.0)


# Named recipe elements, in application order. An element takes the env cfg and owns its fields
# outright -- the same contract as the five structural components in :mod:`rl_exp.tasks.components`,
# and it gets the same treatment: one writer, resolved by recipe, never by the MRO.
ELEMENTS: dict[str, object] = {
    "v3_contact_headroom": v3_contact_headroom,
    "v3_speed_curriculum": v3_speed_curriculum,
    "v3_anti_drag_reward": v3_anti_drag_reward,
    "v3_ck_clock": v3_ck_clock,
    "v4_stock_contact_stack": v4_stock_contact_stack,
    "v5_drops_speed_curriculum": v5_drops_speed_curriculum,
    "v5_reward_package": v5_reward_package,
    "v5_sir_terrain_curriculum": v5_sir_terrain_curriculum,
    "v6_spine_unlock": v6_spine_unlock,
    "v11_joint_sir_curriculum": v11_joint_sir_curriculum,
    "v12_reset_robustness": v12_reset_robustness,
    "v13_miki_kernel": v13_miki_kernel,
    "v14_head_load": v14_head_load,
    "play_drops_speed_curriculum": play_drops_speed_curriculum,
    "play_pins_full_command_range": play_pins_full_command_range,
    "play_drops_sir_terrain_curriculum": play_drops_sir_terrain_curriculum,
    "play_drops_joint_sir_curriculum": play_drops_joint_sir_curriculum,
    "baseline_robot": baseline_robot,
    "baseline_actions": baseline_actions,
    "baseline_flat_ground": baseline_flat_ground,
    "baseline_proprio_obs": baseline_proprio_obs,
    "baseline_timing": baseline_timing,
    "baseline_fixed_command": baseline_fixed_command,
    "baseline_rewards": baseline_rewards,
    "baseline_base_contact": baseline_base_contact,
    "baseline_no_curriculum": baseline_no_curriculum,
    "baseline_no_dr": baseline_no_dr,
}

# What each recipe is: the ordered elements it applies on top of the shared wiring (and, for its
# PLAY variant, the extra ones after the shared PLAY wiring), plus the registered tasks it claims
# to reproduce -- named, not derived from the version string, because a task id is a published
# name and a rename must not silently re-point this gate at nothing.
#
# Each delta is stated once, as the previous recipe's delta plus its own additions -- which is what
# the recipes are (vN's subclass extends vN-1's body). Writing them out again per version would put
# "v8 declares the same as v6" in three places to keep in sync; sharing the tuple makes it one
# object. What stays explicit, per recipe, is the task ids.
_V3_DELTA: tuple[str, ...] = (
    "v3_contact_headroom",
    "v3_speed_curriculum",
    "v3_anti_drag_reward",
    "v3_ck_clock",
)
_V4_DELTA: tuple[str, ...] = (*_V3_DELTA, "v4_stock_contact_stack")
_V5_DELTA: tuple[str, ...] = (
    *_V4_DELTA,
    "v5_drops_speed_curriculum",
    "v5_reward_package",
    "v5_sir_terrain_curriculum",
)
# v6.1 unlocks the spine; v8 and v10 add nothing to the cfg (the asset flip and the tilt flag are
# not cfg fields), so the three recipes share this one list and their task ids are the difference.
_V6_DELTA: tuple[str, ...] = (*_V5_DELTA, "v6_spine_unlock")
_V11_DELTA: tuple[str, ...] = (*_V6_DELTA, "v11_joint_sir_curriculum")
_V12_DELTA: tuple[str, ...] = (*_V11_DELTA, "v12_reset_robustness")
# v13 branches off v10, not off v12: the single-variable kernel fix on the v10 line.
_V13_DELTA: tuple[str, ...] = (*_V6_DELTA, "v13_miki_kernel")
_V14_DELTA: tuple[str, ...] = (*_V13_DELTA, "v14_head_load")

_V3_PLAY: tuple[str, ...] = ("play_drops_speed_curriculum", "play_pins_full_command_range")
_SIR_PLAY: tuple[str, ...] = ("play_drops_sir_terrain_curriculum",)
"""The only PLAY element v5-v10 and v13/v14 need: they keep v5's yaml-sourced forward range, so the
``_V3_PLAY`` pair is absent by design -- it would null a curriculum they already dropped and pin the
range to the curriculum's (-1, 5) where the frozen PLAY recipe says (0, 3)."""
_JOINT_SIR_PLAY: tuple[str, ...] = ("play_drops_joint_sir_curriculum",)
"""v11/v12 replace the row SIR with the joint one, so their PLAY guard is the joint term."""

RECIPES: dict[str, dict] = {
    "v1": {"elements": (), "play_elements": (), "declares": (False, False), "train": "Lizard-Rough-v1", "play": "Lizard-Rough-Play-v1"},
    "v2": {"elements": (), "play_elements": (), "declares": (False, False), "train": "Lizard-Rough-v2", "play": "Lizard-Rough-Play-v2"},
    "v3": {"elements": _V3_DELTA, "play_elements": _V3_PLAY, "declares": (False, False), "train": "Lizard-Rough-v3", "play": "Lizard-Rough-Play-v3"},
    "v4": {"elements": _V4_DELTA, "play_elements": _V3_PLAY, "declares": (False, False), "train": "Lizard-Rough-v4", "play": "Lizard-Rough-Play-v4"},
    "v5": {"elements": _V5_DELTA, "play_elements": _SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v5", "play": "Lizard-Rough-Play-v5"},
    # v6/v8/v10 share one element list: v6.1 unlocks the spine (one yaml-sourced line), v8 and
    # v10 change no cfg field at all -- v8's flip + joint renames are the asset, v10's tilt
    # removal is the yaml flag components.terminations already reads. An empty delta is stated
    # as v6's list, never as ``None``: these recipes ARE declared, what they declare beyond v6
    # is nothing.
    "v6": {"elements": _V6_DELTA, "play_elements": _SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v6", "play": "Lizard-Rough-Play-v6"},
    "v8": {"elements": _V6_DELTA, "play_elements": _SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v8", "play": "Lizard-Rough-Play-v8"},
    "v10": {"elements": _V6_DELTA, "play_elements": _SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v10", "play": "Lizard-Rough-Play-v10"},
    # v11 hands the terrain curriculum to the joint particle filter; v12 adds the reset/obs
    # robustness package on top of it. v13 deliberately branches off v10, NOT off v12 -- it is the
    # single-variable kernel fix on the v10 line -- so its list is v6's plus its own element, and
    # the joint SIR / v12 resets are absent from it by construction.
    "v11": {"elements": _V11_DELTA, "play_elements": _JOINT_SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v11", "play": "Lizard-Rough-Play-v11"},
    "v12": {"elements": _V12_DELTA, "play_elements": _JOINT_SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v12", "play": "Lizard-Rough-Play-v12"},
    "v13": {"elements": _V13_DELTA, "play_elements": _SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v13", "play": "Lizard-Rough-Play-v13"},
    "v14": {"elements": _V14_DELTA, "play_elements": _SIR_PLAY, "declares": (True, False), "train": "Lizard-Rough-v14", "play": "Lizard-Rough-Play-v14"},
}

MAIN_LINE = "lizard/main"
BASELINE_LINE = "lizard/baseline"

# The baseline line: flat ground, a fixed low-speed command, proprio only -- and no ancestry in
# the teacher line (its ``base.json`` is a lineage root). Its shared wiring is therefore the
# framework stock cfg, so the recipe's elements are simultaneously "what this recipe is" and
# "how it differs from that stock cfg" -- which is what hard B asks a new recipe to declare.
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
        "train": "Lizard-Baseline-Flat-v1",
        "play": "Lizard-Baseline-Flat-Play-v1",
    },
}

# Line -> its shared wiring and its recipe table. Keyed by the same family-relative handle the
# recipe map and the golden locks use, so "which line is this" has one answer everywhere.
LINES: dict[str, dict] = {
    MAIN_LINE: {"base": teacher_env_cfg.LizardRoughTeacherEnvCfg, "recipes": RECIPES},
    BASELINE_LINE: {"base": baseline_env_cfg.BaselineWiringCfg, "recipes": BASELINE_RECIPES},
}


def declared(line: str = MAIN_LINE) -> list[str]:
    """The recipes of ``line`` whose whole delta is declared, so the builder can produce them."""
    return sorted(version for version, decl in LINES[line]["recipes"].items() if decl["elements"] is not None)


def pending(line: str = MAIN_LINE) -> list[str]:
    """The recipes of ``line`` still expressed by their subclass body."""
    return sorted(version for version, decl in LINES[line]["recipes"].items() if decl["elements"] is None)


def declaration(version: str, *, play: bool = False, line: str = MAIN_LINE) -> bool | None:
    """Whether ``line``'s ``version`` promises a resumable curriculum state, or None if unstated.

    The promise is a *statement about* a recipe, so the snapshot leaves it out (format 2 excludes
    ``ClassVar``) and it is carried as a ``ClassVar`` on the built config rather than as a field --
    a field would enter the frozen golden and re-anchor every lock. Until this table carries it,
    the runtime answered by reading the version subclass; ``check_recipe_build`` compares the two
    for as long as both paths exist, so a drifted table is red instead of quiet.

    Args:
        version: recipe version, a key of this line's recipe table.
        play: the evaluation variant (a PLAY task never resumes a curriculum by construction).
        line: family-relative line handle, a key of :data:`LINES`.

    Returns:
        ``True``/``False`` when the recipe states it, ``None`` when it does not state it at all
        (``build`` then leaves the shared wiring's own statement alone).
    """
    entry = LINES[line]["recipes"].get(version) or {}
    stated = entry.get("declares")
    return None if stated is None else bool(stated[1 if play else 0])


def _wired_class(version: str, *, play: bool, line: str):
    """The class to construct: the line's shared wiring, plus the recipe's own statement.

    A synthesized subclass, for one reason: four readers ask ``type(cfg)`` whether this task
    promises a curriculum state -- the resume path, the save guard, the trainer's import guard and
    the run manifest -- and a builder that returns the bare shared class silently answers "no" for
    a recipe that declares yes. Carrying the statement on the class keeps those readers unchanged
    and keeps the statement out of the snapshot. The class name is the shared wiring's, so nothing
    that records ``type(cfg).__name__`` moves.
    """
    base = LINES[line]["base"]
    stated = declaration(version, play=play, line=line)
    if stated is None:
        return base
    # annotated as a ClassVar, not merely set: the snapshot tells the two apart by the
    # annotation (cfg_snapshot._class_var_names), so an unannotated attribute would enter the
    # frozen-golden comparison as a field the golden does not have -- a statement is not data
    return type(
        base.__name__,
        (base,),
        {"__annotations__": {cstate.REQUIRES_CURRICULUM_STATE: ClassVar[bool]}, cstate.REQUIRES_CURRICULUM_STATE: stated},
    )


def base_cfg(version: str, *, line: str = MAIN_LINE, play: bool = False):
    """The shared wiring a recipe starts from, before any of its own elements are applied.

    Public because the attribution check has to start where the builder starts: a checker that
    built its own base would drift from this one without either side noticing. It carries the
    recipe's statement for the same reason ``build`` does -- otherwise the statement itself would
    read as a field changed by nobody.
    """
    return _wired_class(version, play=play, line=line)(params_version=version)


def apply_into(cfg, version: str, *, play: bool = False, line: str = MAIN_LINE, trace: list | None = None):
    """Apply this recipe's declared steps to an existing cfg -- ``build``'s body, as a function.

    Shared by :func:`build` and :func:`recipe_class` so the two mechanisms cannot drift: one
    applies the steps to an instance the caller holds (and can trace), the other applies them
    during construction, which is what a registry entry needs.

    Args:
        cfg: the cfg to subject to the recipe (usually the shared wiring's instance).
        version: recipe version, a key of this line's recipe table.
        play: also apply the shared PLAY wiring and the recipe's evaluation elements.
        line: family-relative line handle, a key of :data:`LINES`.
        trace: when a list is given, every step is appended as ``(name, callable)``.

    Returns:
        The same cfg, for chaining.
    """
    entry = LINES[line]["recipes"][version]
    for name in entry["elements"]:
        ELEMENTS[name](cfg)
        if trace is not None:
            trace.append((name, ELEMENTS[name]))
    if play:
        # the shared PLAY wiring first, then the recipe's own evaluation-determinism elements:
        # they undo parts of what the recipe just built (a curriculum that would widen the range
        # mid-eval, a range that no longer has a curriculum to climb it)
        apply_play_wiring(cfg)
        if trace is not None:
            trace.append(("apply_play_wiring", apply_play_wiring))
        for name in entry["play_elements"]:
            ELEMENTS[name](cfg)
            if trace is not None:
                trace.append((name, ELEMENTS[name]))
    return cfg


def recipe_class(version: str, *, play: bool = False, line: str = MAIN_LINE, name: str | None = None):
    """The class a registry entry can point at: the shared wiring, wired by its declared steps.

    A class, because that is what a task registration resolves: hydra instantiates the entry point
    with no arguments, so "the recipe" has to be expressible as a constructor. The steps run in
    ``__post_init__`` -- the same place the version subclass bodies ran theirs -- which is what
    makes the declaration path usable as *the training entry* rather than only as a comparison
    subject. ``check_recipe_build`` compares this class against :func:`build` field for field, so
    the two ways of applying one recipe cannot diverge.

    Args:
        version: recipe version, a key of this line's recipe table.
        play: the deterministic evaluation variant.
        line: family-relative line handle, a key of :data:`LINES`.
        name: the class name to use, defaulting to a name derived from the line and version. A
            caller that replaces a registered class passes that class's own name, so anything
            recording ``type(cfg).__name__`` (a checkpoint payload does) cannot tell the two
            paths apart and a resume may cross them.

    Returns:
        The config class. Construct it with no arguments.

    Raises:
        KeyError: the line or the version is not declared.
        ValueError: the recipe's delta is not declared yet.
    """
    if line not in LINES:
        raise KeyError(f"unknown recipe line {line!r}; known: {sorted(LINES)}")
    recipes = LINES[line]["recipes"]
    if version not in recipes:
        raise KeyError(f"unknown recipe {version!r} on {line}; known: {sorted(recipes)}")
    if recipes[version]["elements"] is None:
        raise ValueError(
            f"recipe {version!r} on {line}: its delta is not declared yet (declared: {declared(line)}),"
            " so a class for it would have to guess the missing part"
        )
    base = LINES[line]["base"]
    stated = declaration(version, play=play, line=line)

    def __post_init__(self):
        """The shared wiring's own construction, then this recipe's declared steps.

        The version subclass bodies this replaces did exactly this; the class looks for
        ``base.__post_init__`` rather than ``super()`` because this function is not defined in a
        class body, so it has no ``__class__`` cell for the zero-argument form.
        """
        base.__post_init__(self)
        apply_into(self, version, play=play, line=line)

    namespace: dict = {
        "params_version": version,
        "__post_init__": __post_init__,
        "__doc__": f"{line}/{version}{'/play' if play else ''}, built from its declared elements.",
    }
    if stated is not None:
        # annotated, not merely set: an unannotated attribute enters the snapshot as a field
        # (cfg_snapshot tells the two apart by the annotation), and a statement is not data
        namespace["__annotations__"] = {cstate.REQUIRES_CURRICULUM_STATE: ClassVar[bool]}
        namespace[cstate.REQUIRES_CURRICULUM_STATE] = stated
    klass = type(
        name or f"{base.__name__}_{line.split('/')[-1]}_{version}{'_PLAY' if play else ''}",
        (base,),
        namespace,
    )
    return configclass(klass)


def build(version: str, *, play: bool = False, trace: list | None = None, line: str = MAIN_LINE):
    """The env cfg a recipe declares.

    Args:
        version: recipe version, a key of this line's recipe table.
        play: the deterministic evaluation variant (no randomization, no curriculum).
        trace: when a list is given, every step is appended to it as ``(name, callable)``, in
            application order -- so a reader can replay the recipe instead of restating its
            order (and drift from it).
        line: family-relative line handle, a key of :data:`LINES`. The version counter is
            per-line, so two lines both having a ``"v1"`` is the normal case, not a collision.

    Returns:
        The env cfg, built from that line's shared wiring plus this recipe's declared elements.
        No version subclass is involved.

    Raises:
        KeyError: the line or the version is not declared.
        ValueError: the recipe's delta is not declared yet, so producing a config would mean
            guessing the missing part.
    """
    if line not in LINES:
        raise KeyError(f"unknown recipe line {line!r}; known: {sorted(LINES)}")
    recipes = LINES[line]["recipes"]
    if version not in recipes:
        raise KeyError(f"unknown recipe {version!r} on {line}; known: {sorted(recipes)}")
    elements = recipes[version]["elements"]
    if elements is None:
        raise ValueError(
            f"recipe {version!r} on {line}: its delta is not declared yet (declared: {declared(line)}),"
            f" so the builder cannot produce it without guessing"
        )
    # the version travels as the *field* it is: the shared wiring resolves every structural
    # choice from it, and a subclass that only restated it is exactly what this replaces
    return apply_into(base_cfg(version, line=line, play=play), version, play=play, line=line, trace=trace)
