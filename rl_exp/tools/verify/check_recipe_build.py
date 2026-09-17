# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Hard A and hard B: a built recipe must be its frozen golden, and a new one its declared diff.

Hard A (``ARCH_PLAN.md`` 2.4 B3) has three things that make it a proof rather than a tautology,
and they are the reason it is a separate gate instead of a flag on the golden gate:

* the expectation is the **frozen lock**, read from disk. It was written before the builder
  existed, so it cannot have been shaped by it. A builder compared against its own output would
  be equal by construction -- the failure mode stage B names first.
* the subject is ``recipe.build(version)``, i.e. the **declaration**, not the version subclass.
  The golden gate builds through the class; this one builds through the declaration and no class.
* the comparison is the golden gate's own snapshot and diff, so "identical" here means the same
  thing it means there. Two comparison rules would let a difference hide between them.

A recipe whose delta is not declared yet is *printed*, never skipped: silence reads as "passed",
and a builder that quietly produces "v14 minus whatever has not moved yet" would be green and
wrong. Both counts of the comparison set are pinned per line, so it cannot shrink quietly either.

Hard B (B4) is the other half, and it belongs here rather than in a gate of its own because the
mechanism is the same one: build the declaration, snapshot it with the same serializer, diff it
with the same walker. What differs is the expectation -- not a frozen golden but the recipe's own
``diff.json``, sitting next to the recipe (2.4: "the location is associated with the directory"),
listing the paths where it is allowed to differ from **the framework stock cfg**. The base is the
line's shared wiring, and this gate checks that claim instead of assuming it: a wiring class that
quietly carried a delta would make every later comparison meaningless. All three ledger checks are
two-way -- undeclared change, declared-but-ineffective entry, and a claimed-empty base that is not
empty -- because "only one explicit difference list" means the list and the diff are equal, not
that one contains the other.

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

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cfg_snapshot as cs  # noqa: E402
import check_cfg_lock as lock  # noqa: E402 - sibling gate: snapshot, diff and lock reading
from recipe_lines import discover  # noqa: E402
from rl_exp.tasks import recipe  # noqa: E402

DIFF_NAME = "diff.json"
"""The difference declaration's filename inside a recipe's version directory (``ARCH_PLAN`` 2.4 B4)."""

EXPECTED_COMPARED: dict[str, int] = {
    "lizard/main": 24,
    "lizard/baseline": 2,
}
"""How many recipe/task pairs this gate compares, per line, pinned.

The comparison set is whatever a line's recipe table declares, so a version whose delta is
withdrawn -- or a new one added before its delta is written -- *silently shrinks the subject*:
fewer comparisons, same green. A count is the cheapest way to notice, and the two pins together
cover both directions: a count falling means a declaration was lost, ``EXPECTED_PENDING`` growing
means a subject arrived uncompared. Both numbers are for the state each line closed at; a
deliberate change updates them in the same commit that changes the recipes.
"""

EXPECTED_PENDING: dict[str, tuple[str, ...]] = {
    "lizard/main": (),
    "lizard/baseline": (),
}
"""Versions whose delta is not declared yet, per line. Printed, and red when the list is not this one."""

EXPECTED_DIFFS: dict[tuple[str, str], int] = {
    # hard B: the first new-architecture recipe declares its difference from the framework stock
    # cfg, path by path. Pinned like the other counts -- a declaration that quietly shrinks is
    # exactly the failure this gate is built around.
    ("lizard/baseline", "v1"): 33,
}
"""Recipe -> how many paths its difference declaration lists (``diff.json`` next to the recipe)."""

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


