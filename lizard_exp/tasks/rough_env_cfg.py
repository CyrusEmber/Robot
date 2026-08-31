# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard (26-joint) rough-terrain velocity task (stock Isaac Lab rough setup).

Inherits the flat task (:mod:`.lizard_env_cfg`) with all robot/DR parameters,
then re-enables the stock rough-terrain setup from
:class:`LocomotionVelocityRoughEnvCfg`: procedural terrain generator,
height scanner (perceptive, in the policy observations), terrain difficulty
curriculum and terrain-aware spawn.
"""

import isaaclab.terrains as terrain_gen
from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import RayCasterCfg, patterns
from isaaclab.terrains import TerrainGeneratorCfg
from isaaclab.utils.configclass import configclass
from isaaclab.utils.noise import UniformNoiseCfg as Unoise

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from lizard_exp.tasks.lizard_env_cfg import LizardFlatEnvCfg

# stock rough terrains are sized for ~0.5 m robots (8x8 m tiles, 0.05-0.23 m
# steps); the lizard is 3.6 m long with 1.4 m leg reach -> scale obstacles ~2x
LIZARD_ROUGH_TERRAINS_CFG = TerrainGeneratorCfg(
    size=(16.0, 16.0),
    border_width=25.0,
    num_rows=10,
    num_cols=20,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
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


@configclass
class LizardRoughEnvCfg(LizardFlatEnvCfg):
    """26-joint lizard on stock rough terrain, perceptive (height scan in obs)."""

    def __post_init__(self):
        super().__post_init__()

        # undo the flat conversion: lizard-scaled rough terrain + generator
        self.scene.terrain.terrain_type = "generator"
        self.scene.terrain.terrain_generator = LIZARD_ROUGH_TERRAINS_CFG
        self.scene.terrain.max_init_terrain_level = 5

        # height scanner: bodies live under the importer's Geometry scope
        # (flattened USD: /Robot/Geometry/base_link); anymal assumes /Robot/base.
        # Pattern covers the full leg span (feet at |x| up to ~1.4 m) but
        # sparser than stock (0.2 m resolution -> 15x9 = 135 points).
        self.scene.height_scanner = RayCasterCfg(
            prim_path="{ENV_REGEX_NS}/Robot/Geometry/base_link",
            offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
            ray_alignment="yaw",
            pattern_cfg=patterns.GridPatternCfg(resolution=0.2, size=[2.8, 1.6]),
            debug_vis=False,
            mesh_prim_paths=["/World/ground"],
        )
        self.observations.policy.height_scan = ObsTerm(
            func=mdp.height_scan,
            params={"sensor_cfg": SceneEntityCfg("height_scanner")},
            noise=Unoise(n_min=-0.1, n_max=0.1),
            clip=(-1.0, 1.0),
        )

        # terrain difficulty curriculum (stock)
        self.curriculum.terrain_levels = CurrTerm(func=mdp.terrain_levels_vel)


@configclass
class LizardRoughEnvCfg_PLAY(LizardRoughEnvCfg):
    """Play variant: smaller terrain grid, curriculum off, randomization off."""

    def __post_init__(self):
        super().__post_init__()

        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.scene.terrain.max_init_terrain_level = None
        if self.scene.terrain.terrain_generator is not None:
            self.scene.terrain.terrain_generator.num_rows = 5
            self.scene.terrain.terrain_generator.num_cols = 5
            self.scene.terrain.terrain_generator.curriculum = False
        self.observations.policy.enable_corruption = False
        # disable every randomization event for deterministic evaluation
        self.events.base_external_force_torque = None
        self.events.push_robot = None
        self.events.randomize_inertia = None
        self.events.randomize_actuator_gains = None
        self.events.randomize_joint_params = None
        self.events.randomize_limb_mass = None
        self.events.add_base_mass = None
        self.events.base_com = None
        self.events.physics_material = None
