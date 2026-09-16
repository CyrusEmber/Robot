# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Hard A: a built recipe must be field-for-field the frozen golden (``ARCH_PLAN.md`` 2.4, B3).

Three things make this a proof rather than a tautology, and they are the reason it is a separate
gate instead of a flag on the golden gate:

* the expectation is the **frozen lock**, read from disk. It was written before the builder
  existed, so it cannot have been shaped by it. A builder compared against its own output would
  be equal by construction -- the failure mode stage B names first.
* the subject is ``recipe.build(version)``, i.e. the **declaration**, not the version subclass.
  The golden gate builds through the class; this one builds through the declaration and no class.
* the comparison is the golden gate's own snapshot and diff, so "identical" here means the same
  thing it means there. Two comparison rules would let a difference hide between them.

A recipe whose delta is not declared yet is *printed*, never skipped: silence reads as "passed",
and a builder that quietly produces "v14 minus whatever has not moved yet" would be green and
wrong.
"""

from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cfg_snapshot as cs  # noqa: E402
import check_cfg_lock as lock  # noqa: E402 - sibling gate: snapshot, diff and lock reading
from recipe_lines import discover  # noqa: E402
from rl_exp.tasks import recipe  # noqa: E402


def frozen_entries(line_key: str, cache: dict[str, dict]) -> tuple[dict, str | None]:
    """The frozen golden entries of the line a recipe declares it belongs to.

    Args:
        line_key: family-relative line handle, from the recipe map (a declaration, not a guess).
        cache: per-line entry cache, so one line is read once.

    Returns:
        The entries by ``<combination>|<task id>``, and an error when they cannot be read.
    """
    if line_key in cache:
        return cache[line_key], None
    line = discover().get(line_key)
    if line is None:
        return {}, f"line {line_key!r} is not a discovered recipe line"
    entries, error = lock.load_entries(line)
    cache[line_key] = entries
    return entries, error


def main(argv: list[str] | None = None) -> int:
    """Gate entry point: build each declared recipe and compare it against the frozen golden."""
    problems: list[str] = []
    mapping = lock.recipe_map()
    try:
        combo_key = lock.combination_key(lock.combination())
    except Exception as err:  # noqa: BLE001 - an unresolvable combination means no baseline to read
        print(f"  FAIL framework combination unresolvable: {type(err).__name__}: {err}")
        print("RECIPE_BUILD_FAILED")
        return 1
    cache: dict[str, dict] = {}
    compared = 0

    for version in sorted(recipe.RECIPES):
        decl = recipe.RECIPES[version]
        if decl["elements"] is None:
            continue
        for kind, play in (("train", False), ("play", True)):
            task_id = decl.get(kind)
            if not task_id:
                problems.append(
                    f"{version} ({kind}): no task id declared -- a recipe with nothing to compare"
                    f" against is not expressible, it is untested"
                )
                continue
            recipe_key = mapping.get("tasks", {}).get(task_id)
            line_key = mapping.get("recipes", {}).get(recipe_key or "", {}).get("line")
            entries, error = frozen_entries(line_key, cache)
            if error:
                problems.append(f"{task_id}: {error}")
                continue
            stored = entries.get(f"{combo_key}|{task_id}")
            if stored is None:
                problems.append(
                    f"{task_id}: the frozen golden has no entry for combination {combo_key!r}"
                )
                continue

            try:
                built = recipe.build(version, play=play)
            except Exception as err:  # noqa: BLE001 - a build that fails is the finding
                problems.append(f"{task_id}: build failed: {type(err).__name__}: {err}")
                continue
            if getattr(built, "params_version", None) != version:
                problems.append(
                    f"{task_id}: built cfg carries params_version={getattr(built, 'params_version', None)!r}"
                    f" while the recipe is {version!r}"
                )
            rows: list = []
            lock.walk_diff(stored["snapshot"]["env"], cs.snapshot(built), "", rows)
            if rows:
                problems.append(
                    f"{task_id}: {len(rows)} field(s) differ from the frozen golden: {rows[:5]}"
                )
            compared += 1

    for problem in problems:
        print(f"  FAIL {problem}")
    waiting = recipe.pending()
    if waiting:
        print(f"  not declared yet (not compared): {waiting}")
    if problems:
        print("RECIPE_BUILD_FAILED")
        return 1
    print(f"RECIPE_BUILD_OK ({compared} task(s) field-identical to the frozen golden)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
