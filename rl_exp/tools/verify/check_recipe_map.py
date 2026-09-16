# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Explicit recipe map gate: ARCH_PLAN 2.1's identity half (offline).

``versions/recipes.json`` states, one line at a time, which recipe a task id means and
which config entries that recipe names. Nothing here infers identity from a task id:
the map is authored, and this gate checks it against the registration it is supposed to
describe. That is the whole point -- a task id that quietly loads something else (the
failure the old regex allowed) has to be red, not explained away.

Split with its sibling gate: ``check_recipe_registry`` owns lifecycle (may this line run
at all), this one owns identity (which config is this task). Both consume the same line
handles, so a recipe naming a line the lifecycle index does not have is red here.

Ceiling, deliberate: the registration is read by parsing ``rl_exp/tasks/__init__.py``
with ``ast`` rather than importing the gym registry, so this gate stays stdlib-only and
cannot be taken down by an in-flight edit elsewhere in the tree. ``check_cfg_lock`` reads
the real registry, so the two disagreeing is itself detectable.

The config-side binding -- ``params_version`` on the class versus the declared
``legacy_task_version`` -- belongs to A3, where the identity check stops reading the task
id. Until then the declared value is checked for form and against the task id only.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from recipe_lines import RecipeLineError, discover  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parents[3]
RECIPES = _REPO / "rl_exp" / "versions" / "recipes.json"
TASKS = _REPO / "rl_exp" / "tasks" / "__init__.py"
FORMAT_VERSION = 1
RECIPE_KEYS = ("line", "env_cfg_entry", "agent_entry", "legacy_task_version")
_KEY = re.compile(r"^(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*)@(?P<revision>[1-9][0-9]*)$")

_ENTRY_POINTS = ("env_cfg_entry_point", "rsl_rl_cfg_entry_point")


