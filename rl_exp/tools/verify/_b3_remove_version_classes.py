# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""ARCH_PLAN 2.4 / work/closed/2026/recipe-registry-and-diff-declaration.md step 3: delete the version subclass bodies.

The registry has resolved env cfgs through ``recipe_tasks`` since the entry switch, and every
gate now reads the generated classes, so the version subclasses are dead code -- but dead code
that a reader would still take for the definition of a recipe. Deleting them is what makes
"adding a version = adding elements and a table row" true instead of aspirational.

Two things this script must NOT take with them, and checks for:

* the shared wiring (``LizardRoughTeacherEnvCfg`` / ``_PLAY``, ``BaselineWiringCfg``) -- the
  builder's base, referenced from ``recipe.LINES``;
* ``ring_pattern`` / ``RingPatternCfg`` / ``TEACHER_TERRAINS_CFG*`` / ``TEACHER_PRIVILEGED_SPEC``
  -- module-level facts that sit *between* the deleted classes in the file.

Deletion is by class name, located through the AST (decorators included), so it does not depend
on line numbers and it fails loudly if a name is already gone or if a keeper is missing.

One-shot tool, not a gate (underscore prefix, like ``_a0_paths.py``).

Usage:
    python rl_exp\\tools\\verify\\_b3_remove_version_classes.py            # report only
    python rl_exp\\tools\\verify\\_b3_remove_version_classes.py --apply    # rewrite
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]

TARGETS: dict[str, tuple[str, ...]] = {
    "rl_exp/tasks/teacher_env_cfg.py": (
        "LizardRoughTeacherEnvCfg_V1",
        "LizardRoughTeacherEnvCfg_V1_PLAY",
        "LizardRoughTeacherEnvCfg_V2",
        "LizardRoughTeacherEnvCfg_V2_PLAY",
        "LizardRoughTeacherEnvCfg_V3",
        "LizardRoughTeacherEnvCfg_V3_PLAY",
        "LizardRoughTeacherEnvCfg_V4",
        "LizardRoughTeacherEnvCfg_V4_PLAY",
        "LizardRoughTeacherEnvCfg_V5",
        "LizardRoughTeacherEnvCfg_V5_PLAY",
        "LizardRoughTeacherEnvCfg_V6",
        "LizardRoughTeacherEnvCfg_V6_PLAY",
        "LizardRoughTeacherEnvCfg_V8",
        "LizardRoughTeacherEnvCfg_V8_PLAY",
        "LizardRoughTeacherEnvCfg_V10",
        "LizardRoughTeacherEnvCfg_V10_PLAY",
        "LizardRoughTeacherEnvCfg_V11",
        "LizardRoughTeacherEnvCfg_V11_PLAY",
        "LizardRoughTeacherEnvCfg_V12",
        "LizardRoughTeacherEnvCfg_V12_PLAY",
        "LizardRoughTeacherEnvCfg_V13",
        "LizardRoughTeacherEnvCfg_V13_PLAY",
        "LizardRoughTeacherEnvCfg_V14",
        "LizardRoughTeacherEnvCfg_V14_PLAY",
    ),
    "rl_exp/tasks/baseline_env_cfg.py": (
        "BaselineFlatEnvCfg",
        "BaselineFlatEnvCfg_PLAY",
    ),
}

# what must survive the deletion, per file -- the wiring the builder stands on and the
# module-level facts that live between the deleted classes
KEEP: dict[str, tuple[str, ...]] = {
    "rl_exp/tasks/teacher_env_cfg.py": (
        "LizardRoughTeacherEnvCfg",
        "LizardRoughTeacherEnvCfg_PLAY",
        "TeacherActionsCfg",
        "TEACHER_PRIVILEGED_SPEC",
        "TEACHER_TERRAINS_CFG",
        "ring_pattern",
        "RingPatternCfg",
        "_load_params",
    ),
    "rl_exp/tasks/baseline_env_cfg.py": (
        "BaselineWiringCfg",
        "BaselineActionsCfg",
        "_load_params",
    ),
}


def _top_level(tree: ast.Module) -> dict[str, ast.stmt]:
    """Top-level names this file defines: classes, functions and module-level assignments.

    ``AnnAssign`` counts: the specs in these modules are annotated (``X: dict[str, set[str]]``),
    and a keeper check that cannot see them would refuse a plan that is in fact fine.
    """
    names: dict[str, ast.stmt] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names[target.id] = node
    return names


def _span(node: ast.stmt) -> tuple[int, int]:
    """Half-open 0-based line span of a statement, decorators included."""
    first = min([node.lineno, *[decorator.lineno for decorator in getattr(node, "decorator_list", [])]])
    return first - 1, node.end_lineno


def plan(path: str) -> tuple[list[tuple[str, int, int]], list[str]]:
    text = (_REPO / path).read_text(encoding="utf-8")
    nodes = _top_level(ast.parse(text))
    rows: list[tuple[str, int, int]] = []
    problems: list[str] = []
    for name in TARGETS[path]:
        node = nodes.get(name)
        if node is None:
            problems.append(f"{path}: {name} is not a top-level class any more (already removed?)")
            continue
        rows.append((name, *_span(node)))
    for name in KEEP[path]:
        if name not in nodes:
            problems.append(f"{path}: {name} is missing -- it must outlive this script")
    return sorted(rows, key=lambda row: row[1]), problems


def apply(path: str) -> None:
    rows, problems = plan(path)
    if problems:
        raise SystemExit("\n".join(problems))
    lines = (_REPO / path).read_text(encoding="utf-8").splitlines(keepends=True)
    spans = [(start, end) for _, start, end in rows]
    kept = [line for index, line in enumerate(lines) if not any(start <= index < end for start, end in spans)]
    (_REPO / path).write_text("".join(kept), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", default=False)
    args = parser.parse_args(argv)
    refused = False
    for path in sorted(TARGETS):
        rows, problems = plan(path)
        print(f"{path}: {len(rows)} class(es) to delete")
        for name, start, end in rows:
            print(f"  {name}: lines {start + 1}-{end} ({end - start} line(s))")
        for problem in problems:
            print(f"  PROBLEM: {problem}")
        refused = refused or bool(problems)
    if refused:
        print("B3_REMOVE_REFUSED")
        return 1
    if args.apply:
        for path in sorted(TARGETS):
            apply(path)
        print("B3_REMOVE_APPLIED")
    else:
        print("B3_REMOVE_PLAN_OK (dry run; pass --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
