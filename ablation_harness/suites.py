# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Fixed terrain suites for deterministic evaluation (Locomotion-Eval protocol).

A suite is a ``TerrainImporterCfg`` where every terrain type is locked:
column-per-type, fixed difficulty, pinned seed. Key determinism tricks
(verified against ``TerrainGenerator`` source):

* ``curriculum=True`` + equal ``proportion`` -> the curriculum generator assigns
  columns DETERMINISTICALLY by cumulative proportion: column ``j`` gets exactly
  sub-terrain ``j`` (dict insertion order). The random generator samples types
  per cell and can miss types entirely -- never use it for a suite.
* ``difficulty_range=(1.0, 1.0)`` locks the difficulty parameter (belt and
  suspenders on top of single-value parameter ranges).
* ``seed`` pins the RNG stream -> identical realizations across runs (the rough
  terrains still sample noise internally, but the same noise every time).

Lizard scale: 3.6 m body, ~2.8 m foot span, 16 m tiles (matches the training
terrain tile size so the policy sees familiar-sized features).
"""

import math

import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.terrains import TerrainGeneratorCfg, TerrainImporterCfg

# protocol-pinned generation seed (same for every eval, every run)
SUITE_SEED = 123

# column order == dict insertion order in the generator (see module docstring)
LIZARD_SUITE_V1_NAMES = [
    "flat",
    "slope_5deg",
    "slope_10deg",
    "stairs_10cm",
    "stairs_20cm",
    "rough_a",
    "rough_b",
    "gap_20cm",
    "gap_40cm",
]

_LIZARD_SUITE_V1_GENERATOR = TerrainGeneratorCfg(
    size=(16.0, 16.0),
    border_width=5.0,
    num_rows=1,
    num_cols=len(LIZARD_SUITE_V1_NAMES),
    curriculum=True,
    difficulty_range=(1.0, 1.0),
    seed=SUITE_SEED,
    use_cache=False,
    sub_terrains={
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0),
        "slope_5deg": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=1.0,
            slope_range=(math.radians(5.0), math.radians(5.0)),
            platform_width=2.0,
        ),
        "slope_10deg": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=1.0,
            slope_range=(math.radians(10.0), math.radians(10.0)),
            platform_width=2.0,
        ),
        "stairs_10cm": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=1.0,
            step_height_range=(0.10, 0.10),
            step_width=0.7,
            platform_width=4.0,
            border_width=1.5,
            holes=False,
        ),
        "stairs_20cm": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=1.0,
            step_height_range=(0.20, 0.20),
            step_width=0.7,
            platform_width=4.0,
            border_width=1.5,
            holes=False,
        ),
        "rough_a": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=1.0,
            noise_range=(0.05, 0.05),
            noise_step=0.04,
            border_width=5.0,
        ),
        "rough_b": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=1.0,
            noise_range=(0.15, 0.15),
            noise_step=0.04,
            border_width=5.0,
        ),
        "gap_20cm": terrain_gen.MeshGapTerrainCfg(
            proportion=1.0,
            gap_width_range=(0.20, 0.20),
            platform_width=6.0,
        ),
        "gap_40cm": terrain_gen.MeshGapTerrainCfg(
            proportion=1.0,
            gap_width_range=(0.40, 0.40),
            platform_width=6.0,
        ),
    },
)


def lizard_suite_v1() -> TerrainImporterCfg:
    """Fixed terrain suite for the lizard (9 columns, one terrain type each).

    Returns a fresh ``TerrainImporterCfg`` each call so callers can freely
    mutate it (e.g. override ``max_init_terrain_level``) without touching the
    frozen generator definition.
    """
    return TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=_LIZARD_SUITE_V1_GENERATOR,
        max_init_terrain_level=0,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        debug_vis=False,
    )
