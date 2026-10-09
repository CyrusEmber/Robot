# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The recipe builder: one env cfg from what a recipe declares (``ARCH_PLAN.md`` 2.4, stage B3).

The class hierarchy expressed a recipe twice over: once as the shared base wiring, and again as a
chain of per-version subclasses whose ``__post_init__`` each overwrote a few fields. The winner was
whichever class the MRO ran last, so "what is a version" was only readable by replaying every body
in the chain -- and a new recipe meant a new class. Those chains are gone
(``acceptance/records/2026-10-09-retired-family-prune-manifest.md``); the one line left, the lizard2
family's, states its elements in :mod:`rl_exp.tasks.lizard2_recipe` and is read through this module.

The builder keeps the shared wiring (an env cfg whose every structural choice resolves from the
version it is handed) and turns the *deltas* into data: an ordered list of named elements per
recipe. That is the whole point of stage B -- a new recipe becomes a declaration, not a subclass.

A recipe is listed here only once its entire delta is declared. Until then the field is ``None``
and the hard-A gate prints it, because a builder that quietly produced "vN minus whatever I have
not moved yet" would pass every check it was asked to pass.
"""

from __future__ import annotations

from typing import ClassVar

from rl_exp.tasks import curriculum_state as cstate
from rl_exp.tasks import lizard2_env_cfg, lizard2_recipe, recipe_params
from rl_exp.tasks.play_utils import apply_play_wiring
from rl_exp.tasks.recipe_factory import make_class


def _doc(cfg) -> dict:
    """This recipe's parameters document.

    Read through the line the cfg declares (``params_line``) and the version it carries, so an
    element cannot read another recipe's numbers by accident -- which is the whole reason the
    version is a field and not a class name.
    """
    return recipe_params.load(cfg.params_line, cfg.params_version)


# The lizard2 family's main line: a new family (its own USD asset, its own 30-joint skeleton) with
# the retired baseline line's shape -- flat ground, one version per frozen recipe, and a declaration
# module of its own that exports both the element map and the recipe table, so nothing below has to
# know an element name.
LIZARD2_LINE = "lizard2/main"
LIZARD2_RECIPES = lizard2_recipe.LIZARD2_RECIPES

# Line -> its shared wiring and its recipe table. Keyed by the same family-relative handle the
# recipe map and the golden locks use, so "which line is this" has one answer everywhere.
LINES: dict[str, dict] = {
    LIZARD2_LINE: {"base": lizard2_env_cfg.Lizard2WiringCfg, "recipes": LIZARD2_RECIPES},
}


def declared(line: str = LIZARD2_LINE) -> list[str]:
    """The recipes of ``line`` whose whole delta is declared, so the builder can produce them."""
    return sorted(version for version, decl in LINES[line]["recipes"].items() if decl["elements"] is not None)


def pending(line: str = LIZARD2_LINE) -> list[str]:
    """The recipes of ``line`` whose delta is not declared yet, so no class can be built for them."""
    return sorted(version for version, decl in LINES[line]["recipes"].items() if decl["elements"] is None)


def declaration(version: str, *, play: bool = False, line: str = LIZARD2_LINE) -> bool | None:
    """Whether ``line``'s ``version`` promises a resumable curriculum state, or None if unstated.

    The promise is a *statement about* a recipe, so the snapshot leaves it out (format 2 excludes
    ``ClassVar``) and it is carried as a ``ClassVar`` on the built config rather than as a field --
    a field would enter the frozen golden and re-anchor every lock. The statement lives in the
    recipe table, and ``check_recipe_build`` reports a version class that reappears as a second
    expression of the same recipe, so a drifted table is red instead of quiet.

    Args:
        version: recipe version, a key of this line's recipe table.
        play: the evaluation variant (a PLAY task never resumes a curriculum by construction).
        line: family-relative line handle, a key of :data:`LINES`.

    Returns:
        ``True``/``False`` when the recipe states it, ``None`` when it does not state it at all
        (``build`` then leaves the shared wiring's own statement alone).
    """
    return _stated(version, "declares", play=play, line=line)


def pins_full_range(version: str, *, play: bool = False, line: str = LIZARD2_LINE) -> bool | None:
    """Whether ``line``'s ``version`` pins the full forward range, or None if unstated.

    The second ``ClassVar`` a version class used to state (``PLAY_PINS_COMMAND_RANGE``), carried
    the same way and for the same reason. Its reader is the shared wiring's ``__post_init__``, i.e.
    *construction* time: a play variant of a recipe whose curriculum cannot widen the range asks for
    the full one instead of the curriculum's window. Reproducing that effect with a
    play element afterwards -- which is what the builder did while the table was silent -- leaves
    the statement itself unstated, and a statement that only exists on a class body dies with it.

    Args:
        version: recipe version, a key of this line's recipe table.
        play: the evaluation variant.
        line: family-relative line handle, a key of :data:`LINES`.

    Returns:
        ``True``/``False`` when the recipe states it, ``None`` when it does not state it at all.
    """
    return _stated(version, "pins_full_range", play=play, line=line)


def _stated(version: str, key: str, *, play: bool, line: str) -> bool | None:
    """One ``(train, play)`` statement from a recipe table, or None when the recipe does not state it."""
    entry = LINES[line]["recipes"].get(version) or {}
    stated = entry.get(key)
    return None if stated is None else bool(stated[1 if play else 0])


def declared_params_version(version: str, *, line: str = LIZARD2_LINE):
    """The ``params_version`` this recipe carries: the table key, unless the recipe states its own.

    The key is a *handle* -- what the table is keyed by and what gates iterate -- and the field value
    is a separate fact, because "a recipe with no frozen version" is a real thing here: the retired
    family's four dev-state envs read the live yaml and recorded no version at all
    (``legacy_task_version: null`` in the identity map, ``params_version`` written as ``None`` on
    the class). Reading the version off the key would have forced a version token they do not have,
    which the golden and the identity map would then disagree with.

    Args:
        version: recipe version, a key of this line's recipe table.
        line: family-relative line handle, a key of :data:`LINES`.

    Returns:
        The declared ``params_version`` (a version string, or ``None`` for a dev-state recipe).
    """
    return LINES[line]["recipes"][version].get("params_version", version)


def recipe_base(version: str, *, line: str = LIZARD2_LINE):
    """The shared wiring this recipe is built on: the line's, unless the recipe names its own.

    The override exists because one line can hold two wiring roots: the retired family's frozen
    recipes built on its teacher wiring and its four dev-state envs on the family wiring -- same
    robot stack, same dev yaml (their ``params_line`` was that line), different constructor. A base
    per *line* would have forced those envs onto a second line, and a second line needs its own
    ``<line>_params.yaml``: two SSOTs for one set of numbers, which is exactly what
    :mod:`rl_exp.tasks.recipe_params` exists to prevent. lizard2 states no per-recipe base.
    """
    entry = LINES[line]["recipes"][version]
    return entry.get("base") or LINES[line]["base"]


# The ClassVars a version class used to state about its recipe, and the accessor that now reads
# each of them from the recipe table. One list, so "which statements must move off the class
# bodies" has a single answer -- and so a name that has not moved yet shows up as a gap rather
# than as a statement nobody notices is missing.
CLASSVAR_STATEMENTS: tuple[tuple[str, object], ...] = (
    (cstate.REQUIRES_CURRICULUM_STATE, declaration),
    ("PLAY_PINS_COMMAND_RANGE", pins_full_range),
)


def _wired_class(version: str, *, play: bool, line: str):
    """The class to construct: the line's shared wiring, plus the recipe's own statements.

    A synthesized subclass, for one reason: four readers ask ``type(cfg)`` whether this task
    promises a curriculum state -- the resume path, the save guard, the trainer's import guard and
    the run manifest -- and a builder that returns the bare shared class silently answers "no" for
    a recipe that declares yes. Carrying the statement on the class keeps those readers unchanged
    and keeps the statement out of the snapshot. The class name is the shared wiring's, so nothing
    that records ``type(cfg).__name__`` moves.
    """
    base = recipe_base(version, line=line)
    stated: dict[str, bool] = {}
    for classvar, accessor in CLASSVAR_STATEMENTS:
        value = accessor(version, play=play, line=line)
        if value is not None:
            stated[classvar] = value
    if not stated:
        return base
    # annotated as a ClassVar, not merely set: the snapshot tells the two apart by the
    # annotation (cfg_snapshot._class_var_names), so an unannotated attribute would enter the
    # frozen-golden comparison as a field the golden does not have -- a statement is not data
    return type(
        base.__name__,
        (base,),
        {
            "__annotations__": {name: ClassVar[bool] for name in stated},
            **stated,
        },
    )


def base_cfg(version: str, *, line: str = LIZARD2_LINE, play: bool = False):
    """The shared wiring a recipe starts from, before any of its own elements are applied.

    Public because the attribution check has to start where the builder starts: a checker that
    built its own base would drift from this one without either side noticing. It carries the
    recipe's statement for the same reason ``build`` does -- otherwise the statement itself would
    read as a field changed by nobody.
    """
    return _wired_class(version, play=play, line=line)(params_version=declared_params_version(version, line=line))


def apply_into(cfg, version: str, *, play: bool = False, line: str = LIZARD2_LINE, trace: list | None = None):
    """Apply this recipe's declared steps to an existing cfg -- ``build``'s body, as a function.

    Shared by :func:`build` and :func:`recipe_class` so the two mechanisms cannot drift: one
    applies the steps to an instance the caller holds (and can trace), the other applies them
    during construction, which is what a registry entry needs.

    Args:
        cfg: the cfg to subject to the recipe (usually the shared wiring's instance).
        version: recipe version, a key of this line's recipe table.
        play: also apply the shared PLAY wiring and the recipe's evaluation elements.
        line: family-relative line handle, a key of :data:`LINES`.
        trace: when a list is given, every step is appended as ``(name, callable)``.

    Returns:
        The same cfg, for chaining.
    """
    entry = LINES[line]["recipes"][version]
    # the line's element map: lizard2 exports its own, so the names a table states resolve here
    # without this module knowing one of them
    elements = lizard2_recipe.ELEMENTS
    for name in entry["elements"]:
        elements[name](cfg)
        if trace is not None:
            trace.append((name, elements[name]))
    if play:
        # the shared PLAY wiring first, then the recipe's own evaluation-determinism elements:
        # they undo parts of what the recipe just built (a curriculum that would widen the range
        # mid-eval, a range that no longer has a curriculum to climb it)
        apply_play_wiring(cfg)
        if trace is not None:
            trace.append(("apply_play_wiring", apply_play_wiring))
        for name in entry["play_elements"]:
            elements[name](cfg)
            if trace is not None:
                trace.append((name, elements[name]))
    return cfg


def recipe_class(version: str, *, play: bool = False, line: str = LIZARD2_LINE, name: str | None = None):
    """The class a registry entry can point at: the shared wiring, wired by its declared steps.

    A class, because that is what a task registration resolves: hydra instantiates the entry point
    with no arguments, so "the recipe" has to be expressible as a constructor. The steps run in
    ``__post_init__`` -- the same place the version subclass bodies ran theirs -- which is what
    makes the declaration path usable as *the training entry* rather than only as a comparison
    subject. ``check_recipe_build`` compares this class against :func:`build` field for field, so
    the two ways of applying one recipe cannot diverge.

    Args:
        version: recipe version, a key of this line's recipe table.
        play: the deterministic evaluation variant.
        line: family-relative line handle, a key of :data:`LINES`.
        name: the class name to use, defaulting to a name derived from the line and version. A
            caller that replaces a registered class passes that class's own name, so anything
            recording ``type(cfg).__name__`` (a checkpoint payload does) cannot tell the two
            paths apart and a resume may cross them.

    Returns:
        The config class. Construct it with no arguments.

    Raises:
        KeyError: the line or the version is not declared.
        ValueError: the recipe's delta is not declared yet.
    """
    if line not in LINES:
        raise KeyError(f"unknown recipe line {line!r}; known: {sorted(LINES)}")
    recipes = LINES[line]["recipes"]
    if version not in recipes:
        raise KeyError(f"unknown recipe {version!r} on {line}; known: {sorted(recipes)}")
    if recipes[version]["elements"] is None:
        raise ValueError(
            f"recipe {version!r} on {line}: its delta is not declared yet (declared: {declared(line)}),"
            " so a class for it would have to guess the missing part"
        )
    base = recipe_base(version, line=line)

    statements = {
        classvar: value
        for classvar, accessor in CLASSVAR_STATEMENTS
        if (value := accessor(version, play=play, line=line)) is not None
    }
    return make_class(
        base, name=name or f"{base.__name__}_{line.split('/')[-1]}_{version}{'_PLAY' if play else ''}",
        version=declared_params_version(version, line=line), statements=statements,
        apply=lambda cfg: apply_into(cfg, version, play=play, line=line),
        description=f"{line}/{version}{'/play' if play else ''}, built from its declared elements.",
    )


def build(version: str, *, play: bool = False, trace: list | None = None, line: str = LIZARD2_LINE):
    """The env cfg a recipe declares.

    Args:
        version: recipe version, a key of this line's recipe table.
        play: the deterministic evaluation variant (no randomization, no curriculum).
        trace: when a list is given, every step is appended to it as ``(name, callable)``, in
            application order -- so a reader can replay the recipe instead of restating its
            order (and drift from it).
        line: family-relative line handle, a key of :data:`LINES`. The version counter is
            per-line, so two lines both having a ``"v1"`` is the normal case, not a collision.

    Returns:
        The env cfg, built from that line's shared wiring plus this recipe's declared elements.
        No version subclass is involved.

    Raises:
        KeyError: the line or the version is not declared.
        ValueError: the recipe's delta is not declared yet, so producing a config would mean
            guessing the missing part.
    """
    if line not in LINES:
        raise KeyError(f"unknown recipe line {line!r}; known: {sorted(LINES)}")
    recipes = LINES[line]["recipes"]
    if version not in recipes:
        raise KeyError(f"unknown recipe {version!r} on {line}; known: {sorted(recipes)}")
    elements = recipes[version]["elements"]
    if elements is None:
        raise ValueError(
            f"recipe {version!r} on {line}: its delta is not declared yet (declared: {declared(line)}),"
            f" so the builder cannot produce it without guessing"
        )
    # the version travels as the *field* it is: the shared wiring resolves every structural
    # choice from it, and a subclass that only restated it is exactly what this replaces
    return apply_into(base_cfg(version, line=line, play=play), version, play=play, line=line, trace=trace)
