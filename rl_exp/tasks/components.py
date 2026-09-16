# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Structural components of the teacher recipes: one writer per component (``ARCH_PLAN`` 2.4).

A structural piece used to be written wherever a version first needed it: the base class
built the height scanner, then ``LizardRoughTeacherEnvCfg_V3`` set that very field to ``None``
and hung four per-foot casters next to it. Two writers for one piece means the final state is
whatever the MRO ran last -- invisible from either site.

A component here is the *complete* state of one piece for one recipe, returned by name so the
caller assigns each name exactly once. The choice resolves by **recipe version**, never by
"whoever wrote last": V13/V14 inherit V10, not V11, so a sibling line's change must not leak
into them.

Discipline: the callables and pattern classes a recipe ships stay in the module the golden
recorded them in (``ring_pattern`` is snapshotted as
``rl_exp.tasks.teacher_env_cfg.ring_pattern`` in every V3+ entry), so they arrive here as
arguments instead of being re-homed -- moving a callable re-writes 76 golden paths without
changing one behaviour.
"""

from __future__ import annotations

from isaaclab.sensors import RayCasterCfg, patterns

# The four feet, in the order the extero obs group and the network reshape contract use.
FEET: tuple[str, ...] = ("lf", "rf", "rl", "rr")

# Where the ring geometry lives: it entered the frozen yaml at v3, and every later frozen
# copy carries the same section (the inherited wiring below reads it).
RING_SECTION = "v3"

# Which recipes sense height with the single ground grid scanner (the recipes that predate the
# ring swap) and which replaced it with four per-foot rings. A new recipe states its own
# choice here: the base class raises on a version neither table knows, so silence is never a
# silent default.
GRID_SCANNER: frozenset[str] = frozenset({"v1", "v2"})
FOOT_RINGS: frozenset[str] = frozenset(
    {"v3", "v4", "v5", "v6", "v8", "v10", "v11", "v12", "v13", "v14"}
)


def _grid_scanner(update_period: float) -> RayCasterCfg:
    """The single ground grid scanner: 0.2 m resolution over the full leg span."""
    # bodies live under the importer's Geometry scope (flattened USD:
    # /Robot/Geometry/base_link); the base task assumes /Robot/base.
    # Pattern covers the full leg span (feet at |x| up to ~1.4 m), 0.2 m
    # resolution -> 15x9 = 135 points.
    return RayCasterCfg(
        prim_path="{ENV_REGEX_NS}/Robot/Geometry/base_link",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
        ray_alignment="yaw",
        pattern_cfg=patterns.GridPatternCfg(resolution=0.2, size=[2.8, 1.6]),
        debug_vis=False,
        mesh_prim_paths=["/World/ground"],
        # scanner at the policy rate: same cadence the base class gives the stock
        # scanner (the family replacement accidentally leaves 0 -> 200 Hz)
        update_period=update_period,
    )


def _foot_ring(foot: str, ring: dict, pattern_cfg, update_period: float) -> RayCasterCfg:
    """One per-foot ring caster (the ring pattern instance is shared by all four feet)."""
    # the casters also register /World/ground in RayCaster.meshes, which the priv
    # foot_contact_normals / r_fc raycasts rely on
    return RayCasterCfg(
        prim_path=f"{{ENV_REGEX_NS}}/Robot/Geometry/{foot}_foot",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, ring["ray_offset_z"])),
        ray_alignment="yaw",
        pattern_cfg=pattern_cfg,
        debug_vis=False,
        mesh_prim_paths=["/World/ground"],
        update_period=update_period,
    )


def height_sensing(
    version: str, *, decimation: int, dt: float, params: dict, ring_pattern_cls: type
) -> dict[str, RayCasterCfg | None]:
    """The scene's height-sensing entities for one recipe, keyed by the name they take.

    Args:
        version: recipe version; must be stated in :data:`GRID_SCANNER` or :data:`FOOT_RINGS`.
        decimation: control decimation [steps], for the sensor period.
        dt: physics step [s].
        params: the recipe's parameters document; the ring block is read from it (only the
            ring recipes carry it, and their frozen yaml always does).
        ring_pattern_cls: the ring pattern class for this recipe. Injected rather than
            imported: it lives in ``teacher_env_cfg``, whose snapshot path every V3+ golden
            entry records, and this module cannot import its own caller.

    Returns:
        Name -> sensor (or ``None`` for the field the recipe does not use), in assignment
        order. A recipe has exactly one of the two sensing forms.

    Raises:
        ValueError: the version is not stated in either table. An unstated recipe must not
            silently inherit a sibling's sensing.
    """
    update_period = decimation * dt
    if version in GRID_SCANNER:
        return {"height_scanner": _grid_scanner(update_period)}
    if version in FOOT_RINGS:
        ring = params[RING_SECTION]["foot_ring"]
        pattern_cfg = ring_pattern_cls(
            ring_counts=tuple(ring["ring_counts"]),
            ring_radii=tuple(ring["ring_radii"]),
        )
        return {
            "height_scanner": None,
            **{
                f"{foot}_foot_ring": _foot_ring(foot, ring, pattern_cfg, update_period)
                for foot in FEET
            },
        }
    raise ValueError(
        f"Unknown teacher params_version '{version}' for height sensing;"
        f" known: {sorted(GRID_SCANNER | FOOT_RINGS)}"
    )
