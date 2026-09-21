# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Structural components of the teacher recipes: one writer per component (``ARCH_PLAN`` 2.4).

A structural piece used to be written wherever a version first needed it: the base class
built the height scanner, then the v3 recipe set that very field to ``None``
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

from isaaclab.managers import ObservationGroupCfg
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.sensors import RayCasterCfg, patterns

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp

from rl_exp.tasks import teacher_mdp
from rl_exp.tasks.param_grid_terrain import build_param_grid_terrain_cfg
from rl_exp.tools.verify import terrain_split_probe

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


# Recipes that keep the inherited base-contact termination with its sensor narrowed to the
# lizard's base body (the framework term watches anymal's "base"), and the recipes that dropped
# the term instead: the sprawled body sits low, so base contact is a crouch signal, not a fall,
# and the trained robot never flips. Contact stays penalized by ``rewards.undesired_contacts``
# (v3.6 / D0-6, user decision 2026-09-01: penalty only).
BASE_CONTACT_KEPT: frozenset[str] = frozenset({"v1", "v2"})
BASE_CONTACT_DROPPED: frozenset[str] = frozenset(
    {"v3", "v4", "v5", "v6", "v8", "v10", "v11", "v12", "v13", "v14"}
)

# v3 introduced the tilt termination (D1, threshold from the yaml); v10's recipe reads a flag of
# its own to decide whether to keep it (``v10.tilt_terminate: null`` -> gone), and the recipes
# after v10 inherit both the term and the flag.
TILT_ADDED: frozenset[str] = frozenset(
    {"v3", "v4", "v5", "v6", "v8", "v10", "v11", "v12", "v13", "v14"}
)
TILT_FLAG: frozenset[str] = frozenset({"v10", "v11", "v12", "v13", "v14"})

# v14's fall gate: roll angle plus pitch guard and dwell, all from its own yaml section.
ROLL_OVER: frozenset[str] = frozenset({"v14"})

_TERMINATIONS_KNOWN = BASE_CONTACT_KEPT | BASE_CONTACT_DROPPED


def terminations(
    version: str, *, params: dict, base_contact: DoneTerm, base_body: str
) -> dict[str, DoneTerm | None]:
    """The termination terms one recipe owns, keyed by name, in assignment order.

    Only the terms a recipe actually decides about appear here: a recipe that never had a
    ``tilt`` term must not be handed one holding ``None``, or the recipe grows a key nobody
    chose (the snapshot records the difference).

    Args:
        version: recipe version; must be stated in the tables above.
        params: the recipe's parameters document; the tilt and roll-over sections are read from
            it (a recipe that reads them always carries them in its frozen copy).
        base_contact: the inherited framework term, narrowed in place for the recipes that keep
            it. Passed in rather than rebuilt: its ``func`` is the framework's, and only the
            sensor changes.
        base_body: the lizard's base body name, from the recipe's own names block.

    Returns:
        Name -> term, or the recipe's explicit ``None`` for a term it drops.

    Raises:
        ValueError: the version is not stated in the tables above. An unstated recipe must not
            silently inherit a sibling's fall gates.
    """
    if version not in _TERMINATIONS_KNOWN:
        raise ValueError(
            f"Unknown teacher params_version '{version}' for terminations;"
            f" known: {sorted(_TERMINATIONS_KNOWN)}"
        )

    owned: dict[str, DoneTerm | None] = {}
    if version in BASE_CONTACT_KEPT:
        # the base task assumes the anymal base body is called "base"
        base_contact.params["sensor_cfg"] = SceneEntityCfg("contact_forces", body_names=[base_body])
        owned["base_contact"] = base_contact
    else:
        owned["base_contact"] = None

    if version in TILT_ADDED:
        if version in TILT_FLAG and params["v10"]["tilt_terminate"] is None:
            owned["tilt"] = None
        else:
            owned["tilt"] = DoneTerm(
                func=teacher_mdp.tilt_terminate,
                params={"gravity_z_limit": params["v3"]["tilt_terminate"]["gravity_z_limit"]},
            )

    if version in ROLL_OVER:
        roll_over = params["v14"]["roll_over"]
        owned["roll_over"] = DoneTerm(
            func=teacher_mdp.RollOverTerm,
            params={
                "roll_limit_deg": roll_over["roll_limit_deg"],
                "pitch_guard_deg": roll_over["pitch_guard_deg"],
                "dwell_s": roll_over["dwell_s"],
            },
        )
    return owned


