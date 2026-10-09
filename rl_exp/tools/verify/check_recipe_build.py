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

``ClassVar`` is the one thing a *field* comparison cannot see: a statement about a recipe is not
recipe data, so the snapshot (format 2) leaves it out and no diff will ever report it. Those
statements live in the recipe table (``recipe.CLASSVAR_STATEMENTS``, one list) and the declaration
path stamps them onto the class it hands back.

This gate used to hold the transition: for as long as the version class bodies existed, each one
had to state exactly what the table stated. Those bodies are gone (work/closed/2026/recipe-registry-and-diff-declaration.md step 3), so there is
nothing left to compare against -- and the comparison is not silently dropped: a recipe whose
version subclass reappears now fails by name, because a recipe with two expressions is a recipe
whose two expressions can disagree. What the deleted comparison also carried -- "no ClassVar goes
without a home" -- needs no replacement: a ClassVar on the shared wiring is inherited by the
generated class, and a per-recipe one can only be added through the table now.
"""

from __future__ import annotations

import importlib
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
    "lizard2/main": 6,
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
    "lizard2/main": (),
}
"""Versions whose delta is not declared yet, per line. Printed, and red when the list is not this one."""

EXPECTED_DIFFS: dict[tuple[str, str], int] = {
    # Paths each recipe declares, pinned like the other counts: a declaration that quietly shrinks
    # is exactly the failure this gate is built around. A recipe with a mother declares against it
    # (``base.json``); a lineage root has no mother, so it can only declare against the framework
    # stock cfg -- and the whole line's wiring then shows up as that one recipe's delta. A recipe
    # with no declaration at all is legitimate (a root that IS the whole line): it is printed below
    # rather than papered over, because a stock reading would restate the line's heritage as its own
    # delta.
    # lizard2/main v1 is a LINEAGE ROOT (``base.json`` is null): 108 = 65 env paths + 43 agent leaves
    # (the gate counts both halves); it was 107 before 2026-09-22's pre-training revision added the
    # head-contact termination. Pinned at freeze (2026-09-22) -- the declaration is computed from the
    # recipe itself, so this count is the only thing that can notice the day the computation loses a
    # group.
    ("lizard2/main", "v1"): 108,
    # v2's base.json names v1, so this is a LINEAGE reading and the count is small on purpose: the one
    # env path its own delta moves (the legs action group's joint list: the blade patterns leave it)
    # plus the two agent leaves its own runner sets (experiment_name, max_iterations) = 3. A 108 here
    # would mean the emitter had read it as a root and restated v1's whole heritage as v2's delta.
    ("lizard2/main", "v2"): 3,
    # V3 changes only the robot spawn, leg action group and log directory against v2 -- 3 paths until
    # 2026-10-09, when the v3.3 revision gave this version its own `max_iterations = 6000` instead of
    # inheriting v2's 14000, which is a second agent leaf: 2 env + 2 agent = 4. Pinned at the same
    # freeze as v1/v2; a regeneration that loses a group shows up here as a count, not as silence.
    ("lizard2/main", "v3"): 4,
}
"""Recipe -> how many paths its difference declaration lists (``diff.json`` next to the recipe)."""


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


def resurrected_class(version: str, *, play: bool, line: str) -> type | None:
    """A class in the line's wiring module that still builds ``version``: the duplicate is back.

    This gate used to compare the recipe table against the version subclass the recipe replaced.
    Those subclasses were deleted (work/closed/2026/recipe-registry-and-diff-declaration.md step 3), so the comparison has no second side left --
    and instead of dropping the question, it is asked the other way round: if a class like that
    exists again, one recipe has two expressions again, and two expressions is how this migration's
    whole failure mode starts (a field written by a path nobody ran). Constructed and read through
    ``params_version``, which is a field, not a class attribute (1.0's finding).
    """
    module_name = recipe.LINES[line]["base"].__module__
    module = importlib.import_module(module_name)
    base = recipe.LINES[line]["base"]
    # The line's shared wiring, both halves: the module keeps a PLAY sibling beside the base class,
    # and that sibling resolves to *some* version's recipe by default. It is what a recipe is built
    # on, not an expression of one, so it is not what this probe looks for -- the probe is about a
    # recipe class coming back, and those carry the name the registry generated.
    sibling = getattr(module, f"{base.__name__}_PLAY", None)
    wiring = {base, sibling} if isinstance(sibling, type) else {base}
    for value in vars(module).values():
        if not isinstance(value, type) or value in wiring:
            continue
        if getattr(value, "__module__", None) != module_name:
            continue
        if value.__name__.endswith("_PLAY") is not bool(play):
            continue
        instance = _probe(value)
        if instance is not None and getattr(instance, "params_version", None) == version:
            return value
    return None


def attribution(version: str, *, play: bool, paths: list[str], line: str) -> None:
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


_PROBE: dict[type, object | None] = {}


def _probe(cls) -> object | None:
    """One instance per class per gate run: the probe reads a field, it does not compare configs."""
    if cls not in _PROBE:
        try:
            _PROBE[cls] = cls()
        except Exception:  # noqa: BLE001 - a class that cannot be built is not a candidate
            _PROBE[cls] = None
    return _PROBE[cls]


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


def covers(key: str, path: str) -> bool:
    """Does one declared entry cover a changed path? An entry covers its own subtree.

    Direction matters: entries are usually shallower than the paths they cover
    (``rewards.ang_vel_xy_l2`` covers it exactly; ``scene.robot`` covers the twelve fields the
    robot block writes), so every comparison asks whether the *entry* covers the *path*, never
    the other way round.
    """
    return path == key or path.startswith(f"{key}.")


def agent_entry(line_key: str, version: str) -> str:
    """The agent cfg the recipe map names for this recipe's train task.

    Read from the map rather than written into the difference declaration: which class runs a
    recipe is already declared in one place, and a second copy is a second thing to keep in step.
    """
    mapping = lock.recipe_map()
    task_id = recipe.LINES[line_key]["recipes"][version]["train"]
    recipe_key = mapping.get("tasks", {}).get(task_id)
    entry = (mapping.get("recipes", {}).get(recipe_key or "") or {}).get("agent_entry")
    if not isinstance(entry, str) or not entry:
        raise KeyError(f"the recipe map names no agent entry for {task_id}")
    return entry


IDENTITY_FIELDS = ("params_version",)
"""Fields that say *which recipe this is*, not what it does.

Every recipe carries its own value by construction (``build`` asserts it), so a recipe-versus-mother
diff always contains it -- and it is never a difference between the two recipes. Named here rather
than written into twelve declarations, because it is not a statement anybody could get wrong.
"""

WIRING_AUTHOR = "wiring"
"""The shared wiring, reading this recipe's own document (a yaml value no element writes).

The residual writer: if a path is not an element's, this is what produced it, and saying so is more
useful than saying nothing.
"""


def base_of(line_key: str, version: str, declared: dict, paths: list[str]):
    """The two cfgs a difference declaration is read against: ``(subject, base)`` or ``None``.

    The base is not a choice the declaration gets to make: ``base.json`` in the recipe's own
    directory names its mother, and a line root (``null``) can only be compared against the
    framework stock cfg. So the file decides the reading, the declaration only describes it --
    and a stock block on a recipe that has a mother (or the reverse) is a second answer to a
    question that already has one, which is a finding.
    """
    line = discover().get(line_key)
    if line is None:
        paths.append(f"{line_key}: not a discovered recipe line")
        return None
    base_json = line.root / version / "base.json"
    try:
        mother = json.loads(base_json.read_text(encoding="utf-8")).get("base")
    except (OSError, json.JSONDecodeError) as err:
        paths.append(f"{line_key}/{version}: base.json unreadable: {type(err).__name__}: {err}")
        return None
    stock_block = declared.get("base")
    if mother is None and stock_block is None:
        paths.append(
            f"{line_key}/{version}: a line root has no mother, so the declaration has to say what"
            " it is compared against (a stock block naming the framework cfg)"
        )
        return None
    if mother is not None and stock_block is not None:
        paths.append(
            f"{line_key}/{version}: base.json names mother {mother!r}, so the stock block in the"
            " declaration is a second answer to a question that already has one"
        )
        return None
    if mother is None:
        try:
            stock = lock.resolve_entry(stock_block["stock"])()
            wiring = lock.resolve_entry(stock_block["wiring"])(params_version=version)
        except (ImportError, AttributeError, TypeError, KeyError, ValueError) as err:
            paths.append(f"{line_key}/{version}: the declared stock base does not resolve: {type(err).__name__}: {err}")
            return None
        wiring_rows: list = []
        lock.walk_diff(cs.snapshot(stock), cs.snapshot(wiring), "", wiring_rows, limit=1 << 30)
        empty_except = sorted(stock_block["wiring_is_stock_except"])
        if sorted(row[0] for row in wiring_rows) != empty_except:
            paths.append(
                f"{line_key}/{version}: the base the recipe declares is not the stock cfg plus"
                f" {empty_except}: {[row[0] for row in wiring_rows][:5]}"
            )
            return None
        return recipe.build(version, line=line_key), wiring, None
    try:
        return recipe.build(version, line=line_key), recipe.build(mother, line=line_key), mother
    except Exception as err:  # noqa: BLE001 - a missing mother is the finding
        paths.append(f"{line_key}/{version}: mother {mother!r} does not build: {type(err).__name__}: {err}")
        return None


def authored_paths(trace: list[tuple[str, object]], line_key: str, version: str) -> dict[str, set[str]]:
    """What each declared element of this recipe actually moved, replayed step by step.

    A declaration entry is a claim about the declaration, and this is the declaration answering it:
    the same replay the attribution check runs, so the two cannot disagree about what an element
    did.
    """
    step_cfg = recipe.base_cfg(version, line=line_key)
    out: dict[str, set[str]] = {}
    for name, step in trace:
        before = cs.snapshot(step_cfg)
        step(step_cfg)
        moved: list = []
        lock.walk_diff(before, cs.snapshot(step_cfg), "", moved, limit=1 << 30)
        out.setdefault(name, set()).update(row[0] for row in moved)
    return out


def hard_b(line_key: str, version: str, declared: dict, paths: list[str]) -> int:
    """A recipe must differ from its base by exactly the declared list, and each entry must say who.

    Directions, because only one of them looks like a bug:

    * an **undeclared** change is the drift this gate exists for;
    * a **declared** entry that no longer changes anything is how a declaration rots into a
      description of a recipe that moved on;
    * an entry whose **named author does not produce that path** means the list and the declaration
      have stopped agreeing: an *element* author has to have moved it in the replay, and the shared
      wiring is the residual writer, allowed a path only where no element moved it. Rewriting the
      list to go green therefore has to reach the element list, which is the whole reason each entry
      names one;
    * a base that is not what ``base.json`` says it is would make every later comparison
      meaningless, so the claim is checked rather than assumed.

    The gate used to accept a third kind of author (``components.<name>``, resolved through the
    ownership table of the deleted structural-component gate). Those modules retired with the
    historical lines, so a ``components.*`` entry is now just an author that matches no element and
    fails like any other mis-attribution -- the prefix is not a way to be excused from naming a
    writer (acceptance/records/2026-10-09-retired-family-prune-manifest.md, 裁决 §8-G).

    Returns the number of declared paths, or 0 when the declaration could not be checked.
    """
    sides = base_of(line_key, version, declared, paths)
    if sides is None:
        return 0
    subject, base, mother = sides
    identity = {field: True for field in IDENTITY_FIELDS}
    rows: list = []
    lock.walk_diff(cs.snapshot(base), cs.snapshot(subject), "", rows, limit=1 << 30)
    rows = [row for row in rows if row[0].split(".")[0] not in identity]

    allowed = declared["env"]["allowed"]
    flat = sorted({key for group in allowed.values() for key in group["paths"]})
    for author, group in sorted(allowed.items()):
        if not group["paths"]:
            paths.append(f"{line_key}/{version}: group {author!r} declares no path -- empty groups read as coverage")
    leaves = [row[0] for row in rows]
    undeclared = sorted({leaf for leaf in leaves if not any(covers(key, leaf) for key in flat)})
    if undeclared:
        against = f"mother {mother}" if mother else "the declared base"
        paths.append(
            f"{line_key}/{version}: {len(undeclared)} env field(s) differ from {against} without"
            f" being declared: {undeclared[:5]}"
        )
    ineffective = sorted(key for key in flat if not any(covers(key, leaf) for leaf in leaves))
    if ineffective:
        paths.append(
            f"{line_key}/{version}: {len(ineffective)} declared env path(s) no longer differ from"
            f" the base (drop them, or the list describes a recipe that moved on): {ineffective[:5]}"
        )

    trace: list[tuple[str, object]] = []
    recipe.build(version, trace=trace, line=line_key)
    produced = authored_paths(trace, line_key, version)
    for author, group in sorted(allowed.items()):
        # A group is one author set, and the paths in it have to be exactly the paths that set
        # produced: the key is the authorship claim, so a path in the wrong group is a claim about
        # a writer that did not write it. Two kinds, because this gate knows two writers -- the
        # shared wiring (reading the recipe's own document) and the recipe's elements (several of
        # which touch the same path in sequence).
        for key in group["paths"]:
            writers = {name for name, moves in produced.items() if any(covers(key, moved) for moved in moves)}
            if author == WIRING_AUTHOR:
                if writers:
                    paths.append(
                        f"{line_key}/{version}: {key!r} is attributed to {WIRING_AUTHOR}, but"
                        f" elements moved it: {sorted(writers)} -- name them"
                    )
            elif writers != set(author.split("+")) or not writers:
                # No other author kind is recognised: an entry naming anything but an element set or
                # the wiring (the retired ``components.<name>`` prefix included) lands here.
                paths.append(
                    f"{line_key}/{version}: {key!r} is attributed to {author!r} while the elements"
                    f" that moved it are {sorted(writers) or 'none'} -- the list and the element"
                    " list have drifted apart"
                )

    agent = declared["agent"]
    agent_paths = agent["allowed"]
    try:
        agent_subject = lock.resolve_entry(agent_entry(line_key, version))()
        agent_base = lock.resolve_entry(
            agent.get("stock") or agent_entry(line_key, mother)
        )()
    except (ImportError, AttributeError, TypeError, KeyError, ValueError) as err:
        paths.append(f"{line_key}/{version}: the agent cfg does not resolve: {type(err).__name__}: {err}")
        return len(flat) + len(agent_paths)

    agent_rows: list = []
    lock.walk_diff(cs.snapshot(agent_base), cs.snapshot(agent_subject), "", agent_rows, limit=1 << 30)
    agent_leaves = [row[0] for row in agent_rows]
    agent_undeclared = sorted(
        {leaf for leaf in agent_leaves if not any(covers(key, leaf) for key in agent_paths)}
    )
    if agent_undeclared:
        against = f"mother {mother}" if mother else "the stock agent cfg"
        paths.append(
            f"{line_key}/{version}: {len(agent_undeclared)} agent field(s) differ from {against}"
            f" without being declared: {agent_undeclared[:5]}"
        )
    agent_ineffective = sorted(key for key in agent_paths if not any(covers(key, leaf) for leaf in agent_leaves))
    if agent_ineffective:
        paths.append(
            f"{line_key}/{version}: {len(agent_ineffective)} declared agent path(s) no longer differ"
            f" from the base: {agent_ineffective[:5]}"
        )
    return len(flat) + len(agent_paths)


def main(argv: list[str] | None = None) -> int:
    """Gate entry point: build each declared recipe and compare it against the frozen golden."""
    problems: list[str] = []
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
                # What the identity map declares this task's entry to be. Read here because two
                # checks use it: the golden's own record of it (below) and the class built under it.
                declared_entry = mapping.get("recipes", {}).get(recipe_key or "", {}).get("env_cfg_entry")
                declared_name = declared_entry.split(":")[-1] if isinstance(declared_entry, str) else None
                if not declared_name:
                    problems.append(
                        f"{task_id}: the recipe map names no env cfg entry for it -- there is nothing"
                        " for a registry to point at"
                    )
                # The golden records which class produced its entry, and until now nothing compared
                # that column: it is written from the registry and read by no gate, which is exactly
                # how it sat on the deleted version subclasses from the entry switch (2f67f4c) until
                # work/closed/2026/recipe-registry-and-diff-declaration.md step 2a. Held against the identity map rather than the registry -- [31]
                # binds the two byte for byte, so one comparison covers both -- because a golden that
                # names a class which does not produce it is a comparison against the wrong thing.
                claimed_class = stored.get("env_cfg_class")
                if claimed_class != declared_entry:
                    problems.append(
                        f"{task_id}: the golden names {claimed_class!r} as this entry's class while"
                        f" the recipe map declares {declared_entry!r}"
                    )

                try:
                    built = recipe.build(version, play=play, line=line_key)
                except Exception as err:  # noqa: BLE001 - a build that fails is the finding
                    problems.append(f"{task_id}: build failed: {type(err).__name__}: {err}")
                    continue
                declared_version = recipe.declared_params_version(version, line=line_key)
                if getattr(built, "params_version", None) != declared_version:
                    problems.append(
                        f"{task_id}: built cfg carries params_version={getattr(built, 'params_version', None)!r}"
                        f" while the recipe declares {declared_version!r}"
                    )
                # The retired comparison, asked the other way round. It used to require "the recipe
                # table == the version subclass"; the subclasses are deleted (work/closed/2026/recipe-registry-and-diff-declaration.md step 3), so
                # what is left to check is that none comes back. A recipe with two expressions is one
                # whose second expression nobody runs -- which is where every silent divergence in
                # this migration started. Not a "nothing to compare" skip: a missing class was the
                # old failure, a reappearing one is this one.
                duplicate = resurrected_class(version, play=play, line=line_key)
                if duplicate is not None:
                    problems.append(
                        f"{line_key}/{version}/{kind}: {duplicate.__name__} builds this recipe again --"
                        " a recipe has one expression (its declared elements); the class path was"
                        " deleted on purpose (work/closed/2026/recipe-registry-and-diff-declaration.md step 3)"
                    )
                attribution(version, play=play, paths=attribution_problems, line=line_key)
                # The switch's safety: the class a registry entry can point at has to build the
                # same config build() does, or "the declaration path became the training entry"
                # would change the run without changing the declaration. Constructed under the name
                # the identity map declares for this task -- not one derived here -- because a
                # checkpoint payload records ``type(cfg).__name__`` and a resume compares it: the
                # name has to be the map's, or a run started under one path cannot be resumed under
                # the other.
                try:
                    from_class = recipe.recipe_class(version, play=play, line=line_key, name=declared_name)()
                except Exception as err:  # noqa: BLE001 - a class that cannot be built is the finding
                    problems.append(
                        f"{line_key}/{version}/{kind}: recipe_class failed to build: {type(err).__name__}: {err}"
                    )
                else:
                    class_rows: list = []
                    lock.walk_diff(cs.snapshot(from_class), cs.snapshot(built), "", class_rows)
                    if class_rows:
                        problems.append(
                            f"{line_key}/{version}/{kind}: the registrable class and build() disagree on"
                            f" {len(class_rows)} path(s): {class_rows[:3]}"
                        )
                rows: list = []
                lock.walk_diff(stored["snapshot"]["env"], cs.snapshot(built), "", rows)
                if rows:
                    problems.append(
                        f"{task_id}: {len(rows)} field(s) differ from the frozen golden: {rows[:5]}"
                    )
                compared[line_key] += 1

        # hard B: a recipe that declares its difference from the line's base carries diff.json
        for version in sorted(recipe.LINES[line_key]["recipes"]):
            pinned = (line_key, version) in EXPECTED_DIFFS
            declared, error = declared_diff(line_key, version)
            if not pinned:
                # a declaration nobody pinned is a declaration nobody checked: the file is present,
                # so the comparison would look covered while the count it is held to does not exist
                if declared is not None:
                    problems.append(
                        f"{line_key}/{version}: has a difference declaration that no EXPECTED_DIFFS"
                        " entry pins -- an unchecked declaration reads as a checked one"
                    )
                continue
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
    for problem in problems:
        print(f"  FAIL {problem}")
    for line_key in sorted(recipe.LINES):
        waiting = recipe.pending(line_key)
        if waiting:
            print(f"  {line_key}: not declared yet (not compared): {waiting}")
        undeclared_diffs = [
            version
            for version in sorted(recipe.LINES[line_key]["recipes"])
            if (line_key, version) not in EXPECTED_DIFFS
        ]
        if undeclared_diffs:
            # not a failure: a recipe may legitimately have no difference list (a root that is the
            # whole line). Printed because "no declaration" and "declared, and it matches" read the
            # same in a green run otherwise.
            print(f"  {line_key}: no difference declaration (hard A only): {undeclared_diffs}")
    if problems:
        print("RECIPE_BUILD_FAILED")
        return 1
    print(
        f"RECIPE_BUILD_OK ({sum(compared.values())} task(s) field-identical to the frozen golden;"
        f" {sum(declared_paths.values())} declared difference(s) against their own base)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
