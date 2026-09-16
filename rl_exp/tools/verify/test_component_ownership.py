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

from rl_exp.tasks import components
from rl_exp.tasks.teacher_env_cfg import TEACHER_PRIVILEGED_SPEC, RingPatternCfg

# Component -> the scene names it owns; every host below must route writes through it.
OWNERSHIP: dict[str, tuple[str, ...]] = {
    "height_sensing": ("height_scanner", *(f"{foot}_foot_ring" for foot in components.FEET)),
}
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

    problems = form_problems()
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