# The generator payload and the spawn row for each recipe, in one table so "where does this
# recipe's terrain come from" is answered by reading one place. The payloads themselves stay
# next to the recipe file that defines them (two gates import them from there); ``None`` means
# the recipe's own grid section builds the generator.
#
#   v1/v2  the frozen v1/v2 generator, spawning at row 5 (frozen with the recipe)
#   v3     Miki-aligned terrain (stair top 0.55 m + stepping stones), spawning at the easiest
#          row: the discrete stand-in for the particle-filter curriculum only holds if training
#          starts at level 0
#   v4     coarser rubble -- the soles measure 0.46 x 0.51 m, not the 0.131 m the bone length
#          suggested, so the debris was scaled up
#   v5     v4's types plus flat; the SIR recipes after it reuse this payload
_PARAM_GRID_SECTION = "v11"

TERRAIN_BY_RECIPE: dict[str, tuple[str | None, int | None]] = {
    "v1": ("TEACHER_TERRAINS_CFG", 5),
    "v2": ("TEACHER_TERRAINS_CFG", 5),
    "v3": ("TEACHER_TERRAINS_CFG_V3", 0),
    "v4": ("TEACHER_TERRAINS_CFG_V4", 0),
    "v5": ("TEACHER_TERRAINS_CFG_V5", None),
    "v6": ("TEACHER_TERRAINS_CFG_V5", None),
    "v8": ("TEACHER_TERRAINS_CFG_V5", None),
    "v10": ("TEACHER_TERRAINS_CFG_V5", None),
    "v11": (None, None),
    "v12": (None, None),
    "v13": ("TEACHER_TERRAINS_CFG_V5", None),
    "v14": ("TEACHER_TERRAINS_CFG_V5", None),
}


def terrain(version: str, *, params: dict, payloads: dict[str, object]) -> dict[str, object]:
    """The terrain block for one recipe: type, generator, and the row it spawns at.

    Args:
        version: recipe version; must be stated in :data:`TERRAIN_BY_RECIPE`.
        params: the recipe's parameters document; read only by the recipes that build their
            generator from their own grid section.
        payloads: generator payloads by name, handed in from the module that defines them.

    Returns:
        The three ``scene.terrain`` attributes, in assignment order.

    Raises:
        ValueError: the version is not stated in :data:`TERRAIN_BY_RECIPE`.
        KeyError: the recipe names a payload the caller did not hand in -- a recipe whose
            terrain cannot be resolved must not inherit somebody else's.
    """
    if version not in TERRAIN_BY_RECIPE:
        raise ValueError(
            f"Unknown teacher params_version '{version}' for terrain;"
            f" known: {sorted(TERRAIN_BY_RECIPE)}"
        )
    payload, start_level = TERRAIN_BY_RECIPE[version]
    # The generator is built *inside* TerrainImporter from this cfg, and it generates while
    # it is being constructed, so the split probe has to be watching before the cfg leaves
    # here -- wrapping an instance afterwards would be too late (ARCH_PLAN Step 3.3d).
    terrain_split_probe.install()
    if payload is None:
        # the builder sets curriculum=True itself: replacing a generator afterwards drops the
        # flag, and the column split stops being deterministic
        generator = build_param_grid_terrain_cfg(params[_PARAM_GRID_SECTION]["terrain_grid"])
    else:
        generator = payloads[payload]
    return {
        "terrain_type": "generator",
        "terrain_generator": generator,
        "max_init_terrain_level": start_level,
    }


# The forward range each recipe asks for; ``None`` means the recipe's own yaml carries it.
#   v1/v2  the paper override (-1, 1): the yaml keeps the wide lizard ambition ranges for the
#          family tasks, the teacher narrows them
#   v3     widened to 2 m/s -- a 1 m/s cap made foot-pad creeping the optimum -- gated by a
#          staged speed curriculum
#   v4     v3's range: v4 re-scales the rubble only, and it is the PLAY variant that pins the
#          full 5 m/s (see FULL_FORWARD_RANGE)
#   v5+    a yaml number, because the window is what the SIR particles sample
#   v11    the term itself is replaced by the particle-sourced command
COMMAND_RANGE: dict[str, tuple[float, float] | None] = {
    "v1": (-1.0, 1.0),
    "v2": (-1.0, 1.0),
    "v3": (-1.0, 2.0),
    "v4": (-1.0, 2.0),
    "v5": None,
    "v6": None,
    "v8": None,
    "v10": None,
    "v11": None,
    "v12": None,
    "v13": None,
    "v14": None,
}

# Recipes whose command term is the particle-sourced one (v11's mechanism).
PARTICLE_COMMAND: frozenset[str] = frozenset({"v11", "v12"})

_RANGE_SECTION = "v5"
_PARTICLE_SECTION = "v11"

# The range the PLAY variants of the curriculum-gated recipes pin instead: the staged speed
# curriculum would widen the range mid-evaluation on a good policy.
FULL_FORWARD_RANGE: tuple[float, float] = (-1.0, 5.0)


