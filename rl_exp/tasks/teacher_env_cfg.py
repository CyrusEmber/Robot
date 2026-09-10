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

import torch
import yaml

import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.sensors import RayCasterCfg, patterns
from isaaclab.terrains import TerrainGeneratorCfg
from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    ActionsCfg,
    LocomotionVelocityRoughEnvCfg,
)
from isaaclab_tasks.utils import preset

from rl_exp.tasks import teacher_mdp
from rl_exp.tasks.param_grid_terrain import build_param_grid_terrain_cfg
from rl_exp.tasks.play_utils import apply_play_wiring
from rl_exp.tasks.staged_curriculum import StageCfg, StagedCurriculumTerm, StagedCurriculumTermCfg

# this file lives at rl_exp/tasks/teacher_env_cfg.py -> exp root is parents[1]
_RL_EXP_DIR = pathlib.Path(__file__).resolve().parents[1]

# family layer constant -- own copy by the zero-family-import discipline (drift
# fails loudly: wrong path raises at cfg construction)
_VERSION_FAMILY = "lizard"


def _load_params(version: str) -> dict:
    """Load the frozen lizard_params.yaml copy of ``version`` (never the dev yaml)."""
    path = _RL_EXP_DIR / "versions" / _VERSION_FAMILY / version / "lizard_params.yaml"
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
    # structural (obs groups / foot rings / rewards / DR), wired in
    # LizardRoughTeacherEnvCfg_V3
    "v3": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v4 also keeps the v2/v3 privileged-term set (priv 83); its recipe
    # differences are terrain-only (rubble re-scaled for the real sole size)
    # plus the v3.6.1 collision-stack headroom removal, both wired in
    # LizardRoughTeacherEnvCfg_V4
    "v4": {
        "foot_contact_forces",
        "foot_contact_normals",
        "foot_friction",
        "thigh_shank_contacts",
        "base_external_wrench",
    },
    # v5 also keeps the v2 privileged-term set (priv 83); its recipe
    # differences are reward-side only (anti-collapse package wired in
    # LizardRoughTeacherEnvCfg_V5 on top of the v4 terrain)
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
    # difference is the tilt termination removal (wired in
    # LizardRoughTeacherEnvCfg_V10), spec unchanged. v9 is reserved for the
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
}


@configclass
class LizardRoughTeacherEnvCfg(LocomotionVelocityRoughEnvCfg):
    """Teacher: perceptive + privileged actor, baseline rewards (latest recipe).

    Frozen task ids use the per-version subclasses (_V1/_V2/_V3), never this
    class, so bumping ``params_version`` here cannot retroactively change an
    old recipe.

    Privileged obs per Miki et al. 2022 table + two legacy extras (true base
    velocity, per-body mass); full layout table in FAMILY.md. Obs dim 308.

    ``params_version`` is a plain class attribute (NOT a configclass field, so
    it is never deep-copied): the latest recipe lives here, and per-version
    subclasses below override it for working-tree reproducibility -- running
    an old task id must always rebuild the old recipe, never silently pick
    up code drift from newer versions. Which incremental terms a version
    includes is governed by ``TEACHER_PRIVILEGED_SPEC`` above.
    """

    # v2 = latest (paper-aligned privileged obs); see versions/lizard/v2/NOTES.md
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
class LizardRoughTeacherEnvCfg_V2(LizardRoughTeacherEnvCfg):
    """v2 recipe, reproducible from the working tree (obs 308).

    Same pinning discipline as v1/v3: the task id must rebuild the v2 recipe
    even after the base class moves on to a newer params_version (the base is
    the "latest" pointer, not a frozen entry).
    """

    params_version = "v2"


