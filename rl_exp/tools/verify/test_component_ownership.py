# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""One writer per structural component, and the detector that keeps it that way (``ARCH_PLAN`` 2.4).

The golden lock proves a builder reproduces the same *values*. It cannot prove the values now
come from one place: the same final state is reachable by building a component in the base
class, overwriting a field of it in a subclass, and nulling another field further down -- which
is exactly how the height scanner and the per-foot rings ended up with three writers and one
invisible winner. A green golden is necessary, not sufficient, and this gate covers the half it
cannot see:

* each recipe version resolves to one *complete* form (never a mix, and every declared recipe
  version is stated -- an unstated version must not silently inherit a sibling's),
* no source writes an owned scene name directly: the component stays the only writer,
* the detector fires on a second writer, so a green run is not a dead check.

Scope: the migrated components, in the file that hosts them. A component added later extends
``OWNERSHIP`` (and this docstring's list) rather than teaching a new detector.
"""

from __future__ import annotations

import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]

from rl_exp.tasks import components, teacher_mdp
from rl_exp.tasks.teacher_env_cfg import TEACHER_PRIVILEGED_SPEC, RingPatternCfg
from isaaclab.envs.mdp.commands.commands_cfg import UniformVelocityCommandCfg
from isaaclab.managers import ObservationGroupCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm

# Component -> the scene names it owns; every host below must route writes through it.
OWNERSHIP: dict[str, tuple[str, ...]] = {
    "height_sensing": ("height_scanner", *(f"{foot}_foot_ring" for foot in components.FEET)),
    "terminations": ("base_contact", "tilt", "roll_over"),
    "terrain": ("terrain_type", "terrain_generator", "max_init_terrain_level"),
    "commands": ("base_velocity",),
    "observations": ("policy", "proprio", "extero", "priv"),
}
# The files scanned. ``play_utils.apply_play_wiring`` is deliberately NOT one of them: it is the
# declared PLAY post-processor, and it rewrites the spawn level and the grid shape for every
# recipe on purpose (deterministic evaluation does not roam). That is a recipe-level decision,
# not a version quietly overriding a sibling -- so it stays visible here instead of being
# scanned, and it must never grow into a per-version override.
HOSTS: tuple[str, ...] = ("rl_exp/tasks/teacher_env_cfg.py",)

# Only the fields the component reads need to be present.
RING_PARAMS = {
    components.RING_SECTION: {
        "foot_ring": {"ring_counts": (6, 8), "ring_radii": (0.1, 0.2), "ray_offset_z": 0.05}
    }
}


def chain_names(node: ast.AST) -> list[str]:
    """Every name in an assignment target, inner to outer (``a.b.c`` -> ``[c, b, a]``)."""
    names: list[str] = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        names.append(node.id)
    return names


def second_writers(source: str, owned: set[str]) -> list[str]:
    """Writes of an owned name in ``source`` that do not go through the component.

    Args:
        source: python source text.
        owned: scene names the component owns.

    Returns:
        One ``line: path`` per offending write, in source order. Writing a *field* of an owned
        entity counts (``self.scene.height_scanner.update_period = ...``): that writer still
        decides part of the final state, which is what "one writer" is about. A ``setattr``
        whose name is a variable (the component loop) is not a second writer by construction.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
                name = node.args[1]
                if isinstance(name, ast.Constant) and name.value in owned:
                    found.append(f"{node.lineno}: setattr(..., {name.value!r}, ...)")
            continue
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            names = chain_names(target)
            if any(name in owned for name in names):
                found.append(f"{node.lineno}: {'.'.join(reversed(names))}")
    return sorted(set(found), key=lambda row: int(row.split(":", 1)[0]))


def _expected_names(version: str) -> tuple[str, ...]:
    """The owned names one recipe version must produce, in assignment order."""
    if version in components.GRID_SCANNER:
        return ("height_scanner",)
    return ("height_scanner", *(f"{foot}_foot_ring" for foot in components.FEET))


def _ring_geometry(pattern_cfg) -> tuple:
    """The ring geometry a pattern carries, comparable across the per-sensor copies."""
    return (
        tuple(pattern_cfg.ring_counts),
        tuple(pattern_cfg.ring_radii),
        tuple(pattern_cfg.direction),
    )


def _fake_terms():
    """The inherited framework term (a stand-in) and one recipe document for terminations."""
    term = DoneTerm(func=lambda *a, **k: None, params={})
    params = {
        "v3": {"tilt_terminate": {"gravity_z_limit": -0.5}},
        "v10": {"tilt_terminate": None},
        "v14": {"roll_over": {"roll_limit_deg": 100.0, "pitch_guard_deg": 80.0, "dwell_s": 0.5}},
    }
    return term, params


def termination_problems() -> list[str]:
    """Every declared recipe version resolves to exactly one complete termination set."""
    problems: list[str] = []
    declared = components.BASE_CONTACT_KEPT | components.BASE_CONTACT_DROPPED
    for version in sorted(declared | components.TILT_ADDED | components.ROLL_OVER):
        term, params = _fake_terms()
        owned = components.terminations(
            version, params=params, base_contact=term, base_body="base_link"
        )
        expected = ["base_contact"]
        if version in components.TILT_ADDED:
            expected.append("tilt")
        if version in components.ROLL_OVER:
            expected.append("roll_over")
        if list(owned) != expected:
            problems.append(f"terminations {version}: {list(owned)} != {expected}")
            continue
        if version in components.BASE_CONTACT_KEPT:
            if owned["base_contact"] is not term:
                problems.append(f"terminations {version}: the kept term is not the inherited one")
            elif term.params["sensor_cfg"].body_names != ["base_link"]:
                problems.append(f"terminations {version}: sensor not narrowed to the base body")
        elif owned["base_contact"] is not None:
            problems.append(f"terminations {version}: base contact survived as {owned['base_contact']!r}")
        if "tilt" in owned:
            flagged = version in components.TILT_FLAG
            if flagged and owned["tilt"] is not None:
                problems.append(f"terminations {version}: flag says drop tilt but a term was built")
            if not flagged and owned["tilt"] is None:
                problems.append(f"terminations {version}: tilt dropped without a flag saying so")

    try:
        term, params = _fake_terms()
        components.terminations("v99", params=params, base_contact=term, base_body="base_link")
        problems.append("terminations v99: an unstated version was served a set instead of raising")
    except ValueError:
        pass
    return problems


def terrain_problems() -> list[str]:
    """Every recipe resolves to a payload it actually names, with the block's three fields."""
    problems: list[str] = []
    payloads = {name: object() for name, _ in components.TERRAIN_BY_RECIPE.values() if name}
    built_from_grid = sorted(
        version for version, (name, _) in components.TERRAIN_BY_RECIPE.items() if name is None
    )
    for version, (name, start) in sorted(components.TERRAIN_BY_RECIPE.items()):
        if name is None:
            continue  # the param grid needs a real recipe document; gate [24] builds those tasks
        block = components.terrain(version, params={}, payloads=payloads)
        if list(block) != ["terrain_type", "terrain_generator", "max_init_terrain_level"]:
            problems.append(f"terrain {version}: {list(block)} is not the block's three fields")
            continue
        if block["terrain_type"] != "generator":
            problems.append(f"terrain {version}: type {block['terrain_type']!r}")
        if block["terrain_generator"] is not payloads[name]:
            problems.append(f"terrain {version}: did not take the payload it names ({name})")
        if block["max_init_terrain_level"] != start:
            problems.append(f"terrain {version}: start row {block['max_init_terrain_level']} != {start}")
    if built_from_grid != ["v11", "v12"]:
        problems.append(f"terrain: recipes building from their own grid changed: {built_from_grid}")
    try:
        components.terrain("v99", params={}, payloads=payloads)
        problems.append("terrain v99: an unstated version was served a block instead of raising")
    except ValueError:
        pass
    return problems


def command_problems() -> list[str]:
    """Every recipe resolves to one command term carrying the range it declares."""
    problems: list[str] = []
    params = {
        "v5": {"commands": {"lin_vel_x": [0.0, 3.0]}},
        "v11": {"velocity_command": {"v_pr_threshold": 0.1, "command_jitter": 0.05}},
    }
    for version, declared in sorted(components.COMMAND_RANGE.items()):
        base = UniformVelocityCommandCfg(asset_name="robot")
        term = components.commands(
            version, params=params, base_velocity=base, pins_full_range=False
        )["base_velocity"]
        expected = declared if declared is not None else (0.0, 3.0)
        if tuple(term.ranges.lin_vel_x) != tuple(expected):
            problems.append(f"commands {version}: forward {term.ranges.lin_vel_x} != {expected}")
        if tuple(term.ranges.lin_vel_y) != (-0.5, 0.5):
            problems.append(f"commands {version}: lateral {term.ranges.lin_vel_y} != (-0.5, 0.5)")
        if tuple(term.ranges.ang_vel_z) != (-1.0, 1.0):
            problems.append(f"commands {version}: yaw {term.ranges.ang_vel_z} != (-1.0, 1.0)")
        if version in components.PARTICLE_COMMAND:
            if not isinstance(term, teacher_mdp.ParticleVelocityCommandCfg):
                problems.append(f"commands {version}: term is {type(term).__name__}, not particle")
            elif float(term.v_pr_threshold) != 0.1 or float(term.command_jitter) != 0.05:
                problems.append(f"commands {version}: particle values not read from the document")
            elif tuple(term.resampling_time_range) != (1.0e9, 1.0e9):
                problems.append(f"commands {version}: the particle term resamples on its own")
        elif term is not base:
            problems.append(f"commands {version}: a non-particle recipe replaced the term")

    for version in sorted(components.COMMAND_RANGE):
        base = UniformVelocityCommandCfg(asset_name="robot")
        term = components.commands(
            version, params=params, base_velocity=base, pins_full_range=True
        )["base_velocity"]
        if tuple(term.ranges.lin_vel_x) != components.FULL_FORWARD_RANGE:
            problems.append(f"commands {version}: pinned range {term.ranges.lin_vel_x}")

    try:
        base = UniformVelocityCommandCfg(asset_name="robot")
        components.commands("v99", params=params, base_velocity=base, pins_full_range=False)
        problems.append("commands v99: an unstated version was served a term instead of raising")
    except ValueError:
        pass
    return problems


def _group_terms(group) -> list[str]:
    """The term names a group carries, without the group's own configuration fields."""
    own = set(vars(ObservationGroupCfg()))
    return [name for name in vars(group) if name not in own]


def observation_problems() -> list[str]:
    """Every recipe resolves to the observation groups its version declares, in order."""
    problems: list[str] = []
    params = {
        "robot": {"base_body_name": "base_link"},
        "v3": {"foot_ring": {"scan_offset": 0.05, "clip": [-1.0, 1.0]}},
        "v12": {
            "height_noise": {
                "sigma_w": 0.1,
                "sigma_f": 0.05,
                "sigma_p": 0.02,
                "outlier_prob": 0.01,
                "outlier_range": [-1.0, 1.0],
            }
        },
    }
    for version in sorted(TEACHER_PRIVILEGED_SPEC):
        base = ObservationGroupCfg()
        for name in components.PROPRIO_TERMS:
            setattr(base, name, name)  # a marker: the copy can then be checked by identity
        try:
            groups = components.observations(
                version, params=params, base_policy=base, spec=TEACHER_PRIVILEGED_SPEC
            )
        except Exception as err:  # noqa: BLE001 - a recipe that cannot build is the failure
            problems.append(f"observations {version}: {type(err).__name__}: {err}")
            continue

        if version in components.SINGLE_GROUP_OBS:
            if list(groups) != ["policy"] or groups["policy"] is not base:
                problems.append(f"observations {version}: {list(groups)} is not the flat policy group")
                continue
            included = TEACHER_PRIVILEGED_SPEC[version]
            for name in components.SPEC_TERMS:
                got = base.__dict__.get(name, "<absent>")
                if name in included and not hasattr(got, "func"):
                    problems.append(f"observations {version}: {name} is {got!r}, not a term")
                if name not in included and got is not None:
                    problems.append(f"observations {version}: {name} survived as {got!r}")
            continue

        if list(groups) != ["policy", "proprio", "extero", "priv"] or groups["policy"] is not None:
            problems.append(f"observations {version}: {list(groups)} groups, policy={groups['policy']!r}")
            continue
        if _group_terms(groups["proprio"]) != list(components.PROPRIO_TERMS):
            problems.append(f"observations {version}: proprio order {_group_terms(groups['proprio'])}")
        if _group_terms(groups["priv"]) != list(components.BASELINE_PRIV_TERMS) + list(components.SPEC_TERMS):
            problems.append(f"observations {version}: priv order {_group_terms(groups['priv'])}")
        if _group_terms(groups["extero"]) != [f"{foot}_foot_ring" for foot in components.FEET]:
            problems.append(f"observations {version}: extero order {_group_terms(groups['extero'])}")
        for name in components.PROPRIO_TERMS:
            if getattr(groups["proprio"], name) is not name:
                problems.append(f"observations {version}: proprio {name} is not the framework's term")
                break
        noisy = version in components.RING_NOISE
        for foot in components.FEET:
            term = groups["extero"].__dict__[f"{foot}_foot_ring"]
            if noisy and (term.func is not teacher_mdp.NoisyFootRing or "foot_index" not in term.params):
                problems.append(f"observations {version}: {foot} ring is not the noisy one")
                break
            if not noisy and ("foot_index" in term.params or term.func is teacher_mdp.NoisyFootRing):
                problems.append(f"observations {version}: {foot} ring carries noise it did not ask for")
                break

    try:
        components.observations(
            "v99", params=params, base_policy=ObservationGroupCfg(), spec=TEACHER_PRIVILEGED_SPEC
        )
        problems.append("observations v99: an unstated version was served groups instead of raising")
    except ValueError:
        pass
    return problems


def form_problems() -> list[str]:
    """Every declared recipe version resolves to exactly one complete sensing form."""
    problems: list[str] = []
    overlap = sorted(components.GRID_SCANNER & components.FOOT_RINGS)
    if overlap:
        problems.append(f"{overlap}: declared as both forms -- the pick would be order, not intent")
    missing = sorted(set(TEACHER_PRIVILEGED_SPEC) - (components.GRID_SCANNER | components.FOOT_RINGS))
    if missing:
        problems.append(
            f"{missing}: recipe version(s) with no stated height-sensing form -- state each in"
            f" components.GRID_SCANNER or components.FOOT_RINGS, never leave it to the MRO"
        )

    for version in sorted(components.GRID_SCANNER | components.FOOT_RINGS):
        try:
            names = components.height_sensing(
                version,
                decimation=4,
                dt=0.005,
                params=RING_PARAMS,
                ring_pattern_cls=RingPatternCfg,
            )
        except Exception as err:  # noqa: BLE001 - a component that cannot build is the failure
            problems.append(f"{version}: {type(err).__name__}: {err}")
            continue
        expected = _expected_names(version)
        if tuple(names) != expected:
            problems.append(f"{version}: names {tuple(names)} != expected {expected}")
            continue
        grid = names["height_scanner"]
        rings = [cfg for name, cfg in names.items() if name.endswith("_foot_ring")]
        if version in components.GRID_SCANNER:
            if grid is None or rings:
                problems.append(f"{version}: grid form but grid={grid!r}, {len(rings)} ring(s)")
        elif grid is not None or len(rings) != len(components.FEET):
            problems.append(f"{version}: ring form but grid={grid!r}, {len(rings)} ring(s)")
        elif len({_ring_geometry(cfg.pattern_cfg) for cfg in rings}) != 1:
            # configclass copies a pattern per sensor, so identity proves nothing here --
            # the four feet must simply agree on one geometry.
            problems.append(f"{version}: the four feet no longer agree on one ring geometry")

    try:
        components.height_sensing(
            "v99", decimation=4, dt=0.005, params=RING_PARAMS, ring_pattern_cls=RingPatternCfg
        )
        problems.append("v99: an unstated version was served a form instead of raising")
    except ValueError:
        pass
    return problems


def self_test() -> int:
    """Prove the detector: a direct write, a field write and a literal setattr all fire."""
    owned = set(OWNERSHIP["height_sensing"])
    cases = {
        "direct": "self.scene.height_scanner = None\n",
        "field": "self.scene.height_scanner.update_period = 0.02\n",
        "setattr": 'setattr(self.scene, "lf_foot_ring", RayCasterCfg())\n',
        "through the component": (
            "for name, sensor in components.height_sensing(v).items():\n"
            "    setattr(self.scene, name, sensor)\n"
        ),
    }
    problems: list[str] = []
    for label, source in cases.items():
        fired = bool(second_writers(source, owned))
        if (label == "through the component") == fired:
            problems.append(f"{label!r}: {'fired on the component call' if fired else 'did not fire'}")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print("COMPONENT_OWNERSHIP_SELFTEST_FAILED")
        return 1
    print("COMPONENT_OWNERSHIP_SELFTEST_OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Gate entry point: component forms, then the second-writer scan over the hosts."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        return self_test()

    problems = (
        form_problems()
        + termination_problems()
        + terrain_problems()
        + command_problems()
        + observation_problems()
    )
    for host in HOSTS:
        source = (_REPO / host).read_text(encoding="utf-8")
        for component, owned in OWNERSHIP.items():
            for found in second_writers(source, set(owned)):
                problems.append(
                    f"{host}:{found} writes a name {component!r} owns -- route it through the"
                    f" component or the winner is the MRO again"
                )
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print("COMPONENT_OWNERSHIP_FAILED")
        return 1
    owned = sum(len(names) for names in OWNERSHIP.values())
    print(
        f"COMPONENT_OWNERSHIP_OK ({len(OWNERSHIP)} component(s), {owned} owned name(s),"
        f" {len(HOSTS)} host file(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
