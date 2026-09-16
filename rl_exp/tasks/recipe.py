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

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg

from rl_exp.tasks import components, recipe_params, teacher_mdp
from rl_exp.tasks import teacher_env_cfg
from rl_exp.tasks.play_utils import apply_play_wiring
from rl_exp.tasks.staged_curriculum import StageCfg, StagedCurriculumTerm, StagedCurriculumTermCfg


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
    "v1": {"elements": (), "play_elements": (), "train": "Lizard-Rough-v1", "play": "Lizard-Rough-Play-v1"},
    "v2": {"elements": (), "play_elements": (), "train": "Lizard-Rough-v2", "play": "Lizard-Rough-Play-v2"},
    "v3": {"elements": _V3_DELTA, "play_elements": _V3_PLAY, "train": "Lizard-Rough-v3", "play": "Lizard-Rough-Play-v3"},
    "v4": {"elements": _V4_DELTA, "play_elements": _V3_PLAY, "train": "Lizard-Rough-v4", "play": "Lizard-Rough-Play-v4"},
    "v5": {"elements": _V5_DELTA, "play_elements": _SIR_PLAY, "train": "Lizard-Rough-v5", "play": "Lizard-Rough-Play-v5"},
    # v6/v8/v10 share one element list: v6.1 unlocks the spine (one yaml-sourced line), v8 and
    # v10 change no cfg field at all -- v8's flip + joint renames are the asset, v10's tilt
    # removal is the yaml flag components.terminations already reads. An empty delta is stated
    # as v6's list, never as ``None``: these recipes ARE declared, what they declare beyond v6
    # is nothing.
    "v6": {"elements": _V6_DELTA, "play_elements": _SIR_PLAY, "train": "Lizard-Rough-v6", "play": "Lizard-Rough-Play-v6"},
    "v8": {"elements": _V6_DELTA, "play_elements": _SIR_PLAY, "train": "Lizard-Rough-v8", "play": "Lizard-Rough-Play-v8"},
    "v10": {"elements": _V6_DELTA, "play_elements": _SIR_PLAY, "train": "Lizard-Rough-v10", "play": "Lizard-Rough-Play-v10"},
    # v11 hands the terrain curriculum to the joint particle filter; v12 adds the reset/obs
    # robustness package on top of it. v13 deliberately branches off v10, NOT off v12 -- it is the
    # single-variable kernel fix on the v10 line -- so its list is v6's plus its own element, and
    # the joint SIR / v12 resets are absent from it by construction.
    "v11": {"elements": _V11_DELTA, "play_elements": _JOINT_SIR_PLAY, "train": "Lizard-Rough-v11", "play": "Lizard-Rough-Play-v11"},
    "v12": {"elements": _V12_DELTA, "play_elements": _JOINT_SIR_PLAY, "train": "Lizard-Rough-v12", "play": "Lizard-Rough-Play-v12"},
    "v13": {"elements": _V13_DELTA, "play_elements": _SIR_PLAY, "train": "Lizard-Rough-v13", "play": "Lizard-Rough-Play-v13"},
    "v14": {"elements": _V14_DELTA, "play_elements": _SIR_PLAY, "train": "Lizard-Rough-v14", "play": "Lizard-Rough-Play-v14"},
}


def declared() -> list[str]:
    """The recipes whose whole delta is declared, so the builder can produce them."""
    return sorted(version for version, decl in RECIPES.items() if decl["elements"] is not None)


def pending() -> list[str]:
    """The recipes still expressed by their subclass body."""
    return sorted(version for version, decl in RECIPES.items() if decl["elements"] is None)


def build(version: str, *, play: bool = False):
    """The env cfg a recipe declares.

    Args:
        version: recipe version, a key of :data:`RECIPES`.
        play: the deterministic evaluation variant (no randomization, no curriculum).

    Returns:
        The env cfg, built from the shared wiring plus this recipe's declared elements. No
        version subclass is involved.

    Raises:
        ValueError: the recipe's delta is not declared yet, so producing a config would mean
            guessing the missing part.
        KeyError: the version is not a declared recipe at all.
    """
    if version not in RECIPES:
        raise KeyError(f"unknown recipe {version!r}; known: {sorted(RECIPES)}")
    elements = RECIPES[version]["elements"]
    if elements is None:
        raise ValueError(
            f"recipe {version!r}: its delta is not declared yet (declared: {declared()}),"
            f" so the builder cannot produce it without guessing"
        )
    # the version travels as the *field* it is: the shared wiring resolves every structural
    # choice from it, and a subclass that only restated it is exactly what this replaces
    cfg = teacher_env_cfg.LizardRoughTeacherEnvCfg(params_version=version)
    for name in elements:
        ELEMENTS[name](cfg)
    if play:
        # the shared PLAY wiring first, then the recipe's own evaluation-determinism elements:
        # they undo parts of what the recipe just built (a curriculum that would widen the range
        # mid-eval, a range that no longer has a curriculum to climb it)
        apply_play_wiring(cfg)
        for name in RECIPES[version]["play_elements"]:
            ELEMENTS[name](cfg)
    return cfg