def commands(
    version: str, *, params: dict, base_velocity, pins_full_range: bool
) -> dict[str, object]:
    """The velocity-command term for one recipe.

    Args:
        version: recipe version; must be stated in :data:`COMMAND_RANGE`.
        params: the recipe's parameters document (read for the yaml-sourced range and, in the
            particle recipes, for the jitter and the label threshold).
        base_velocity: the inherited framework term. Mutated in place for every recipe, and
            copied field-by-field into the particle term for the recipes that replace it --
            copied rather than rebuilt, so a framework field added later cannot be dropped by
            accident.
        pins_full_range: this recipe's PLAY variant pins the full forward range instead of the
            curriculum-gated one.

    Returns:
        ``{"base_velocity": term}``.

    Raises:
        ValueError: the version is not stated in :data:`COMMAND_RANGE`.
    """
    if version not in COMMAND_RANGE:
        raise ValueError(
            f"Unknown teacher params_version '{version}' for commands;"
            f" known: {sorted(COMMAND_RANGE)}"
        )

    term = base_velocity
    # paper-faithful local override (plan 4.3): the yaml keeps the wide lizard ambition ranges
    # for the family tasks, the teacher narrows them
    term.ranges.lin_vel_y = (-0.5, 0.5)
    term.ranges.ang_vel_z = (-1.0, 1.0)
    range_x = COMMAND_RANGE[version]
    if range_x is None:
        range_x = tuple(params[_RANGE_SECTION]["commands"]["lin_vel_x"])
    term.ranges.lin_vel_x = range_x

    if version in PARTICLE_COMMAND:
        vc = params[_PARTICLE_SECTION]["velocity_command"]
        particle = teacher_mdp.ParticleVelocityCommandCfg()
        particle.asset_name = term.asset_name
        particle.resampling_time_range = (1.0e9, 1.0e9)
        particle.heading_command = term.heading_command
        particle.heading_control_stiffness = term.heading_control_stiffness
        particle.rel_heading_envs = term.rel_heading_envs
        particle.rel_standing_envs = term.rel_standing_envs
        particle.ranges = term.ranges
        particle.v_pr_threshold = float(vc["v_pr_threshold"])
        particle.command_jitter = float(vc["command_jitter"])
        term = particle

    if pins_full_range:
        term.ranges.lin_vel_x = FULL_FORWARD_RANGE

    return {"base_velocity": term}


# Recipes whose observations live in one flat group: v3 restructured them into three groups
# (proprio / extero / priv) for the split-encoder network, and every later recipe inherits it.
SINGLE_GROUP_OBS: frozenset[str] = frozenset({"v1", "v2"})

# The proprioceptive terms the framework's policy group already carries. The flat recipes keep
# them where they are; the split recipes copy them into ``proprio`` in this order, because a
# group's attribute order is the term concat order and the network's reshape contract.
PROPRIO_TERMS: tuple[str, ...] = (
    "base_lin_vel",
    "base_ang_vel",
    "projected_gravity",
    "velocity_commands",
    "joint_pos",
    "joint_vel",
    "actions",
)

# Privileged terms every recipe carries ...
BASELINE_PRIV_TERMS: tuple[str, ...] = (
    "base_lin_vel_true",
    "base_ang_vel_true",
    "foot_contact",
    "feet_air_time",
    "body_mass",
)

# ... and the incremental ones, in the order they were introduced. A recipe's spec says which
# it includes; the flat recipes keep the rest as an explicit ``None``.
SPEC_TERMS: tuple[str, ...] = (
    "foot_contact_forces",
    "foot_contact_normals",
    "foot_friction",
    "thigh_shank_contacts",
    "base_external_wrench",
)

# Recipes whose extero scans carry the paper's ring noise (v12): func and parameters both come
# from that recipe's own yaml section.
RING_NOISE: frozenset[str] = frozenset({"v12"})
_NOISE_SECTION = "v12"