@configclass
class LizardRoughTeacherEnvCfg_V2_PLAY(LizardRoughTeacherEnvCfg_V2):
    """v2 play variant: obs 308, no randomization, curriculum off."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
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


@configclass
class LizardRoughTeacherEnvCfg_V3(LizardRoughTeacherEnvCfg):
    """v3 recipe: paper-aligned teacher (obs 381 = proprio 90 / extero 208 / priv 83).

    Differences vs v2 (versions/lizard/v3/PLAN.md):
    * extero = 4 per-foot ring scanners (52 points/foot, yaw-aligned) replacing
      the 135-point base grid scan; obs delivered as THREE named groups
      (proprio/extero/priv) -- the model-side contract (teacher_networks.py)
    * D1 tilt termination; D2 anti-drag r_fc replaces the feet_air_time reward;
      D3 c_k penalty curriculum; D4 reset-mode c_k-scaled DR (mass/com/inertia/
      gains/joint params -- friction stays startup so the foot_friction_truth
      obs cache keeps its startup-only semantics, F3 deviation note)
    * v3.4 terrain: Miki-aligned (stairs to 0.55 m + stepping stones), teacher
      snapshot only -- family and v1/v2 generators untouched
    """

    params_version = "v3"

    def __post_init__(self):
        super().__post_init__()
        # v3.4: swap in the Miki-aligned terrain (base __init__ wired the v1/v2
        # frozen generator; swapping after super() is the same late-replace the
        # base itself does -- curriculum=True already set on the new cfg)
        self.scene.terrain.terrain_generator = TEACHER_TERRAINS_CFG_V3
        # v3.5: paper curriculum prerequisite -- spawn at the EASIEST row and
        # let stock terrain_levels_vel (per-robot success-driven row promotion)
        # climb; the discrete stand-in for the particle-filter curriculum only
        # holds if training starts from level 0 (v1/v2 snapshots keep 5: frozen)
        self.scene.terrain.max_init_terrain_level = 0

        # --- v3.6.1: PhysX contact buffer headroom ---
        # belly contact is now persistent by design (base_contact termination
        # removed; a flat-belly robot is not tilted, so tilt does not fire
        # either) and the v3 terrain adds stepping-stone contact pairs. The
        # stock 2**26 collision stack overflows at 4096 envs and PhysX drops
        # contacts silently -> nondeterministic physics. 2**28 gives 4x
        # headroom; v1/v2 frozen cfgs keep the stock value.
        self.sim.physics.default.gpu_collision_stack_size = 2**28

        # --- v3.6: staged speed curriculum replaces the (-1, 1) paper override ---
        # v1 replay showed foot-pad creeping is the optimum at a 1 m/s command
        # cap; widen -1..2 -> 5 gated by success_rate >= 0.8 sustained 120 s,
        # so stages the robot cannot track are never applied (user decision
        # 2026-09-01). Stage 0 also seeds the cfg range so the first resamples
        # already match the curriculum.
        self.commands.base_velocity.ranges.lin_vel_x = (-1.0, 2.0)
        self.curriculum.speed_curriculum = StagedCurriculumTermCfg(
            func=StagedCurriculumTerm,
            stages=[
                StageCfg(command_ranges={"lin_vel_x": (-1.0, 2.0)}, metric_threshold=0.8, sustain_s=120.0),
                StageCfg(command_ranges={"lin_vel_x": (-1.0, 3.0)}, metric_threshold=0.8, sustain_s=120.0),
                StageCfg(command_ranges={"lin_vel_x": (-1.0, 4.0)}, metric_threshold=0.8, sustain_s=120.0),
                StageCfg(command_ranges={"lin_vel_x": (-1.0, 5.0)}),
            ],
        )

        # --- v3.6: belly-contact termination removed (executes D0-6) ---
        # the sprawled body sits low, so base contact is a crouch signal, not a
        # fall -- and the trained robot never flips. Contact stays penalized
        # by rewards.undesired_contacts (user decision 2026-09-01: penalty only).
        self.terminations.base_contact = None

        params = _load_params(self.params_version)
        v3 = params["v3"]
        ring = v3["foot_ring"]
        tilt = v3["tilt_terminate"]
        rfc = v3["r_fc"]
        ck = v3["curriculum_ck"]

        # --- C1/C2: per-foot ring casters replace the base height scanner ---
        # (the casters also register /World/ground in RayCaster.meshes, which
        # the priv foot_contact_normals / r_fc raycasts rely on)
        self.scene.height_scanner = None
        pattern_cfg = RingPatternCfg(
            ring_counts=tuple(ring["ring_counts"]),
            ring_radii=tuple(ring["ring_radii"]),
        )
        update_period = self.decimation * self.sim.dt
        for foot in ("lf", "rf", "rl", "rr"):
            setattr(
                self.scene,
                f"{foot}_foot_ring",
                RayCasterCfg(
                    prim_path=f"{{ENV_REGEX_NS}}/Robot/Geometry/{foot}_foot",
                    offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, ring["ray_offset_z"])),
                    ray_alignment="yaw",
                    pattern_cfg=pattern_cfg,
                    debug_vis=False,
                    mesh_prim_paths=["/World/ground"],
                    update_period=update_period,
                ),
            )

        # --- obs restructure: single flat policy group -> three named groups ---
        # group attr insertion order == term concat order (manager reads __dict__);
        # the extero foot order (lf, rf, rl, rr) is the network reshape contract
        proprio_group = ObservationGroupCfg()
        for name in (
            "base_lin_vel", "base_ang_vel", "projected_gravity", "velocity_commands",
            "joint_pos", "joint_vel", "actions",
        ):
            setattr(proprio_group, name, getattr(self.observations.policy, name))
        self.observations.proprio = proprio_group

        extero_group = ObservationGroupCfg()
        for foot in ("lf", "rf", "rl", "rr"):
            setattr(
                extero_group,
                f"{foot}_foot_ring",
                ObsTerm(
                    func=mdp.height_scan,
                    params={
                        "sensor_cfg": SceneEntityCfg(f"{foot}_foot_ring"),
                        "offset": ring["scan_offset"],
                    },
                    clip=tuple(ring["clip"]),
                ),
            )
        self.observations.extero = extero_group

        priv_group = ObservationGroupCfg()
        for name in (
            "base_lin_vel_true", "base_ang_vel_true", "foot_contact", "feet_air_time",
            "body_mass", "foot_contact_forces", "foot_contact_normals", "foot_friction",
            "thigh_shank_contacts", "base_external_wrench",
        ):
            setattr(priv_group, name, getattr(self.observations.policy, name))
        self.observations.priv = priv_group
        self.observations.policy = None

        # --- D1: tilt termination ---
        self.terminations.tilt = DoneTerm(
            func=teacher_mdp.tilt_terminate,
            params={"gravity_z_limit": tilt["gravity_z_limit"]},
        )

        # --- D2: anti-drag foot clearance replaces the feet_air_time reward ---
        # (the feet_air_time OBS term stays in the priv group)
        self.rewards.feet_air_time = None
        self.rewards.foot_clearance = RewTerm(
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

        # --- D3/D4: c_k schedule + in-place func swaps (names stay stable so
        # PLAY wiring / DR event list keep matching; loop form keeps these
        # recipe-layer swaps out of the family-vs-teacher wiring parity text
        # check, which guards the BASE wiring freeze, not version recipes) ---
        self.events.init_ck = EventTerm(
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
            getattr(self.rewards, name).func = func
        # base_com lives inside a preset wrapper; .default is the physx branch
        com_term = self.events.base_com.default
        com_term.func = teacher_mdp.randomize_rigid_body_com_ck
        com_term.mode = "reset"
        for name, func in (
            ("add_base_mass", teacher_mdp.randomize_rigid_body_mass_ck),
            ("randomize_limb_mass", teacher_mdp.randomize_rigid_body_mass_ck),
            ("randomize_inertia", teacher_mdp.randomize_rigid_body_inertia_ck),
            ("randomize_actuator_gains", teacher_mdp.randomize_actuator_gains_ck),
            ("randomize_joint_params", teacher_mdp.randomize_joint_parameters_ck),
        ):
            term = getattr(self.events, name)
            term.func = func
            term.mode = "reset"


@configclass
class LizardRoughTeacherEnvCfg_V3_PLAY(LizardRoughTeacherEnvCfg_V3):
    """v3 play variant: obs 381, no randomization, curriculum off."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # v3.6: eval determinism -- the staged speed curriculum would widen
        # command ranges mid-eval on a good policy; fix the full ambition range
        # instead and drop the curriculum term
        self.curriculum.speed_curriculum = None
        self.commands.base_velocity.ranges.lin_vel_x = (-1.0, 5.0)


