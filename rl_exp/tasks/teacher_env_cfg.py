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
come from rl_exp/versions/lizard/<version>/lizard_params.yaml (frozen per version).

The teacher ACTOR receives privileged simulation ground truth (Miki et al.
2022): clean height scan, true base velocities, foot contact flags, swing
durations and per-body mass on top of the noisy proprioceptive observations.
Rewards stay at the baseline (no incentive patches): if the teacher still
collapses under privilege, the incentive-escape-hatch hypothesis is confirmed
and the parked reward fixes get re-applied (plan §2.3).
"""

import math
import pathlib
from collections.abc import Callable
from typing import ClassVar

import torch

import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import patterns
from isaaclab.terrains import TerrainGeneratorCfg
from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    ActionsCfg,
    LocomotionVelocityRoughEnvCfg,
)
from isaaclab_tasks.utils import preset

from rl_exp.tasks import components, recipe_params, teacher_mdp
from rl_exp.tasks.play_utils import apply_play_wiring
from rl_exp.tasks.staged_curriculum import StageCfg, StagedCurriculumTerm, StagedCurriculumTermCfg

# this file lives at rl_exp/tasks/teacher_env_cfg.py -> exp root is parents[1]
_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]

# family layer constant -- own copy by the zero-family-import discipline (drift
# fails loudly: wrong path raises at cfg construction)
_VERSION_FAMILY = "lizard"

# ARCH_PLAN 2.1a: own copy of the main line's handle (same discipline as above -- drift raises
# at construction instead of reading a stale tree). The parameter path is derived from this
# handle by recipe_params, the single loader every recipe line shares.
_LINE_KEY = f"{_VERSION_FAMILY}/main"


def _load_params(version: str) -> dict:
    """Load the frozen main_params.yaml copy of ``version`` (never the dev yaml).

    Args:
        version: the frozen version handle this recipe reads.

    Returns:
        The resolved parameters of this line, as this caller's own tree.
    """
    return recipe_params.load(_LINE_KEY, version, frozen_only=True)


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


# v3.4 terrain (versions/lizard/v3/PLAN.md §6.6): Miki-aligned for the untrained
# v3 recipe only -- v1/v2 keep TEACHER_TERRAINS_CFG frozen above. Stair top
# raised 0.35 -> 0.55 m (~40% leg reach; paper demonstrates 30.5 cm ~= 75%
# ANYmal knee, training curriculum cap not given exactly -> estimate);
# stepping stones approximate the paper's open/ledged stair family (option b,
# user decision 2026-09-01): holes_depth gives true step-void geometry.
TEACHER_TERRAINS_CFG_V3 = TerrainGeneratorCfg(
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
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "pyramid_stairs_inv": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=0.2,
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=0.1,
            stone_width_range=(0.5, 0.9),
            stone_distance_range=(0.3, 0.7),
            stone_height_max=0.3,
            holes_depth=-1.0,
            platform_width=4.0,
            border_width=0.5,
        ),
        "boxes": terrain_gen.MeshRandomGridTerrainCfg(
            proportion=0.1, grid_width=0.9, grid_height_range=(0.08, 0.3), platform_width=4.0
        ),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            # v3.6: downsampled_scale 0.3 m (~2.3x the 0.13 m foot blade) -- the
            # stock 0.1 m pitch let flat foot pads perch on the rubble; noise
            # 0.06-0.2 m makes bumps the feet must wrap over
            proportion=0.2,
            noise_range=(0.06, 0.2),
            noise_step=0.04,
            border_width=0.5,
            downsampled_scale=0.3,
        ),
        "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.4), platform_width=4.0, border_width=0.5
        ),
        "hf_pyramid_slope_inv": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.4), platform_width=4.0, border_width=0.5
        ),
    },
)


# v4 terrain (versions/lizard/v4/PLAN.md): rubble re-scaled for the REAL sole.
# Measured from the asset (rl_foot collision mesh bbox, USD scale 1): each foot
# is a 0.46 m x 0.51 m flat plate (the "blade 0.131 m" in the FAMILY geometry
# memo is the kfe->foot bone length, not the sole), stand height ~0.94 m.
# v3.6's 0.3 m rubble pitch was SMALLER than the sole, so the plate bridged
# ~1.5x1.7 rubble cells and rode the envelope flat. IsaacLab 3.0
# random_uniform_terrain: each downsampled cell picks a height from the
# discrete set noise_range[0]..noise_range[1] stepped by noise_step (v3.6 =
# only 5 levels), then cells are spline-interpolated to the 0.1 m grid --
# further smoothing. v4: pitch >= sole width (one bump per foot, no perching
# across cells), taller spread, finer level set. Max local slope
# (0.36 - 0.10) / 0.5 = 0.52 m/m < slope_threshold 0.75: no wall correction.
TEACHER_TERRAINS_CFG_V4 = TerrainGeneratorCfg(
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
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "pyramid_stairs_inv": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=0.2,
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=0.1,
            stone_width_range=(0.5, 0.9),
            stone_distance_range=(0.3, 0.7),
            stone_height_max=0.3,
            holes_depth=-1.0,
            platform_width=4.0,
            border_width=0.5,
        ),
        "boxes": terrain_gen.MeshRandomGridTerrainCfg(
            proportion=0.1, grid_width=0.9, grid_height_range=(0.08, 0.3), platform_width=4.0
        ),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            # v4: downsampled_scale 0.5 m >= sole width 0.46 m -- one bump per
            # foot, the plate must wrap instead of bridging flat; heights
            # (0.10, 0.35) step 0.02 = 14 levels (v3.6: 5 levels 0.06..0.22);
            # top 0.35 m ~= 37% of the 0.94 m stand height, between stones
            # (0.3) and stairs (0.55) -- `用户拍板：2026-09-02`
            proportion=0.2,
            noise_range=(0.10, 0.35),
            noise_step=0.02,
            border_width=0.5,
            downsampled_scale=0.5,
        ),
        "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.4), platform_width=4.0, border_width=0.5
        ),
        "hf_pyramid_slope_inv": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.4), platform_width=4.0, border_width=0.5
        ),
    },
)


# v5.3 terrain (plan versions/lizard/v5/PLAN.md, SIR curriculum): the v4 grid
# + one flat type and a slightly steeper slope cap (v5.5, user decision
# 2026-09-03: 0.4 -> 0.45 rad ~ 25.8 deg). Terrain structure is pinned
# (7 v4 types + flat, 10 rows x 20 cols): the SIR curriculum redistributes
# spawn traffic over the FIXED grid (rows = difficulty particles through
# curriculum=True generation, columns = interchangeable instances) instead
# of regenerating terrains per particle draw -- the single user-approved
# deviation from Lee et al. 2020 Algorithm S1. Flat = bootstrap compensation
# the paper never needed (their gentlest Hills amplitude ~3 mm; our easiest
# rubble row is already 0.10 m, ~30x rougher): proportion 0.125 = an equal
# eighth type (~2 of 20 columns, ~9% of envs). It retires through the band
# semantics like any mastered type; its fixed column share persists
# afterwards, same as a fully-mastered paper terrain type keeps its
# trajectory share. The v4 proportions are kept (the generator normalizes
# the sum).
TEACHER_TERRAINS_CFG_V5 = TerrainGeneratorCfg(
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
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "pyramid_stairs_inv": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=0.2,
            step_height_range=(0.08, 0.55),
            step_width=0.7,
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        ),
        "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=0.1,
            stone_width_range=(0.5, 0.9),
            stone_distance_range=(0.3, 0.7),
            stone_height_max=0.3,
            holes_depth=-1.0,
            platform_width=4.0,
            border_width=0.5,
        ),
        "boxes": terrain_gen.MeshRandomGridTerrainCfg(
            proportion=0.1, grid_width=0.9, grid_height_range=(0.08, 0.3), platform_width=4.0
        ),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=0.2,
            noise_range=(0.10, 0.35),
            noise_step=0.02,
            border_width=0.5,
            downsampled_scale=0.5,
        ),
        "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.45), platform_width=4.0, border_width=0.5
        ),
        "hf_pyramid_slope_inv": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=0.1, slope_range=(0.0, 0.45), platform_width=4.0, border_width=0.5
        ),
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.125),
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
        # v8 anatomy rename (rear/tail/neck1-3 -> chest/neck/tail1-3): patterns
        # follow the CURRENT shared asset -- old task ids load it too, so the
        # base class must match the new names or every version fails to spawn
        joint_names=["chest_.*", "neck_.*", "tail[0-9]_.*"],
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
    # v3 keeps the v2 privileged-term set (priv 83); its recipe differences are
    # structural (obs groups / foot rings / rewards / DR), wired in the recipe's
    # declared elements (rl_exp.tasks.recipe)
    "v3": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v4 also keeps the v2/v3 privileged-term set (priv 83); its recipe
    # differences are terrain-only (rubble re-scaled for the real sole size)
    # plus the v3.6.1 collision-stack headroom removal, both wired in the
    # recipe's declared elements (rl_exp.tasks.recipe)
    "v4": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v5 also keeps the v2 privileged-term set (priv 83); its recipe
    # differences are reward-side only (anti-collapse package wired in the
    # recipe's declared elements on top of the v4 terrain)
    "v5": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v6 keeps the v2/v5 privileged-term set (priv 83); its only recipe
    # difference is the shared asset's axis correction (head +Y -> +X,
    # wired outside the code: blend/URDF/USD regeneration), spec unchanged
    "v6": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v8 keeps the v2-v6 privileged-term set (priv 83); its only recipe
    # difference is the shared asset's anatomy correction (+180 deg flip and
    # joint rename, wired outside the code: blend/URDF/USD regeneration),
    # spec unchanged
    "v8": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v10 keeps the v2-v8 privileged-term set (priv 83); its only recipe
    # difference is the tilt termination removal (wired in the recipe's
    # declared elements), spec unchanged. v9 is reserved for the
    # leg-break protocol line and does not exist yet.
    "v10": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v11 keeps the v10 privileged-term set (priv 83, obs 381): the joint
    # particle terrain curriculum touches terrain/curriculum/commands only,
    # never the obs contract.
    "v11": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v12 keeps the v10/v11 privileged-term set (priv 83, obs 381): the Miki
    # S8 robustness package (reset randomization, friction dips, height-ring
    # noise on the ACTOR extero group) never touches the priv obs contract.
    "v12": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v13 keeps the v10-v12 privileged-term set (priv 83, obs 381): the Miki
    # symmetric tracking-kernel swap touches the reward contract only, never
    # the obs contract.
    "v13": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v14 keeps the v13 set verbatim: the fall gate is a termination, so it
    # touches neither the obs contract nor the reward contract.
    "v14": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
}


@configclass
class LizardRoughTeacherEnvCfg(LocomotionVelocityRoughEnvCfg):
    """Teacher: perceptive + privileged actor, baseline rewards (latest recipe).

    Frozen task ids never use this class: each is built from its declared recipe
    (``rl_exp.tasks.recipe``, materialized as a class in ``rl_exp.tasks.recipe_tasks``),
    so bumping ``params_version`` here cannot retroactively change an old recipe.

    Privileged obs per Miki et al. 2022 table + two legacy extras (true base
    velocity, per-body mass); full layout table in FAMILY.md. Obs dim 308.

    ``params_version`` is a plain class attribute (NOT a configclass field, so
    it is never deep-copied): the latest recipe lives here, and every declared recipe
    stamps its own value for working-tree reproducibility -- running an old task id
    must always rebuild the old recipe, never silently pick up code drift from newer
    versions. Which incremental terms a version includes is governed by
    ``TEACHER_PRIVILEGED_SPEC`` above.
    """

    # declared owner: the recipe line every gate routes by (ClassVar so this statement
    # about the recipe does not enter the config snapshot and move the golden)
    params_line: ClassVar[str] = _LINE_KEY

    # True on the PLAY variants of the curriculum-gated recipes: evaluation has no curriculum to
    # widen the range on a good policy, so they pin the full forward range instead (the rule
    # itself lives in components.commands). ClassVar so this statement about the recipe does not
    # enter the config snapshot and move the golden.
    PLAY_PINS_COMMAND_RANGE: ClassVar[bool] = False

    # v2 = latest (paper-aligned privileged obs); see versions/lizard/main/v2/NOTES.md
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
        # terrain: one writer for the whole block -- which payload a recipe picks and the row
        # it spawns at are declared in components.TERRAIN_BY_RECIPE.
        for name, value in components.terrain(
            self.params_version,
            params=params,
            payloads={
                "TEACHER_TERRAINS_CFG": TEACHER_TERRAINS_CFG,
                "TEACHER_TERRAINS_CFG_V3": TEACHER_TERRAINS_CFG_V3,
                "TEACHER_TERRAINS_CFG_V4": TEACHER_TERRAINS_CFG_V4,
                "TEACHER_TERRAINS_CFG_V5": TEACHER_TERRAINS_CFG_V5,
            },
        ).items():
            setattr(self.scene.terrain, name, value)
        # height sensing: one writer for the whole component -- v1/v2 the ground grid
        # scanner, v3+ four per-foot rings with their geometry from the yaml. The
        # recipes that swapped form used to null the scanner here and build the rings
        # in their own subclass; the choice resolves by version now, so no subclass
        # writes any of these names.
        for name, sensor in components.height_sensing(
            self.params_version,
            decimation=self.decimation,
            dt=self.sim.dt,
            params=params,
            ring_pattern_cls=RingPatternCfg,
        ).items():
            setattr(self.scene, name, sensor)

        # --- rewards / terminations: lizard body-name patterns from SSOT ---
        self.rewards.feet_air_time.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["foot_body_names"]
        )
        self.rewards.undesired_contacts.params["sensor_cfg"] = SceneEntityCfg(
            "contact_forces", body_names=names_params["undesired_contact_body_names"]
        )
        # terminations: one writer for the whole component -- a recipe narrows the inherited
        # base-contact term, drops it, or adds tilt / roll-over gates (components.terminations);
        # no subclass writes these names any more.
        for name, term in components.terminations(
            self.params_version,
            params=params,
            base_contact=self.terminations.base_contact,
            base_body=base_name,
        ).items():
            setattr(self.terminations, name, term)

        # commands: one writer for the term -- the per-recipe forward range, and the replacement
        # term the particle recipes use, are declared in components.COMMAND_RANGE.
        for name, command in components.commands(
            self.params_version,
            params=params,
            base_velocity=self.commands.base_velocity,
            pins_full_range=self.PLAY_PINS_COMMAND_RANGE,
        ).items():
            setattr(self.commands, name, command)

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

        # observations: one writer for the groups -- which terms exist, which group each one
        # belongs to, and how a recipe's version prunes them, are all declared in
        # components.observations (the spec table above says which incremental privileged terms
        # a recipe includes).
        for name, group in components.observations(
            self.params_version,
            params=params,
            base_policy=self.observations.policy,
            spec=TEACHER_PRIVILEGED_SPEC,
        ).items():
            setattr(self.observations, name, group)


@configclass
class LizardRoughTeacherEnvCfg_PLAY(LizardRoughTeacherEnvCfg):
    """Play variant: smaller terrain grid, curriculum off, randomization off."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils;
        # play_utils is deliberately dependency-free so the teacher snapshot keeps
        # its zero-family-import discipline)
        apply_play_wiring(self)










