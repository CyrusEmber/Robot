# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Param-grid terrain builder for the v11 joint SIR curriculum.

Reads the ``v11.terrain_grid`` yaml table and expands EVERY parameter
combination into one sub-terrain entry with single-value ranges. With
``curriculum=True`` the stock TerrainGenerator's difficulty interpolation
becomes a no-op (min == max for every range), so each grid cell is an exact
parameter combo instead of a point on the difficulty diagonal -- the fix for
the diagonal problem (plan versions/lizard/v11/PLAN.md section 1). Columns
split deterministically by cumulative proportion (terrain_generator.py:243-247,
the same mechanism the eval suites rely on); rows are interchangeable
instances (fresh noise realizations for the stochastic terrain functions,
identical geometry for the deterministic ones).

Sub-terrain names encode the combo for :class:`JointSIRTerrainCurriculum`:
``<type>|<lvl>_<lvl>...`` with 0-based levels in yaml axis order; ``flat``
has no axes. All difficulty levels live in the v11 yaml section (SSOT).
"""

from __future__ import annotations

import itertools
import math

import isaaclab.terrains as terrain_gen
from isaaclab.terrains import TerrainGeneratorCfg

# structural constants carried over from TEACHER_TERRAINS_CFG_V5 (geometry,
# not curriculum knobs -- frozen v5 values):
_SIZE = (16.0, 16.0)
_BORDER_WIDTH = 25.0
_H_SCALE = 0.1
_V_SCALE = 0.005
_SLOPE_THRESHOLD = 0.75

_AXIS_DOC = "difficulty axes are read from the yaml keys (minus 'proportion')"


def _make_sub(type_name: str, values: dict, proportion: float):
    """Build one sub-terrain cfg at an explicit parameter combo.

    Every range-style field gets the single value twice so the difficulty
    interpolation is a no-op; scalar fields are set directly.
    """
    if type_name == "stairs":
        return terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=proportion,
            step_height_range=(values["step_height"], values["step_height"]),
            step_width=values["step_width"],
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        )
    if type_name == "stairs_inv":
        return terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=proportion,
            step_height_range=(values["step_height"], values["step_height"]),
            step_width=values["step_width"],
            platform_width=6.0,
            border_width=1.5,
            holes=False,
        )
    if type_name == "stepping_stones":
        return terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=proportion,
            stone_width_range=(values["stone_width"], values["stone_width"]),
            stone_distance_range=(values["stone_distance"], values["stone_distance"]),
            stone_height_max=0.3,
            holes_depth=-1.0,
            platform_width=4.0,
            border_width=0.5,
        )
    if type_name == "boxes":
        return terrain_gen.MeshRandomGridTerrainCfg(
            proportion=proportion,
            grid_height_range=(values["grid_height"], values["grid_height"]),
            grid_width=values["grid_width"],
            platform_width=4.0,
        )
    if type_name == "random_rough":
        return terrain_gen.HfRandomUniformTerrainCfg(
            proportion=proportion,
            noise_range=(values["noise_amp"], values["noise_amp"]),
            noise_step=0.02,
            border_width=0.5,
            downsampled_scale=0.5,
        )
    if type_name == "slope":
        return terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=proportion,
            slope_range=(values["slope"], values["slope"]),
            platform_width=4.0,
            border_width=0.5,
        )
    if type_name == "slope_inv":
        return terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=proportion,
            slope_range=(values["slope"], values["slope"]),
            platform_width=4.0,
            border_width=0.5,
        )
    if type_name == "flat":
        return terrain_gen.MeshPlaneTerrainCfg(proportion=proportion)
    raise ValueError(f"unknown terrain_grid type: {type_name!r} ({_AXIS_DOC})")


def build_param_grid_terrain_cfg(grid: dict) -> TerrainGeneratorCfg:
    """Expand the v11 ``terrain_grid`` table into a per-combo generator cfg.

    Args:
        grid: the ``v11.terrain_grid`` dict: per type ``proportion`` plus axis
            level lists, and optional ``num_rows``/``num_cols`` grid shape.

    Returns:
        The generator cfg: one sub-terrain per parameter combination, named
        ``<type>|<lvl>_<lvl>...`` in itertools.product order (last axis
        fastest, matching the curriculum term's mixed-radix decoding).

    Raises:
        ValueError: if a non-flat type has no axes, or any ``num_cols``.
    """
    num_rows = int(grid.get("num_rows", 4))
    num_cols = int(grid.get("num_cols", 120))
    sub_terrains: dict[str, object] = {}
    raw_total = 0.0
    min_combo_share = 1.0
    for type_name, spec in grid.items():
        if type_name in ("num_rows", "num_cols"):
            continue
        axes = {k: list(v) for k, v in spec.items() if k != "proportion"}
        proportion = float(spec.get("proportion", 0.0))
        raw_total += proportion
        if not axes and type_name != "flat":
            raise ValueError(f"terrain_grid type {type_name!r} has no axes (only 'flat' may be axis-free)")
        if axes:
            combos = list(itertools.product(*[range(len(v)) for v in axes.values()]))
            per = proportion / len(combos)
            min_combo_share = min(min_combo_share, per)
            for levels in combos:
                values = {name: lst[lvl] for (name, lst), lvl in zip(axes.items(), levels)}
                name = f"{type_name}|{'_'.join(str(l) for l in levels)}"
                sub_terrains[name] = _make_sub(type_name, values, per)
        else:
            sub_terrains["flat"] = _make_sub("flat", {}, proportion)
            min_combo_share = min(min_combo_share, proportion)
    # column-starvation guard (cumsum split is over normalized proportions)
    if raw_total > 0.0 and min_combo_share / raw_total * num_cols < 1.0:
        raise ValueError(
            f"num_cols={num_cols} leaves some combos without a column "
            f"(min normalized combo share {min_combo_share / raw_total:.4f}); "
            "raise terrain_grid.num_cols"
        )
    if math.isclose(raw_total, 0.0):
        raise ValueError("terrain_grid has no types with a positive proportion")
    return TerrainGeneratorCfg(
        size=_SIZE,
        border_width=_BORDER_WIDTH,
        num_rows=num_rows,
        num_cols=num_cols,
        horizontal_scale=_H_SCALE,
        vertical_scale=_V_SCALE,
        slope_threshold=_SLOPE_THRESHOLD,
        use_cache=False,
        curriculum=True,
        sub_terrains=sub_terrains,
    )