@configclass
class LizardRoughTeacherEnvCfg_V4(LizardRoughTeacherEnvCfg_V3):
    """v4 recipe: v3 with the rubble re-scaled for the real 0.46 x 0.51 m soles.

    Differences vs v3 (versions/lizard/v4/PLAN.md):
    * random_rough: pitch 0.3 -> 0.5 m (>= sole width 0.46 m: one bump per
      foot, no bridging), heights (0.06, 0.2)/step 0.04 -> (0.10, 0.35)/step
      0.02 (5 -> 14 levels; top 0.35 m ~ 37% stand height)
    * v3.6.1 collision-stack headroom removed: the 2**28 override may have
      masked the real cause of the v3.6.1 contact overflow (flat soles lying
      flush on a fine heightfield = maximal contact-pair count). v4 re-tests
      the stock 2**26 with the coarser terrain
    """

    params_version = "v4"

    def __post_init__(self):
        super().__post_init__()
        # v4: rubble coarse enough for the real soles (TEACHER_TERRAINS_CFG_V4)
        self.scene.terrain.terrain_generator = TEACHER_TERRAINS_CFG_V4
        # v4: drop the v3.6.1 PhysX headroom -- re-test the stock 2**26 with
        # the coarser terrain. WARNING (user decision 2026-09-02): INSPECT THE
        # TERRAIN BEFORE LAUNCHING TRAINING/TESTS. If the overflow comes back
        # (PhysX drops contacts silently -> nondeterministic physics), the
        # root cause is contact density (flat soles on a fine heightfield),
        # NOT buffer size -- do NOT re-raise the stack; simplify the contact
        # geometry (coarser sole collision / terrain) instead.
        self.sim.physics.default.gpu_collision_stack_size = 2**26