def registered(path: pathlib.Path = TASKS) -> dict[str, dict[str, str]]:
    """Every ``gym.register`` call in the task registration module, by task id.

    Args:
        path: the module to parse.

    Returns:
        ``{task id: {entry point name: dotted path}}``. A call this parser cannot read
        (a non-literal id or a computed kwargs dict) is reported as an empty mapping
        under its id so that it shows up as a mapping mismatch instead of vanishing.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, dict[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "register":
            continue
        args = {kw.arg: kw.value for kw in node.keywords}
        raw = args.get("id") or (node.args[0] if node.args else None)
        try:
            task_id = ast.literal_eval(raw) if raw is not None else None
        except (ValueError, TypeError):
            task_id = None
        if not isinstance(task_id, str):
            continue
        entries: dict[str, str] = {}
        kwargs = args.get("kwargs")
        if isinstance(kwargs, ast.Dict):
            for key, value in zip(kwargs.keys, kwargs.values):
                if not isinstance(key, ast.Constant) or key.value not in _ENTRY_POINTS:
                    continue
                try:
                    entries[key.value] = ast.literal_eval(value)
                except (ValueError, TypeError):
                    entries[key.value] = ""
        found[task_id] = entries
    return found


def validate(recipes, lines, registered_tasks) -> list[str]:
    """Every identity problem in one pass (empty list = the map describes the tree).

    Args:
        recipes: parsed ``recipes.json``.
        lines: :class:`recipe_lines.RecipeLine` map of the tree under test.
        registered_tasks: task id to entry points, as :func:`registered` returns.

    Returns:
        All problems, sorted by the object they belong to; empty means clean.
    """
    out: list[str] = []
    if not isinstance(recipes, dict):
        return ["recipes.json must be an object"]
    if recipes.get("format") != FORMAT_VERSION:
        out.append(f"format {recipes.get('format')!r} != {FORMAT_VERSION}")
    entries = recipes.get("recipes")
    tasks = recipes.get("tasks")
    if not isinstance(entries, dict) or not isinstance(tasks, dict):
        return out + ["recipes and tasks must both be objects"]

    for key in sorted(entries):
        entry = entries[key]
        if not _KEY.match(key):
            out.append(f"{key}: recipe key must read <id>@<revision>, revision a positive integer")
        if not isinstance(entry, dict):
            out.append(f"{key}: recipe must be an object")
            continue
        missing = [name for name in RECIPE_KEYS if name not in entry]
        extra = sorted(set(entry) - set(RECIPE_KEYS))
        if missing:
            out.append(f"{key}: recipe is missing {missing}")
        if extra:
            out.append(f"{key}: recipe carries unknown fields {extra} (run-scoped data belongs in the run record)")
        if missing or extra:
            continue
        if entry["line"] not in lines:
            out.append(f"{key}: line {entry['line']!r} is not a discovered recipe line")
        if not isinstance(entry["env_cfg_entry"], str) or ":" not in entry["env_cfg_entry"]:
            out.append(f"{key}: env_cfg_entry {entry['env_cfg_entry']!r} is not module:qualname")
        if not isinstance(entry["agent_entry"], str) or ":" not in entry["agent_entry"]:
            out.append(f"{key}: agent_entry {entry['agent_entry']!r} is not module:qualname")
        claimed = entry["legacy_task_version"]
        if claimed is not None and not re.fullmatch(r"v[0-9]+", str(claimed)):
            out.append(f"{key}: legacy_task_version {claimed!r} must be null or v<N>")

    for task_id in sorted(set(registered_tasks) - set(tasks)):
        out.append(f"{task_id}: registered task with no recipe mapping (missing must not fall back to a name)")
    for task_id in sorted(set(tasks) - set(registered_tasks)):
        out.append(f"{task_id}: task mapping names no registered task")
    for task_id in sorted(set(tasks) & set(registered_tasks)):
        key = tasks[task_id]
        if key not in entries:
            out.append(f"{task_id}: maps to {key!r}, which no recipe defines")
            continue
        entry = entries[key]
        if not isinstance(entry, dict):
            continue
        actual = registered_tasks[task_id]
        for field, point in (("env_cfg_entry", "env_cfg_entry_point"), ("agent_entry", "rsl_rl_cfg_entry_point")):
            declared = entry.get(field)
            if declared != actual.get(point):
                out.append(
                    f"{task_id}: registration loads {actual.get(point)!r} but recipe {key} declares "
                    f"{declared!r} -- a task id must not be redirected silently"
                )
        claimed = entry.get("legacy_task_version")
        if claimed is not None and claimed not in task_id.split("-"):
            out.append(
                f"{task_id}: recipe {key} declares legacy_task_version={claimed!r}, which the task id"
                f" never states -- a task id must name the recipe it loads (the reverse reading is"
                f" deliberately absent: the v0 ids say v0 while those configs carry params_version=None)"
            )
    return out


def _build_entry(entry: str):
    """Import and build the config class a recipe names.

    The class attribute is not readable -- the decorator removes it once the dataclass
    exists, so the value only lives on an instance. That is why an identity check has to
    build one rather than read the class.

    Args:
        entry: the ``module:qualname`` a recipe declares.

    Returns:
        The constructed config instance.
    """
    module_name, _, cls_name = entry.partition(":")
    return getattr(importlib.import_module(module_name), cls_name)()


def bind(entries, build=_build_entry) -> list[str]:
    """The config-side half of identity: the built entry carries the declared version and line.

    Args:
        entries: the ``recipes`` mapping of a parsed ``recipes.json``.
        build: turns an entry point into an instance. Injected so the falsifier can drive
            every verdict without importing isaaclab.

    Returns:
        Every mismatch. A class that cannot be built is a problem, never a skip: an
        identity that cannot be shown is not a verified one.
    """
    out: list[str] = []
    for key in sorted(entries):
        entry = entries[key]
        if not isinstance(entry, dict) or not isinstance(entry.get("env_cfg_entry"), str):
            continue
        declared = entry.get("legacy_task_version")
        try:
            cfg = build(entry["env_cfg_entry"])
        except Exception as err:  # any failure at all means the identity cannot be shown
            out.append(f"{key}: cannot build {entry['env_cfg_entry']!r}: {err!r}")
            continue
        actual = getattr(cfg, "params_version", None)
        if actual != declared:
            out.append(
                f"{key}: declared legacy_task_version={declared!r} but {entry['env_cfg_entry']}"
                f" carries params_version={actual!r}"
            )
        actual_line = getattr(cfg, "params_line", None)
        if actual_line != entry.get("line"):
            out.append(
                f"{key}: declares line {entry.get('line')!r} but {entry['env_cfg_entry']}"
                f" carries params_line={actual_line!r}"
                f" -- lifecycle permissions would be read from the wrong line"
            )
    return out


def load(path: pathlib.Path = RECIPES) -> dict:
    """Read the recipe map, or stand in for it when it is missing or unreadable."""
    if not path.is_file():
        return {"_missing": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {"_unreadable": f"{path}: {err}"}


def main(argv: list[str] | None = None) -> int:
    """Gate entry point: discover lines, parse the registration, check the map.

    Args:
        argv: command line, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 when the map describes the tree, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bind-config",
        action="store_true",
        help="also build each declared env cfg entry point and compare its params_version "
        "(needs isaaclab importable; without it the structural half still runs)",
    )
    args = parser.parse_args(argv)
    try:
        lines = discover()
    except RecipeLineError as err:
        print(err)
        return 1
    recipes = load()
    problems = validate(recipes, lines, registered())
    for key in ("_missing", "_unreadable"):
        if key in recipes:
            problems.insert(0, f"{key[1:]}: {recipes[key]}")
    entries = recipes.get("recipes") or {}
    tasks = recipes.get("tasks") or {}
    print(f"  recipes declared: {len(entries)} | task mappings: {len(tasks)} | lines: {sorted(lines)}")
    if args.bind_config:
        bound = bind(entries)
        problems.extend(bound)
        print(f"  config binding: {len(entries)} entries built, {len(bound)} mismatch(es)")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"recipe identity: {len(problems)} problem(s)")
        return 1
    print("  every registered task names a declared recipe with matching entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
