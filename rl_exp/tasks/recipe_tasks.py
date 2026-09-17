# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The declared recipes as registrable classes (ARCH_PLAN 2.4 C2: the entry switch).

A task registration names a class, so "the recipe is a declaration" only becomes the training
entry if a class exists that builds it. This module is that seam and nothing else: one generated
class per declared recipe and kind, named exactly as the class it replaces, so anything that
records ``type(cfg).__name__`` (a checkpoint payload does, and a resume compares it) cannot tell
which of the two paths produced a run.

The names come from ``versions/recipes.json`` -- the identity map every gate already routes by --
rather than from a list written here, because a second list is what this whole migration exists to
remove. Nothing needs to import this module explicitly: the registry names it as a string, and
``string_to_callable`` imports it on demand.

``check_recipe_build`` asserts, for every recipe, that the class built here is field-for-field what
``recipe.build()`` produces; that is what makes "the switch changed the entry, not the run" a
checked claim instead of a hope.
"""

from __future__ import annotations

import json
import pathlib

from rl_exp.tasks import recipe

_RECIPES_JSON = pathlib.Path(__file__).resolve().parents[1] / "versions" / "recipes.json"


def _registered_names(mapping: dict | None = None) -> dict[str, str]:
    """``task id -> env cfg class name``, read from the identity map (never from a list here).

    The map keeps the two halves apart on purpose -- ``tasks`` says which recipe a task id means,
    ``recipes`` says what that recipe builds -- so the name is joined through them rather than
    guessed from the task id's shape.
    """
    mapping = mapping or json.loads(_RECIPES_JSON.read_text(encoding="utf-8"))
    by_recipe = mapping.get("recipes") or {}
    out: dict[str, str] = {}
    for task_id, recipe_key in (mapping.get("tasks") or {}).items():
        entry = by_recipe.get(recipe_key) or {}
        value = entry.get("env_cfg_entry")
        if isinstance(value, str) and ":" in value:
            out[task_id] = value.split(":")[1]
    return out


def generate() -> dict[str, type]:
    """Materialize one class per declared recipe and kind, keyed by the name it must carry.

    Returns:
        ``{class name: class}``. A recipe whose delta is not declared yet is skipped: it has no
        declaration to build from, so a class for it could only guess (and the gates would rather
        see it missing than invented).
    """
    names = _registered_names()
    generated: dict[str, type] = {}
    for line_key, line in recipe.LINES.items():
        for version, entry in line["recipes"].items():
            if entry["elements"] is None:
                continue
            for kind, play in (("train", False), ("play", True)):
                declared = entry.get(kind)
                if not isinstance(declared, str) or declared not in names:
                    continue
                name = names[declared]
                generated[name] = recipe.recipe_class(version, play=play, line=line_key, name=name)
    return generated


globals().update(generate())