@configclass
class LizardRoughTeacherEnvCfg_V4_PLAY(LizardRoughTeacherEnvCfg_V4):
    """v4 play variant: obs 381, no randomization, curriculum off."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # v3.6: eval determinism -- the staged speed curriculum would widen
        # command ranges mid-eval on a good policy; fix the full ambition range
        # instead and drop the curriculum term
        self.curriculum.speed_curriculum = None
        self.commands.base_velocity.ranges.lin_vel_x = (-1.0, 5.0)


@configclass
class LizardRoughTeacherEnvCfg_V5(LizardRoughTeacherEnvCfg_V4):
    """v5 recipe: reward-side anti-collapse package + SIR terrain curriculum.

    v3/v4 trained to a foot-pad creeping optimum (15555 iters, success_rate
    pinned at the standstill freeload baseline, terrain levels frozen at 1.27,
    foot_clearance reward never above 5e-5). Root causes closed here
    (versions/lizard/v5/PLAN.md, user decision 2026-09-03):
    * r_fc weight sign flipped positive->negative (it shipped as a REWARD for
      low-hanging swing feet; the v5 yaml copy carries the fix, so the frozen
      v3/v4 recipes keep their original behavior)
    * r_slip (feet_slide_ck): contact-foot sliding penalty, c_k-scaled -- the
      paper's only direct anti-creeping term, dropped from v3 by an erratum
    * r_co narrowed to thigh/shank (HFE/KFE links), c_k-scaled; the base body
      moves to a dedicated continuous belly-force penalty (constant weight:
      lying flat must never become free as c_k anneals), HAA/spine exempt
      (user decision)
    * linear tracking track_lin_vel_xy_lin (Cheng et al. 2023 Eq. 2 form)
      replaces track_lin_vel_xy_yaw_frame_exp: standing scores 0, reversal
      scores negative -- the exp kernel let |v_cmd| < 0.5 stand still for half
      the command distribution
    * commands forward-only lin_vel_x (0, 3) with the staged speed curriculum
      removed (it was pinned at stage 0 by the freeloaded success_rate anyway)
    * v5.3: SIR terrain curriculum (Lee et al. 2020 Alg. S1) replaces stock
      terrain_levels_vel -- spawn traffic redistributed per measured success
      band on the fixed 8-type grid (v4 types + flat bootstrap column)
    Obs/network contract unchanged: three groups 90/208/83 = 381.
    """

    params_version = "v5"

    def __post_init__(self):
        super().__post_init__()
        params = _load_params(self.params_version)
        v5 = params["v5"]
        base_name = params["robot"]["base_body_name"]

        # commands: forward-only ambition range, no staged speed curriculum
        # (stage 0's (-1, 2) window kept a 50% standstill-freeload band under
        # the exp kernel; the linear kernel below needs no range gating)
        self.commands.base_velocity.ranges.lin_vel_x = tuple(v5["commands"]["lin_vel_x"])
        self.curriculum.speed_curriculum = None

        # --- v5.3: SIR particle terrain curriculum (Lee et al. 2020 Alg. S1,
        # discrete adaptation; plan versions/lizard/v5/PLAN.md) ---
        # grid = v4 + one flat type; rows = difficulty particles, envs respawn
        # per reset on the type's particle set. The v3.5 "spawn at easiest
        # row" prerequisite dies here: SIR samples uniformly at start (paper
        # line 1), so initial terrain levels are uniform too.
        self.scene.terrain.terrain_generator = TEACHER_TERRAINS_CFG_V5
        self.scene.terrain.max_init_terrain_level = None
        sir = v5["terrain_curriculum"]
        self.curriculum.terrain_levels = teacher_mdp.SIRTerrainCurriculumCfg(
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

        # linear velocity tracking: EP-style normalized kernel replaces the exp
        self.rewards.track_lin_vel_xy_exp = None
        self.rewards.track_lin_vel_xy_lin = RewTerm(
            func=teacher_mdp.track_lin_vel_xy_lin,
            weight=v5["track_goal_vel"]["weight"],
            params={
                "command_name": "base_velocity",
                "min_speed": v5["track_goal_vel"]["min_speed"],
            },
        )

        # r_slip: contact-foot sliding penalty, c_k-scaled (paper S7). Both cfgs
        # must be explicit params so the manager resolves body_ids (a defaulted
        # SceneEntityCfg stays unresolved and indexes with body_ids=None).
        self.rewards.feet_slide = RewTerm(
            func=teacher_mdp.feet_slide_ck,
            weight=v5["r_slip"]["weight"],
            params={
                "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
                "asset_cfg": SceneEntityCfg("robot", body_names=".*_foot"),
            },
        )

        # r_co: legs-only + c_k (paper r_co penalizes thigh/shank). The body
        # list itself comes from the v5 yaml names section (base_class wiring).
        self.rewards.undesired_contacts.func = teacher_mdp.undesired_contacts_ck

        # belly: continuous force-proportional penalty, constant weight
        self.rewards.belly_contact_force = RewTerm(
            func=teacher_mdp.belly_contact_force,
            weight=v5["belly_contact_force"]["weight"],
            params={
                "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[base_name]),
                "force_scale": v5["belly_contact_force"]["force_scale"],
            },
        )

        # r_fc sign fix rides the V3 wiring: foot_clearance.weight is read from
        # THIS version's yaml at V3.__post_init__ time (params_version="v5"),
        # and the v5 yaml copy carries weight: -0.003.


@configclass
class LizardRoughTeacherEnvCfg_V5_PLAY(LizardRoughTeacherEnvCfg_V5):
    """v5 play variant: obs 381, no randomization, no curriculum.

    The speed curriculum is already absent in v5 and the command range is the
    fixed (0, 3) ambition window, so PLAY needs only the shared wiring. The
    SIR terrain curriculum is dropped too: replay keeps its initial terrain
    assignment (fixed grid, no traffic redistribution mid-eval).
    """

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # v5.3: SIR would reassign spawn origins per episode based on replay
        # outcomes -- deterministic eval must not roam
        self.curriculum.terrain_levels = None


@configclass
class LizardRoughTeacherEnvCfg_V6(LizardRoughTeacherEnvCfg_V5):
    """v6 recipe: asset axis correction + spine/tail unlock, reward/obs unchanged.

    The v5 first run walked sideways (crab-walk): the lizard URDF's long axis
    was Y (neck at +y, legs sprawling along x) while the velocity task pays
    for motion along base +X -- so the policy strafed along its own right
    side, exactly as rewarded (trainLinVelXY tracked it as healthy progress).
    v6 regenerates the shared asset with the body rigidly rotated -90 deg
    about Z (blend SSOT via blender/rotate_rig.py; generate_urdf AXIS_MAP
    rotated with it; locks refreshed tree-wide in the same commit). The
    version yaml stays byte-identical to v5 (versioning.mdc §A -- trained v5
    is immutable, asset fix opens v6).

    v6.1 action-space change (user decision 2026-09-07): the whole spine term
    (rear + neck + tail, 10 joints) unlocks at the yaml ``spine_scale`` --
    v1-v5 hardcoded 0.0 left the spine/tail policy-frozen and passively
    wobbling under PD 150/10. Obs groups (90/208/83) and the 26-dim action
    layout are unchanged; only the spine channels become live.
    """

    params_version = "v6"

    def __post_init__(self):
        super().__post_init__()
        # spine_scale comes from THIS version's yaml (0.25), so v1-v5 keep the
        # class-default 0.0 and their recipes rebuild unchanged
        params = _load_params(self.params_version)
        self.actions.joint_pos_spine.scale = params["action"]["spine_scale"]


@configclass
class LizardRoughTeacherEnvCfg_V6_PLAY(LizardRoughTeacherEnvCfg_V6):
    """v6 play variant: same as v5 PLAY (no randomization, no curriculum)."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # SIR reassigns spawn origins per episode -- deterministic eval must not roam
        self.curriculum.terrain_levels = None


