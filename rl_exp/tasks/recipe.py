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
    "play_drops_speed_curriculum": play_drops_speed_curriculum,
    "play_pins_full_command_range": play_pins_full_command_range,
    "play_drops_sir_terrain_curriculum": play_drops_sir_terrain_curriculum,
}

# What each recipe is: the ordered elements it applies on top of the shared wiring (and, for its
# PLAY variant, the extra ones after the shared PLAY wiring), plus the registered tasks it claims
# to reproduce -- named, not derived from the version string, because a task id is a published
# name and a rename must not silently re-point this gate at nothing.
RECIPES: dict[str, dict] = {
    "v1": {"elements": (), "play_elements": (), "train": "Lizard-Rough-v1", "play": "Lizard-Rough-Play-v1"},
    "v2": {"elements": (), "play_elements": (), "train": "Lizard-Rough-v2", "play": "Lizard-Rough-Play-v2"},
    "v3": {
        "elements": ("v3_contact_headroom", "v3_speed_curriculum", "v3_anti_drag_reward", "v3_ck_clock"),
        "play_elements": ("play_drops_speed_curriculum", "play_pins_full_command_range"),
        "train": "Lizard-Rough-v3",
        "play": "Lizard-Rough-Play-v3",
    },
    # v4's delta is v3's plus one line: the stock contact stack, re-tested on coarser rubble.
    "v4": {
        "elements": (
            "v3_contact_headroom",
            "v3_speed_curriculum",
            "v3_anti_drag_reward",
            "v3_ck_clock",
            "v4_stock_contact_stack",
        ),
        "play_elements": ("play_drops_speed_curriculum", "play_pins_full_command_range"),
        "train": "Lizard-Rough-v4",
        "play": "Lizard-Rough-Play-v4",
    },
    # v5 rebuilds the reward economics and hands the terrain curriculum to SIR. Its PLAY
    # variant keeps the yaml's forward-only window: the v3/v4 PLAY elements are deliberately
    # absent (play_drops_speed_curriculum would null a curriculum v5 already dropped, and
    # play_pins_full_command_range would pin (-1, 5) where the frozen PLAY recipe says (0, 3)),
    # so only the SIR rollout guard is left.
    "v5": {
        "elements": (
            "v3_contact_headroom",
            "v3_speed_curriculum",
            "v3_anti_drag_reward",
            "v3_ck_clock",
            "v4_stock_contact_stack",
            "v5_drops_speed_curriculum",
            "v5_reward_package",
            "v5_sir_terrain_curriculum",
        ),
        "play_elements": ("play_drops_sir_terrain_curriculum",),
        "train": "Lizard-Rough-v5",
        "play": "Lizard-Rough-Play-v5",
    },
    "v6": {"elements": None},
    "v8": {"elements": None},
    "v10": {"elements": None},
    "v11": {"elements": None},
    "v12": {"elements": None},
    "v13": {"elements": None},
    "v14": {"elements": None},
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