def _teacher_terms(params: dict) -> dict[str, ObsTerm]:
    """The teacher's privileged terms, built in the fixed order the lists above describe."""
    base_name = params["robot"]["base_body_name"]
    return {
        # privilege 1: clean height scan (no observation noise, clip kept)
        "height_scan": ObsTerm(
            func=mdp.height_scan,
            params={"sensor_cfg": SceneEntityCfg("height_scanner")},
            clip=(-1.0, 1.0),
        ),
        # privilege 2: true base velocities (the proprioceptive terms carry sensor noise;
        # these are the ground-truth counterparts)
        "base_lin_vel_true": ObsTerm(func=mdp.base_lin_vel),
        "base_ang_vel_true": ObsTerm(func=mdp.base_ang_vel),
        # privilege 3: foot contact flags, swing durations, per-body mass
        "foot_contact": ObsTerm(
            func=teacher_mdp.foot_contact_bools,
            params={
                "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
                "threshold": 1.0,
            },
        ),
        "feet_air_time": ObsTerm(
            func=teacher_mdp.feet_air_time,
            params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot")},
        ),
        "body_mass": ObsTerm(
            func=teacher_mdp.body_mass_truth,
            params={"asset_cfg": SceneEntityCfg("robot", body_names=".*")},
        ),
        # privilege 4 (v2, Miki et al. 2022 table completion): contact force vectors, contact
        # normals, per-foot friction, thigh/shank contact flags, persistent external wrench --
        # see rl_exp/versions/lizard/OBS.md (the obs layout SSOT)
        "foot_contact_forces": ObsTerm(
            func=teacher_mdp.foot_contact_forces,
            params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot")},
        ),
        "foot_contact_normals": ObsTerm(
            func=teacher_mdp.FootContactNormalsTerm,
            params={"mesh_prim_path": "/World/ground", "max_distance": 2.0, "start_offset": 0.5},
        ),
        "foot_friction": ObsTerm(
            func=teacher_mdp.foot_friction_truth,
            params={"asset_cfg": SceneEntityCfg("robot", body_names=".*_foot")},
        ),
        "thigh_shank_contacts": ObsTerm(
            func=teacher_mdp.thigh_shank_contacts,
            params={
                "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[".*_hfe", ".*_kfe"]),
                "threshold": 1.0,
            },
        ),
        "base_external_wrench": ObsTerm(
            func=teacher_mdp.base_external_wrench,
            params={"asset_cfg": SceneEntityCfg("robot", body_names=[base_name])},
        ),
    }


def _ring_terms(version: str, params: dict) -> dict[str, ObsTerm]:
    """The four per-foot scan terms, in foot order, plain or with the ring noise (v12)."""
    ring = params[RING_SECTION]["foot_ring"]
    noise = params[_NOISE_SECTION]["height_noise"] if version in RING_NOISE else None
    terms: dict[str, ObsTerm] = {}
    for index, foot in enumerate(FEET):
        scan = {"sensor_cfg": SceneEntityCfg(f"{foot}_foot_ring"), "offset": ring["scan_offset"]}
        if noise is None:
            terms[f"{foot}_foot_ring"] = ObsTerm(
                func=mdp.height_scan, params=scan, clip=tuple(ring["clip"])
            )
        else:
            terms[f"{foot}_foot_ring"] = ObsTerm(
                func=teacher_mdp.NoisyFootRing,
                params={
                    **scan,
                    "foot_index": index,
                    "sigma_w": float(noise["sigma_w"]),
                    "sigma_f": float(noise["sigma_f"]),
                    "sigma_p": float(noise["sigma_p"]),
                    "outlier_prob": float(noise["outlier_prob"]),
                    "outlier_range": tuple(noise["outlier_range"]),
                },
                clip=tuple(ring["clip"]),
            )
    return terms


def observations(
    version: str, *, params: dict, base_policy: ObservationGroupCfg, spec: dict[str, set[str]]
) -> dict[str, ObservationGroupCfg | None]:
    """Every observation group one recipe has, keyed by name, in assignment order.

    Args:
        version: recipe version; must be a key of ``spec``.
        params: the recipe's parameters document (base body name, ring geometry, ring noise).
        base_policy: the framework's policy group, which already carries the proprioceptive
            terms. The flat recipes extend it in place; the split recipes copy those terms out
            of it and drop the group.
        spec: the per-version privileged-term table, owned next to the recipes it describes.

    Returns:
        Group name -> group, or the explicit ``None`` for the flat group a split recipe drops.

    Raises:
        ValueError: the version has no spec entry, so its obs contract is unknown.
    """
    if version not in spec:
        raise ValueError(
            f"Unknown teacher params_version '{version}' for observations; known: {sorted(spec)}"
        )
    terms = _teacher_terms(params)

    if version in SINGLE_GROUP_OBS:
        for name, term in terms.items():
            setattr(base_policy, name, term)
        # strip the incremental terms this recipe does not include, so running an old task id
        # rebuilds the old recipe instead of today's
        every = set().union(*spec.values())
        for name in sorted(every - spec[version]):
            setattr(base_policy, name, None)
        return {"policy": base_policy}

    rings = _ring_terms(version, params)
    proprio = ObservationGroupCfg()
    for name in PROPRIO_TERMS:
        setattr(proprio, name, getattr(base_policy, name))
    extero = ObservationGroupCfg()
    for name, term in rings.items():
        setattr(extero, name, term)
    priv = ObservationGroupCfg()
    for name in BASELINE_PRIV_TERMS + SPEC_TERMS:
        if name in BASELINE_PRIV_TERMS or name in spec[version]:
            setattr(priv, name, terms[name])
        else:
            setattr(priv, name, None)
    return {"policy": None, "proprio": proprio, "extero": extero, "priv": priv}
