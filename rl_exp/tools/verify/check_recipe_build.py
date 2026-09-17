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

The same rule covers the one thing ``build()`` structurally cannot carry. A ``ClassVar`` is a
statement *about* a recipe, so the snapshot (format 2) leaves it out -- and the declaration path
has no class to put it on: ``build()`` returns the shared base class, whose MRO says nothing
about the version it was handed. Two readers see this differently, and the gate prints the
difference with both values rather than deciding it is harmless:

* ``PLAY_PINS_COMMAND_RANGE`` is read at *construction time*, by the base ``__post_init__``. The
  declaration path reproduces its effect instead of the statement (``play_pins_full_command_range``
  writes the same range afterwards), so the printed gap is already materialized in the fields.
* ``REQUIRES_CURRICULUM_STATE`` is read at *runtime* off ``type(cfg)`` (``curriculum_state``,
  ``runrecord.manifest``). The declaration path cannot state it, and nothing in the fields makes
  up for it -- a real, open gap (``ACCEPTANCE.md`` B3, v5 entry), which is why it is printed on
  every run instead of being fixed by a flag that would only look fixed.
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

EXPECTED_COMPARED = 24
"""How many recipe/task pairs this gate compares, pinned.

The comparison set is whatever ``RECIPES`` declares, so a version whose delta is withdrawn --
or a new one added before its delta is written -- *silently shrinks the subject*: fewer
comparisons, same green. A count is the cheapest way to notice, and the two pins together cover
both directions: ``compared`` falling means a declaration was lost, ``PENDING`` growing means a
subject arrived uncompared. Both numbers are for the state B3 closed at (12 recipes x train/play);
a deliberate change updates them in the same commit that changes the recipes.
"""

EXPECTED_PENDING: tuple[str, ...] = ()
"""Versions whose delta is not declared yet. Printed, and red when the list is not this one."""

EXPECTED_GAPS: dict[str, tuple[str, str]] = {
    "REQUIRES_CURRICULUM_STATE": (
        "read at runtime off type(cfg); the declaration path has no class to state it, and no"
        " field makes up for it",
        "before build() becomes the training entry (ARCH_PLAN 2.4 C2): the reading side must come"
        " from a declaration that survives both paths",
    ),
    "PLAY_PINS_COMMAND_RANGE": (
        "read at construction time by the base __post_init__; the declaration path reproduces its"
        " effect instead of the statement, so the gap is already materialized in the fields",
        "none -- this one is carried in the fields by construction",
    ),
}
"""Gaps this gate tolerates, keyed by ClassVar name: why, and when it must be gone.

A gap whose name is not in this table is a failure: a *new* ClassVar the declaration cannot carry
is exactly the kind of silent divergence the table exists to make somebody notice. Printing every
gap on every run is how a real one becomes wallpaper -- the due column is what makes it a debt.
"""


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


def classvar_gaps(cls, built) -> list[tuple[str, object, object]]:
    """ClassVars ``cls`` states that the built cfg's class does not, as ``(name, stated, carried)``.

    Compared class to class, never through a constructed instance: the point of the check is that
    the declaration path carries no class of its own, so ``type(built)`` is the shared base and a
    name only the version class annotates shows up here. The names come from the snapshot's own
    ``ClassVar`` filter, so "left out of the golden" and "reported here" are one rule, not two.

    Names, not rendered strings: the ledger that decides which gaps are tolerated is keyed by
    what the gap *is*, so a statement that changes value (True -> False) stays the same debt.
    """
    out: list[tuple[str, object, object]] = []
    for name in cs._class_var_names(cls):
        stated = getattr(cls, name, "not stated")
        carried = getattr(type(built), name, "not stated")
        if carried != stated:
            out.append((name, stated, carried))
    return out


