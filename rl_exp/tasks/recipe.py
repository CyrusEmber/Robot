# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The recipe builder: one env cfg from what a recipe declares (``ARCH_PLAN.md`` 2.4, stage B3).

The class hierarchy expresses a recipe twice over: once as the shared base wiring, and again as a
chain of per-version subclasses whose ``__post_init__`` each overwrite a few fields. The winner
is whichever class the MRO ran last, so "what is v14" is only readable by replaying every body in
the chain -- and a new recipe means a new class.

The builder keeps the shared wiring (an env cfg whose every structural choice resolves from the
version it is handed) and turns the *deltas* into data: an ordered list of named elements per
recipe. That is the whole point of stage B -- a new recipe becomes a declaration, not a subclass.

A recipe is listed here only once its entire delta is declared. Until then the field is ``None``
and the hard-A gate prints it, because a builder that quietly produced "v14 minus whatever I have
not moved yet" would pass every check it was asked to pass.
"""

from __future__ import annotations

from rl_exp.tasks import teacher_env_cfg
from rl_exp.tasks.play_utils import apply_play_wiring

# Named recipe elements, in application order. An element takes the env cfg and owns its fields
# outright -- the same contract as the five structural components in :mod:`rl_exp.tasks.components`,
# and it gets the same treatment: one writer, resolved by recipe, never by the MRO.
ELEMENTS: dict[str, object] = {}

# What each recipe is: the ordered elements it applies on top of the shared wiring, and the
# registered tasks it claims to reproduce (named, not derived from the version string -- a task id
# is a published name, and a rename must not silently re-point this gate at nothing).
RECIPES: dict[str, dict] = {
    "v1": {"elements": (), "train": "Lizard-Rough-v1", "play": "Lizard-Rough-Play-v1"},
    "v2": {"elements": (), "train": "Lizard-Rough-v2", "play": "Lizard-Rough-Play-v2"},
    # v3's delta (speed curriculum, r_fc, c_k, reset DR) and everything after it are still
    # written as subclass bodies; each moves here as a named element.
    "v3": {"elements": None},
    "v4": {"elements": None},
    "v5": {"elements": None},
    "v6": {"elements": None},
    "v8": {"elements": None},
    "v10": {"elements": None},
    "v11": {"elements": None},
    "v12": {"elements": None},
    "v13": {"elements": None},
    "v14": {"elements": None},
}


def declared() -> list[str]:
    """The recipes whose whole delta is declared, so the builder can produce them."""
    return sorted(version for version, decl in RECIPES.items() if decl["elements"] is not None)


def pending() -> list[str]:
    """The recipes still expressed by their subclass body."""
    return sorted(version for version, decl in RECIPES.items() if decl["elements"] is None)


def build(version: str, *, play: bool = False):
    """The env cfg a recipe declares.

    Args:
        version: recipe version, a key of :data:`RECIPES`.
        play: the deterministic evaluation variant (no randomization, no curriculum).

    Returns:
        The env cfg, built from the shared wiring plus this recipe's declared elements. No
        version subclass is involved.

    Raises:
        ValueError: the recipe's delta is not declared yet, so producing a config would mean
            guessing the missing part.
        KeyError: the version is not a declared recipe at all.
    """
    if version not in RECIPES:
        raise KeyError(f"unknown recipe {version!r}; known: {sorted(RECIPES)}")
    elements = RECIPES[version]["elements"]
    if elements is None:
        raise ValueError(
            f"recipe {version!r}: its delta is not declared yet (declared: {declared()}),"
            f" so the builder cannot produce it without guessing"
        )
    # the version travels as the *field* it is: the shared wiring resolves every structural
    # choice from it, and a subclass that only restated it is exactly what this replaces
    cfg = teacher_env_cfg.LizardRoughTeacherEnvCfg(params_version=version)
    for name in elements:
        ELEMENTS[name](cfg)
    if play:
        apply_play_wiring(cfg)
    return cfg