@configclass
class LizardRoughTeacherEnvCfg_V8(LizardRoughTeacherEnvCfg_V6):
    """v8 recipe: anatomy-correct asset (flip + rename), reward/obs unchanged.

    The v6 first run walked tail-first (probe: displacement solidly along base
    +X under forward commands, yet the GUI showed the head trailing): the rig's
    bone names were 180 deg off the model's anatomy -- the "neck1-3" chain is
    the tail (build_rig.py ``antenna_tip``), the "tail_yaw/tail_pitch" chain
    carries the sphere HEAD (``sphere_tip``), and the leg names were
    front/rear + left/right swapped. v6 rotated the NAME-head onto task +X,
    which is anatomically the tail, so the policy walked exactly as paid --
    tail-first. v8 regenerates the shared asset with a further +180 deg Z
    rotation (net +90 from the pre-v6 blend: sphere head -y -> +x, antenna
    tail -> -x) and renames all 26 joints to anatomy
    (blender/rename_flip_v8.py; generate_urdf AXIS_MAP flipped with it;
    every version yaml migrated in the same commit). Reward/obs/action
    structure stays byte-identical to v6.2 -- only joint NAMES and the asset
    orientation change, so the 90/208/83 obs groups and the 26-dim action
    layout are unchanged.
    """

    params_version = "v8"


