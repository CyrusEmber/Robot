# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The declared recipes as registrable classes (ARCH_PLAN 2.4 C2: the entry switch).

A task registration names a class, so "the recipe is a declaration" only becomes the training
entry if a class exists that builds it. This module is that seam and nothing else: one class per
declared recipe and kind, named exactly as the class it replaces, so anything that records
``type(cfg).__name__`` (a checkpoint payload does, and a resume compares it) cannot tell which of
the two paths produced a run.

The names come from ``versions/recipes.json`` -- the identity map every gate already routes by --
rather than from a list written here, because a second list is what this whole migration exists to
remove. Nothing needs to import this module explicitly: the registry names it as a string, and
``string_to_callable`` imports it on demand.

Resolution is **per name, on demand** (module ``__getattr__``), and each line is built by its own
constructor. Both halves are load-bearing:

* one line's classes are never built while resolving another's, so importing the baseline task
  does not drag in the main line (``versions/lizard/baseline/PLAN.md``: that line does not import
  another line's cfg or mdp);
* a name is built once and cached, and no bulk update can overwrite it with a class from a second
  path -- "one recipe, one expression" is why the version subclasses were deleted, and a cache that
  silently swaps an object breaks the same rule at runtime.

``check_recipe_build`` asserts, for every recipe, that the class resolved here is field-for-field
what ``recipe.build()`` produces; that is what makes "the switch changed the entry, not the run" a
checked claim instead of a hope.
"""

from __future__ import annotations

import json
import pathlib

_MODULE = "rl_exp.tasks.recipe_tasks"
_LINES_BUILT_ELSEWHERE = {"lizard/baseline"}
"""Lines whose classes their own module builds, so resolving one never imports the main line.

The baseline line is the case: its recipe code is independent by contract (``baseline/PLAN.md``
§与其它线的边界), and ``baseline_recipe.recipe_class`` is what makes that true at import time.
Its key is the same string ``baseline_env_cfg._LINE_KEY`` and the identity map's ``line`` field
carry; ``test_baseline_isolation.py`` asserts this table has no entry no declared task claims.
"""

_RECIPES_JSON = pathlib.Path(__file__).resolve().parents[1] / "versions" / "recipes.json"


def _identity_map(mapping: dict | None = None) -> dict:
    """``versions/recipes.json``, read or injected."""
    if mapping is not None:
        return mapping
    return json.loads(_RECIPES_JSON.read_text(encoding="utf-8"))


def _own_entries(mapping: dict | None = None) -> dict[str, dict]:
    """``class name -> {task, line, recipe}`` for the entries this module is the declared home of.

    The map keeps the two halves apart on purpose -- ``tasks`` says which recipe a task id means,
    ``recipes`` says what that recipe builds -- so the name is joined through them rather than
    guessed from the task id's shape.

    Only entries whose ``env_cfg_entry`` names *this* module are kept. The map is the family's, and
    parkour's two entries are the parkour module's classes: a name collected here is a promise that
    ``getattr`` can produce it (``__all__`` is built from this dict), and a promise the module
    cannot keep is worse than a missing entry. A name two tasks both claim would collapse into one
    entry; ``check_configclass_fields`` cross-checks the exports against the map, which is what
    makes that visible rather than silent.

    Args:
        mapping: the identity map, defaulting to the file on disk.

    Returns:
        Class name -> the task, line and recipe key that declare it.
    """
    document = _identity_map(mapping)
    by_recipe = document.get("recipes") or {}
    out: dict[str, dict] = {}
    for task_id, recipe_key in (document.get("tasks") or {}).items():
        entry = by_recipe.get(recipe_key) or {}
        module, _, name = str(entry.get("env_cfg_entry") or "").partition(":")
        if module != _MODULE or not name:
            continue
        out[name] = {"task": task_id, "line": entry.get("line"), "recipe": recipe_key}
    return out


def _builder(line: str):
    """``(its recipe table, its constructor)`` for ``line`` -- each line owns its own.

    A line listed in :data:`_LINES_BUILT_ELSEWHERE` is imported here and built by its own module;
    every other line is built by the main declaration module. The point of the split is that the
    baseline half is never imported to resolve the other half, and vice versa.

    Args:
        line: family-relative line handle, as the identity map states it.

    Returns:
        The line's recipe table and a ``(version, *, play, name) -> type`` constructor.
    """
    if line in _LINES_BUILT_ELSEWHERE:
        from rl_exp.tasks import baseline_recipe

        def build_baseline(version: str, *, play: bool, name: str) -> type:
            return baseline_recipe.recipe_class(version, play=play, name=name)

        return baseline_recipe.BASELINE_RECIPES, build_baseline

    from rl_exp.tasks import recipe

    def build_main(version: str, *, play: bool, name: str) -> type:
        return recipe.recipe_class(version, play=play, line=line, name=name)

    return recipe.LINES[line]["recipes"], build_main


def class_for(name: str) -> type:
    """The class ``name`` resolves to, built by the line that declares it.

    Args:
        name: the class name a registry entry declares (the part after ``:``).

    Returns:
        The generated config class.

    Raises:
        AttributeError: ``name`` is not a class this module declares, or the recipe it belongs to
            is declared nowhere yet (no declaration to build from, so a class for it could only
            guess -- the gates would rather see it missing than invented).
    """
    entry = _own_entries().get(name)
    if entry is None:
        raise AttributeError(f"{name!r} is not a class {_MODULE} declares")
    table, build = _builder(entry["line"])
    for version, declaration in table.items():
        if declaration["elements"] is None:
            continue
        for kind, play in (("train", False), ("play", True)):
            if declaration.get(kind) == entry["task"]:
                return build(version, play=play, name=name)
    raise AttributeError(
        f"{name!r}: no declared recipe of line {entry['line']!r} builds task {entry['task']!r}"
    )


def __getattr__(name: str) -> type:
    """Resolve one class, cache it, and never let a second path overwrite it.

    ``__getattr__`` runs only while the name is absent from the module namespace, so the first
    resolution wins and every later ``getattr`` (including ``string_to_callable``'s, and the
    trainer's own entry-point import) hands back the same object.
    """
    cls = class_for(name)
    globals()[name] = cls
    return cls


__all__ = sorted(_own_entries())


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