# --- v3: paper-alignment layer (three obs groups + foot rings + D1-D4 package) ---


def ring_pattern(cfg: "RingPatternCfg", device: str) -> tuple[torch.Tensor, torch.Tensor]:
    """Concentric-ring ray pattern for per-foot terrain scanning (paper S1).

    Args:
        cfg: The ring pattern configuration.
        device: Device to create the pattern on.

    Returns:
        Ray starting positions [num_rays, 3] and directions [num_rays, 3].
    """
    if len(cfg.ring_counts) != len(cfg.ring_radii):
        raise ValueError(
            f"ring_counts {cfg.ring_counts} and ring_radii {cfg.ring_radii} must pair 1:1."
        )
    starts = []
    for count, radius in zip(cfg.ring_counts, cfg.ring_radii):
        theta = torch.arange(count, device=device) * (2.0 * math.pi / count)
        ring = torch.zeros(count, 3, device=device)
        ring[:, 0] = radius * torch.cos(theta)
        ring[:, 1] = radius * torch.sin(theta)
        starts.append(ring)
    ray_starts = torch.cat(starts, dim=0)
    ray_directions = torch.zeros_like(ray_starts)
    ray_directions[:, :] = torch.tensor(list(cfg.direction), device=device)
    return ray_starts, ray_directions