@configclass
class LizardRoughTeacherEnvCfg_V8_PLAY(LizardRoughTeacherEnvCfg_V8):
    """v8 play variant: same as v6 PLAY (no randomization, no curriculum)."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # SIR reassigns spawn origins per episode -- deterministic eval must not roam
        self.curriculum.terrain_levels = None


@configclass
class LizardRoughTeacherEnvCfg_V10(LizardRoughTeacherEnvCfg_V8):
    """v10 recipe: tilt termination removed (single-variable fix).

    Diagnosis (2026-09-09; v8.1 killed at iter 7700): ``Episode_Termination/
    tilt`` sat at 0.60 (v8.1) / 0.76 (v6) -- the v3 ``tilt_terminate`` pg_z
    limit (instantaneous total tilt > 53 deg, no dwell window) killed
    legitimate pitch (terrain slopes <= 26 deg, vaulting, spine articulation)
    as "falls". Most episodes truncated early, SIR success_rate pinned at
    0.019 (success requires surviving to timeout), terrain curriculum and
    velocity learning starved. v10 deletes the term entirely so fallen states
    stay in the rollout data: the belly_contact_force penalty (-0.5/step)
    plus zero tracking supplies the get-up gradient, and the 2 m tail +
    sprawled legs carry the ground righting apparatus (lizards self-right in
    seconds). Only time_out terminates. Everything else is byte-identical to
    v8.1. Pre-registered counter-hack (v10 yaml): sustained belly contact
    with high tracking -> raise the belly_contact_force weight.
    """

    params_version = "v10"

    def __post_init__(self):
        super().__post_init__()
        # D1 removal, yaml-driven (v10.tilt_terminate: null -> no tilt term)
        if _load_params(self.params_version)["v10"]["tilt_terminate"] is None:
            self.terminations.tilt = None


@configclass
class LizardRoughTeacherEnvCfg_V10_PLAY(LizardRoughTeacherEnvCfg_V10):
    """v10 play variant: same as v8 PLAY (no randomization, no curriculum)."""

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # SIR reassigns spawn origins per episode -- deterministic eval must not roam
        self.curriculum.terrain_levels = None


@configclass
class LizardRoughTeacherEnvCfg_V11(LizardRoughTeacherEnvCfg_V10):
    """v11 recipe: joint particle terrain curriculum (plan versions/lizard/v11/PLAN.md).

    Replaces the v5 scalar-row SIR with the joint (terrain param combo,
    velocity bucket) particle filter over a frozen param-sampled grid
    (param_grid_terrain.py; every combination becomes one sub-terrain with
    single-value ranges, so the stock difficulty interpolation is a no-op --
    the fix for the diagonal problem). Measurement returns to the paper's
    per-state-transition Tr (Lee et al. 2020 Eq. 2/3/7) -- family PLAN
    ledger #15 option a; velocity enters the particle (repo extension: the
    paper samples commands randomly and keeps them out). lin_vel_x now
    comes from the particle via ParticleVelocityCommand, with mid-episode
    resampling disabled so a whole episode keeps one pairing (reset order:
    curriculum compute at :369 precedes command resample at :394). All
    difficulty levels and curriculum knobs live in the v11 yaml section
    (SSOT). The v5 SpawnWeightSIRTerrainCurriculum stays frozen for v1-v10
    reproducibility.
    """

    params_version = "v11"

    def __post_init__(self):
        super().__post_init__()
        params = _load_params(self.params_version)
        v11 = params["v11"]

        # v11 terrain: param-sampled grid. The builder sets curriculum=True
        # itself (pit: replacing the generator after super() otherwise drops
        # the flag and the column split stops being deterministic).
        self.scene.terrain.terrain_generator = build_param_grid_terrain_cfg(v11["terrain_grid"])
        self.scene.terrain.max_init_terrain_level = None

        # v11 curriculum: joint SIR replaces the v5 row SIR (setattr via the
        # module constant -- the command term and check_obs_layout look the
        # term up by the same name; v11.1)
        self.curriculum.terrain_levels = None
        sir = v11["terrain_curriculum"]
        setattr(
            self.curriculum,
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

        # v11 command: particle-sourced lin_vel_x + the Eq. 2 label
        # accumulator. Field-by-field copy from the v5-wired term (its ranges
        # object already carries the v5 (0, 3) narrowing).
        vc = v11["velocity_command"]
        base_cmd = self.commands.base_velocity
        new_cmd = teacher_mdp.ParticleVelocityCommandCfg()
        new_cmd.asset_name = base_cmd.asset_name
        new_cmd.resampling_time_range = (1.0e9, 1.0e9)
        new_cmd.heading_command = base_cmd.heading_command
        new_cmd.heading_control_stiffness = base_cmd.heading_control_stiffness
        new_cmd.rel_heading_envs = base_cmd.rel_heading_envs
        new_cmd.rel_standing_envs = base_cmd.rel_standing_envs
        new_cmd.ranges = base_cmd.ranges
        new_cmd.v_pr_threshold = float(vc["v_pr_threshold"])
        new_cmd.command_jitter = float(vc["command_jitter"])
        self.commands.base_velocity = new_cmd


@configclass
class LizardRoughTeacherEnvCfg_V11_PLAY(LizardRoughTeacherEnvCfg_V11):
    """v11 play variant: no randomization, no curriculum.

    The ParticleVelocityCommand term stays (obs/command contract unchanged):
    with the joint SIR dropped its lin_vel_x falls back to the (0, 3)
    uniform range sample, matching the v10 PLAY behavior.
    """

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # the joint SIR reassigns spawn origins + velocities per episode --
        # deterministic eval must not roam (the command term then takes its
        # range fallback)
        setattr(self.curriculum, teacher_mdp.JOINT_SIR_TERM, None)


@configclass
class LizardRoughTeacherEnvCfg_V12(LizardRoughTeacherEnvCfg_V11):
    """v12 recipe: Miki et al. 2022 S8 reset/observation robustness package.

    The audit against the paper's S8 randomization list (user request
    2026-09-10, versions/lizard/v12/PLAN.md) found three gaps on top of v11;
    all knobs live in the v12 yaml section:

    * joint initial position AND velocity randomization at reset -- the stock
      ``reset_robot_joints`` scales the default pose, which is all-zero for
      this sprawled rig, so it has been a silent no-op; replaced by three
      ``reset_joints_by_offset`` terms (legs / feet / spine, soft-limit
      clamped)
    * base pose/velocity reset ranges moved to the yaml (the values are the
      stock base-cfg ones the teacher line already inherited -- pose x/y
      +-0.5 m, yaw +-3.14 rad, 6-axis velocity +-0.5 -- now tunable)
    * occasional foot-friction dips (``FootFrictionDipTerm``, p_dip 0.1 ->
      static [0.05, 0.3]); the privileged ``foot_friction`` obs cache is
      updated in the same call
    * height-ring noise model on the actor exteroception
      (``sample_ring_noise`` + ``NoisyFootRing``): conditions nominal/offset/
      noisy at 60/30/10 per episode (redrawn midway), per-foot per-episode
      bias w, per-foot per-step eps_f, per-point per-step eps_p, intermittent
      outliers, amplitudes x c_k

    Deliberate deviations (user decision 2026-09-10: no student
    distillation): the noise rides the TEACHER actor -- the paper corrupts
    only the student's height samples; the priv group stays clean. The
    r_slip weight returns to -0.003 (v8.1's -0.03 was never probed at this
    recipe). Obs groups / dims unchanged: 90/208/83 = 381.

    p_dip / joint offsets / sigmas are estimates -> ablation knobs (paper
    gives no numbers for the reset offsets; its z noise vector is per-leg
    and not printed in full -- one sigma set serves all feet here).
    """

    params_version = "v12"

    def __post_init__(self):
        super().__post_init__()
        params = _load_params(self.params_version)
        v12 = params["v12"]
        rr = v12["reset_randomization"]
        hn = v12["height_noise"]

        # --- joint initial state randomization (paper S8) ---
        # the stock scale-type term is a no-op on the all-zero default pose
        self.events.reset_robot_joints = None
        for name, patterns, key in (
            ("reset_joints_legs", [".*_haa_joint", ".*_hfe_joint", ".*_kfe_joint"], "legs"),
            ("reset_joints_feet", [".*_foot_joint"], "feet"),
            ("reset_joints_spine", ["chest_.*", "neck_.*", "tail[0-9]_.*"], "spine"),
        ):
            setattr(
                self.events,
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

        # --- base pose/velocity reset ranges from the yaml ---
        # (stock values inherited until now; exposed for tuning)
        self.events.reset_base.params["pose_range"] = {a: tuple(r) for a, r in rr["base_pose_range"].items()}
        self.events.reset_base.params["velocity_range"] = {a: tuple(r) for a, r in rr["base_velocity_range"].items()}

        # --- occasional foot-friction dips (paper S8) ---
        self.events.foot_friction_dip = EventTerm(
            func=teacher_mdp.FootFrictionDipTerm,
            mode="reset",
            params={
                "asset_cfg": SceneEntityCfg("robot", body_names=".*_foot"),
                "static_friction_range": tuple(rr["friction_dip"]["static"]),
                "dynamic_ratio_range": tuple(rr["friction_dip"]["dynamic_ratio"]),
                "p_dip": float(rr["friction_dip"]["p_dip"]),
            },
        )

        # --- height-ring noise (paper S8) on the actor extero group ---
        # reset event owns the per-episode state; the four extero terms swap
        # their func in place -- names, order and dims (208) stay the contract
        self.events.sample_ring_noise = EventTerm(
            func=teacher_mdp.sample_ring_noise,
            mode="reset",
            params={"ratios": tuple(hn["ratios"])},
        )
        for i, foot in enumerate(("lf", "rf", "rl", "rr")):
            term = getattr(self.observations.extero, f"{foot}_foot_ring")
            term.func = teacher_mdp.NoisyFootRing
            term.params = {
                **term.params,
                "foot_index": i,
                "sigma_w": float(hn["sigma_w"]),
                "sigma_f": float(hn["sigma_f"]),
                "sigma_p": float(hn["sigma_p"]),
                "outlier_prob": float(hn["outlier_prob"]),
                "outlier_range": tuple(hn["outlier_range"]),
            }


@configclass
class LizardRoughTeacherEnvCfg_V12_PLAY(LizardRoughTeacherEnvCfg_V12):
    """v12 play variant: no randomization, no curriculum, clean extero.

    ``apply_play_wiring`` nulls ``sample_ring_noise`` and ``foot_friction_dip``
    (shared DR list) -- ``NoisyFootRing`` then returns clean scans. The joint
    offset terms and the base pose/velocity ranges stay, matching the stock
    ``reset_base`` handling: PLAY randomization is seeded, not zeroed.
    """

    def __post_init__(self):
        super().__post_init__()

        # deterministic evaluation: shared PLAY wiring (single source, see play_utils)
        apply_play_wiring(self)

        # the joint SIR reassigns spawn origins + velocities per episode --
        # deterministic eval must not roam (the command term then takes its
        # range fallback)
        setattr(self.curriculum, teacher_mdp.JOINT_SIR_TERM, None)
