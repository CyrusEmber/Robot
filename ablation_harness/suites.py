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
* ``seed`` pins the generator's own rng, but **not** the terrain functions: they draw from the
  global numpy stream (the height-field family) and the global torch stream (the random boxes),
  which the generator deliberately leaves alone (``terrain_generator.py:148``). A suite is only
  reproducible if the caller seeds those streams first -- :func:`eval.py` does it with
  :func:`rl_exp.tasks.terrain_geometry.seed_rngs` right before ``gym.make``. v1 got away with it
  by accident: its ``rough`` columns pinned their amplitude to a single value, which collapses
  the internal ``np.random.choice`` to a constant. v2 gives them a range, so the seed is doing
  real work (work/active/verified-rebuild-rating.md).

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


#: v2 keeps v1's column layout: what changed is the geometry of the two rough columns, which in
#: v1 were uniform plates (a single-value ``noise_range`` collapses ``np.random.choice`` to a
#: constant). Only the amplitude ranges move, so a v2 row is still readable against the same
#: column semantics.
LIZARD_SUITE_V2_NAMES = list(LIZARD_SUITE_V1_NAMES)

_LIZARD_SUITE_V2_GENERATOR = _LIZARD_SUITE_V1_GENERATOR.copy()
_LIZARD_SUITE_V2_GENERATOR.sub_terrains = {
    **{name: cfg.copy() for name, cfg in _LIZARD_SUITE_V1_GENERATOR.sub_terrains.items()},
    "rough_a": terrain_gen.HfRandomUniformTerrainCfg(
        proportion=1.0,
        noise_range=(0.02, 0.06),
        noise_step=0.01,
        downsampled_scale=0.5,  # ~= one sole: bumps at the scale the policy can feel
        border_width=5.0,
    ),
    "rough_b": terrain_gen.HfRandomUniformTerrainCfg(
        proportion=1.0,
        noise_range=(0.08, 0.16),
        noise_step=0.02,
        downsampled_scale=0.5,
        border_width=5.0,
    ),
}


def lizard_suite_v2() -> TerrainImporterCfg:
    """Fixed terrain suite for the lizard, v2: v1's layout with genuinely rough columns.

    Returns a fresh ``TerrainImporterCfg`` each call, as :func:`lizard_suite_v1` does.
    """
    return TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=_LIZARD_SUITE_V2_GENERATOR,
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