def attribution(version: str, *, play: bool, paths: list[str], line: str = recipe.MAIN_LINE) -> None:
    """Every declared step must change a field, and every changed field must have a step.

    The builder applies named elements in order (``recipe.build``), and a declaration is only as
    good as the mapping behind it: an element that changes nothing is invisible in a field
    comparison, and a field that changed with no element behind it means the mapping is not the
    whole story. Neither is visible from the golden -- both sides equal, or one side simply not
    listed -- so this replays the recipe step by step and attributes the difference:

    * each step must move at least one field;
    * the union of what the steps moved must be exactly what the recipe moved.

    An element may declare rather than change: a recipe that restates a value the base already
    has (to pin it against framework drift) moves nothing, and that is a *statement*, not a dead
    step. Those are named in the recipe's ``pins``, and the list is two-way -- a pin that starts
    moving fields is a pin to drop.

    Args:
        version: the recipe to replay.
        play: replay the evaluation variant (its steps include the shared play wiring).
        paths: collects one line per finding (the gate's report, not an exception).
        line: the recipe line being replayed.
    """
    trace: list[tuple[str, object]] = []
    built = recipe.build(version, play=play, trace=trace, line=line)
    step_cfg = recipe.base_cfg(version, line=line)
    pins = set(recipe.LINES[line]["recipes"][version].get("pins", ()))
    where = f"{line}/{version}/{'play' if play else 'train'}"
    moved: set[str] = set()
    for name, step in trace:
        before = cs.snapshot(step_cfg)
        step(step_cfg)
        rows: list = []
        # the diff is asked for everything: the gate's own _DIFF_LIMIT would truncate the
        # attribution and turn "moved nothing" into a claim about the first twenty paths
        lock.walk_diff(before, cs.snapshot(step_cfg), "", rows, limit=1 << 30)
        touched = {row[0] for row in rows}
        if not touched and name not in pins:
            paths.append(f"{where}: element {name!r} changes nothing")
        if touched and name in pins:
            paths.append(
                f"{where}: element {name!r} is declared a pin (it restates the base value) but"
                f" moves {len(touched)} field(s): drop it from the recipe's pins"
            )
        moved |= touched
    rows: list = []
    lock.walk_diff(cs.snapshot(recipe.base_cfg(version, line=line)), cs.snapshot(built), "", rows, limit=1 << 30)
    ownerless = {row[0] for row in rows} - moved
    if ownerless:
        paths.append(
            f"{where}: {len(ownerless)} field(s) changed with no declared element behind them:"
            f" {sorted(ownerless)[:5]}"
        )


def declared_diff(line_key: str, version: str) -> tuple[dict | None, str | None]:
    """The difference declaration a recipe carries, read from the recipe's own directory.

    Hard B asks a new recipe to declare how it differs from its base, and ARCH_PLAN 2.4 says the
    declaration lives where the recipe does. Resolved from the line and version -- never from a
    path written down twice -- so a recipe that moves cannot leave its declaration behind.
    """
    discovered = discover().get(line_key)
    if discovered is None:
        return None, f"line {line_key!r} is not a discovered recipe line"
    path = discovered.root / version / DIFF_NAME
    if not path.is_file():
        return None, f"no difference declaration at {cs.relativize(str(path))}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as err:
        return None, f"{cs.relativize(str(path))} is not readable JSON: {err}"