def attribution(version: str, *, play: bool, paths: list[str]) -> None:
    """Every declared step must change a field, and every changed field must have a step.

    The builder applies named elements in order (``recipe.build``), and a declaration is only as
    good as the mapping behind it: an element that changes nothing is invisible in a field
    comparison, and a field that changed with no element behind it means the mapping is not the
    whole story. Neither is visible from the golden -- both sides equal, or one side simply not
    listed -- so this replays the recipe step by step and attributes the difference:

    * each step must move at least one field;
    * the union of what the steps moved must be exactly what the recipe moved.

    Args:
        version: the recipe to replay.
        play: replay the evaluation variant (its steps include the shared play wiring).
        paths: collects one line per finding (the gate's report, not an exception).
    """
    trace: list[tuple[str, object]] = []
    built = recipe.build(version, play=play, trace=trace)
    step_cfg = recipe.base_cfg(version)
    moved: set[str] = set()
    for name, step in trace:
        before = cs.snapshot(step_cfg)
        step(step_cfg)
        rows: list = []
        # the diff is asked for everything: the gate's own _DIFF_LIMIT would truncate the
        # attribution and turn "moved nothing" into a claim about the first twenty paths
        lock.walk_diff(before, cs.snapshot(step_cfg), "", rows, limit=1 << 30)
        touched = {row[0] for row in rows}
        if not touched:
            paths.append(f"{version}/{'play' if play else 'train'}: element {name!r} changes nothing")
        moved |= touched
    rows: list = []
    lock.walk_diff(
        cs.snapshot(recipe.base_cfg(version)), cs.snapshot(built), "", rows, limit=1 << 30
    )
    ownerless = {row[0] for row in rows} - moved
    if ownerless:
        paths.append(
            f"{version}/{'play' if play else 'train'}: {len(ownerless)} field(s) changed with no"
            f" declared element behind them: {sorted(ownerless)[:5]}"
        )


def main(argv: list[str] | None = None) -> int:
    """Gate entry point: build each declared recipe and compare it against the frozen golden."""
    problems: list[str] = []
    gaps: dict[str, dict] = {}
    attribution_problems: list[str] = []
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
            # the recipe map names the class this task is built from, so the ClassVar comparison
            # reads a declaration instead of guessing the class name from the version string
            entry = (mapping.get("recipes", {}).get(recipe_key or "") or {}).get("env_cfg_entry")
            try:
                cls = lock.resolve_entry(entry)
            except (ImportError, AttributeError, TypeError, ValueError) as err:
                problems.append(
                    f"{task_id}: recipe {recipe_key!r} entry {entry!r} does not resolve:"
                    f" {type(err).__name__}: {err}"
                )
            else:
                for name, stated, carried in classvar_gaps(cls, built):
                    gaps.setdefault(name, {"values": set(), "recipes": []})
                    gaps[name]["values"].add(f"{stated!r} != {carried!r}")
                    gaps[name]["recipes"].append(f"{version}/{kind}")
            attribution(version, play=play, paths=attribution_problems)
            rows: list = []
            lock.walk_diff(stored["snapshot"]["env"], cs.snapshot(built), "", rows)
            if rows:
                problems.append(
                    f"{task_id}: {len(rows)} field(s) differ from the frozen golden: {rows[:5]}"
                )
            compared += 1

    problems.extend(attribution_problems)
    waiting = tuple(recipe.pending())
    if waiting != EXPECTED_PENDING:
        problems.append(
            f"versions without a declared delta changed ({list(waiting)} != {list(EXPECTED_PENDING)}):"
            " a subject arrived uncompared, or a declaration was withdrawn"
        )
    if compared != EXPECTED_COMPARED:
        problems.append(
            f"compared {compared} recipe/task pair(s), expected {EXPECTED_COMPARED}: the"
            " comparison set shrank or grew without this pin being updated"
        )
    for name, seen in sorted(gaps.items()):
        if name not in EXPECTED_GAPS:
            problems.append(
                f"classvar the declaration cannot carry, and the ledger does not know it: {name}"
                f" -- in {', '.join(seen['recipes'])}"
            )
    for name in sorted(set(EXPECTED_GAPS) - set(gaps)):
        # an entry nobody owes any more is a line that hides the next one
        problems.append(f"the ledger still lists {name}, which is no longer a gap (drop the entry)")

    for problem in problems:
        print(f"  FAIL {problem}")
    if waiting:
        print(f"  not declared yet (not compared): {list(waiting)}")
    # one line per gap class, not one per recipe: eighteen identical lines are a line to skip,
    # and the recipes that share a gap share it for the same reason
    for name, seen in sorted(gaps.items()):
        if name not in EXPECTED_GAPS:
            continue
        print(
            f"  classvar the declaration cannot carry: {name}"
            f" ({', '.join(sorted(seen['values']))}) -- in {', '.join(seen['recipes'])}"
            f"\n    why: {EXPECTED_GAPS[name][0]}\n    due: {EXPECTED_GAPS[name][1]}"
        )
    if problems:
        print("RECIPE_BUILD_FAILED")
        return 1
    print(f"RECIPE_BUILD_OK ({compared} task(s) field-identical to the frozen golden)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