@configclass
class RingPatternCfg(patterns.PatternBaseCfg):
    """Concentric-ring pattern: ``ring_counts[i]`` points on ``ring_radii[i]`` [m].

    Paper default: counts (6, 8, 10, 12, 16) x radii (0.08..0.48) = 52 points
    per foot; the 40-point fallback is a yaml-only change (network input dims
    follow the env).
    """

    func: Callable = ring_pattern

    ring_counts: tuple[int, ...] = (6, 8, 10, 12, 16)
    """Number of points on each ring."""
    ring_radii: tuple[float, ...] = (0.08, 0.16, 0.26, 0.36, 0.48)
    """Ring radii [m]."""
    direction: tuple[float, float, float] = (0.0, 0.0, -1.0)
    """Ray direction (straight down)."""











        # r_fc sign fix rides the V3 wiring: foot_clearance.weight is read from
        # THIS version's yaml at V3.__post_init__ time (params_version="v5"),
        # and the v5 yaml copy carries weight: -0.003.












        # D1 removal is yaml-driven (v10.tilt_terminate: null) and owned by
        # components.terminations, which reads the same flag in the single writer.





        # v11 command: the particle-sourced term -- a field-by-field copy of the v5-wired term
        # (whose ranges already carry the yaml narrowing) -- is declared in
        # components.COMMAND_RANGE.