def hard_b(line_key: str, version: str, declared: dict, paths: list[str]) -> int:
    """The first new recipe must differ from its base by exactly the declared list.

    Both directions, because only one of them looks like a bug: an **undeclared** change is the
    drift this gate exists for, and a **declared** entry that no longer changes anything is how a
    declaration rots into a description of a recipe that moved on. The recipe's base is the
    framework stock cfg -- pinned by the declaration, and checked here rather than assumed, since
    a wiring class that quietly carried a delta would make every later comparison meaningless.

    Returns the number of declared paths, or 0 when the declaration could not be checked.
    """
    trace: list[tuple[str, object]] = []
    built = recipe.build(version, trace=trace, line=line_key)
    try:
        stock = lock.resolve_entry(declared["base"]["stock"])()
        wiring = lock.resolve_entry(declared["base"]["wiring"])(params_version=version)
    except (ImportError, AttributeError, TypeError, KeyError, ValueError) as err:
        paths.append(f"{line_key}/{version}: the declared base does not resolve: {type(err).__name__}: {err}")
        return 0

    wiring_rows: list = []
    lock.walk_diff(cs.snapshot(stock), cs.snapshot(wiring), "", wiring_rows, limit=1 << 30)
    empty_except = sorted(declared["base"]["wiring_is_stock_except"])
    if sorted(row[0] for row in wiring_rows) != empty_except:
        paths.append(
            f"{line_key}/{version}: the base the recipe declares is not the stock cfg plus"
            f" {empty_except}: {[row[0] for row in wiring_rows][:5]}"
        )

    rows: list = []
    lock.walk_diff(cs.snapshot(wiring), cs.snapshot(built), "", rows, limit=1 << 30)
    allowed = declared["allowed"]
    undeclared = sorted({row[0] for row in rows if not any(row[0] == key or row[0].startswith(f"{key}.") for key in allowed)})
    if undeclared:
        paths.append(
            f"{line_key}/{version}: {len(undeclared)} field(s) differ from the declared base"
            f" without being declared: {undeclared[:5]}"
        )
    ineffective = sorted(key for key in allowed if not any(row[0] == key or row[0].startswith(f"{key}.") for row in rows))
    if ineffective:
        paths.append(
            f"{line_key}/{version}: {len(ineffective)} declared path(s) no longer differ from the"
            f" base (drop them, or the list describes a recipe that moved on): {ineffective[:5]}"
        )
    return len(allowed)


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
    compared: dict[str, int] = dict.fromkeys(recipe.LINES, 0)
    declared_paths: dict[tuple[str, str], int] = {}

    for line_key in sorted(recipe.LINES):
        for version in sorted(recipe.LINES[line_key]["recipes"]):
            decl = recipe.LINES[line_key]["recipes"][version]
            if decl["elements"] is None:
                continue
            for kind, play in (("train", False), ("play", True)):
                task_id = decl.get(kind)
                if not task_id:
                    problems.append(
                        f"{line_key}/{version} ({kind}): no task id declared -- a recipe with"
                        f" nothing to compare against is not expressible, it is untested"
                    )
                    continue
                recipe_key = mapping.get("tasks", {}).get(task_id)
                # the recipe map is a second declaration of which line a task belongs to: if the
                # two disagree, one of them is stale, and a golden read through the wrong line
                # would compare this recipe against somebody else's expectation
                mapped_line = mapping.get("recipes", {}).get(recipe_key or "", {}).get("line")
                if mapped_line != line_key:
                    problems.append(
                        f"{task_id}: the recipe map puts it on {mapped_line!r} while the builder"
                        f" says {line_key!r} -- one of the two is stale"
                    )
                    continue
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
                    built = recipe.build(version, play=play, line=line_key)
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
                attribution(version, play=play, paths=attribution_problems, line=line_key)
                rows: list = []
                lock.walk_diff(stored["snapshot"]["env"], cs.snapshot(built), "", rows)
                if rows:
                    problems.append(
                        f"{task_id}: {len(rows)} field(s) differ from the frozen golden: {rows[:5]}"
                    )
                compared[line_key] += 1

        # hard B: a recipe that declares its difference from the line's base carries diff.json
        for version in sorted(recipe.LINES[line_key]["recipes"]):
            if (line_key, version) not in EXPECTED_DIFFS:
                continue
            declared, error = declared_diff(line_key, version)
            if declared is None:
                problems.append(f"{line_key}/{version}: hard B not checked: {error}")
                continue
            declared_paths[(line_key, version)] = hard_b(line_key, version, declared, problems)

    problems.extend(attribution_problems)
    for line_key, expected in sorted(EXPECTED_PENDING.items()):
        waiting = tuple(recipe.pending(line_key))
        if waiting != expected:
            problems.append(
                f"{line_key}: versions without a declared delta changed ({list(waiting)} !="
                f" {list(expected)}): a subject arrived uncompared, or a declaration was withdrawn"
            )
    for line_key, expected in sorted(EXPECTED_COMPARED.items()):
        if compared[line_key] != expected:
            problems.append(
                f"{line_key}: compared {compared[line_key]} recipe/task pair(s), expected {expected}:"
                " the comparison set shrank or grew without this pin being updated"
            )
    for key, expected in sorted(EXPECTED_DIFFS.items()):
        actual = declared_paths.get(key)
        if actual != expected:
            problems.append(
                f"{key[0]}/{key[1]}: declared {actual} difference path(s), expected {expected}:"
                " the difference list is not the one this pin was written for"
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
    for line_key in sorted(recipe.LINES):
        waiting = recipe.pending(line_key)
        if waiting:
            print(f"  {line_key}: not declared yet (not compared): {waiting}")
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
    print(
        f"RECIPE_BUILD_OK ({sum(compared.values())} task(s) field-identical to the frozen golden;"
        f" {sum(declared_paths.values())} declared difference(s) from the stock base)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
