# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Startup lifecycle check: may this launch proceed on this recipe line (ARCH_PLAN 2.2 / C1)?

Three callers must not answer that question differently, and two of them already exist: the
old trainer, and the tuning entry (``ablation_harness``), which shells out to that same
trainer. So wiring the trainer covers both, and this module is the *single* place where the
directory is turned into a verdict -- the decision table itself is not repeated here, it is
:mod:`rl_exp.tools.verify.recipe_lifecycle`, whose cases are the contract.

What this module owns:

* **Identity from the directory**, not from the task id: ``versions/recipes.json`` says which
  recipe a task id means, ``versions/lines.json`` says whether that line is active. A number in
  a task id never grants permission.
* **Read once** -- the index is read at startup and never again, so a directory edited while a
  run is in flight cannot change what that run was launched under (2.2). The revision and the
  content digests are captured with the verdict, which is what T0 records.
* **The source checkpoint of a resume**, resolved here and not left to the trainer's own later
  call: that call happens after this run's log directory exists, so with the default
  ``load_run`` (``.*``) the newest directory is this run's own empty one and the resolution
  would come back empty. Resolving before the directory is created answers what the run is
  actually continuing from.

Unknown is never permission (hard constraint 1): an unreadable index, a task missing from the
map, a line missing from the lifecycle index, or a source that does not resolve all end in a
refusal, never in a default of ``active``.
"""

from __future__ import annotations

import datetime
import os
import pathlib

from rl_exp.tools.runrecord import provenance as prov
from rl_exp.tools.verify import cfg_snapshot as cs
from rl_exp.tools.verify import check_recipe_map, check_recipe_registry, recipe_lifecycle

_REPO = pathlib.Path(__file__).resolve().parents[3]
LINES_PATH = _REPO / "rl_exp" / "versions" / "lines.json"
RECIPES_PATH = _REPO / "rl_exp" / "versions" / "recipes.json"

INDEX_DIR_ENV = "RL_RECIPE_DIR"
"""Where the recipe directory is read from, overriding this checkout's ``rl_exp/versions``.

A machine/testing hook, like ``RL_ISAAC_ROOT``: retiring a real line to test the retired path is
forbidden by 2.1a, so the entry-side cases (L02/L03) point the read at a tree that *is* retired.
It moves where the directory is read from and nothing else -- the verdict still comes from
whatever directory that is, and the digest recorded in T0 says which one answered.
"""


def index_root() -> pathlib.Path:
    """The repository root whose ``rl_exp/versions`` holds the directory this run reads.

    Returns:
        The repository root named by :data:`INDEX_DIR_ENV` (a fixture tree whose own
        ``rl_exp/versions`` carries the lines under test), or this checkout.
    """
    override = os.environ.get(INDEX_DIR_ENV, "").strip()
    return pathlib.Path(override) if override else _REPO


def read_index(root: pathlib.Path | None = None) -> dict:
    """Read both halves of the recipe directory, once, with what identifies that reading.

    Args:
        root: repository root to read from, defaulting to this checkout (tests pass a
            synthetic tree).

    Returns:
        ``{"lines", "recipes", "revision", "digests"}`` where the two parsed documents are
        returned as their loaders give them (including their missing/unreadable stand-ins) and
        ``digests`` maps each file to its SHA-256 -- the record needs to name *which* revision
        of the directory granted the permission, not just its number.
    """
    root = pathlib.Path(root) if root is not None else index_root()
    lines_path = root / "rl_exp" / "versions" / "lines.json"
    recipes_path = root / "rl_exp" / "versions" / "recipes.json"
    lines = check_recipe_registry.load(lines_path)
    return {
        "lines": lines,
        "recipes": check_recipe_map.load(recipes_path),
        "revision": lines.get("revision"),
        "digests": {"lines": prov.sha256_file(lines_path), "recipes": prov.sha256_file(recipes_path)},
    }


def identity(task: str | None, index: dict) -> dict:
    """Resolve ``task id -> recipe key -> line -> status``, or list what stopped it.

    Every step is checked here rather than defaulted: a task that is not in the map is not
    "probably main", and a line with no lifecycle entry is not "probably active".

    Args:
        task: the gym task id being launched.
        index: the parsed directory from :func:`read_index`.

    Returns:
        ``{"task", "recipe", "line", "status", "problems"}``: the resolved identity and, when
        resolution failed, the reasons (a non-empty ``problems`` must refuse the launch).
    """
    recipes = index.get("recipes") or {}
    lines = index.get("lines") or {}
    problems: list[str] = []
    for document, parsed in (("recipes.json", recipes), ("lines.json", lines)):
        for key in ("_missing", "_unreadable"):
            if parsed.get(key):
                problems.append(f"{document} is not usable: {parsed[key]}")

    key = (recipes.get("tasks") or {}).get(task)
    entry = (recipes.get("recipes") or {}).get(key) if key else None
    line = (entry or {}).get("line")
    status = ((lines.get("lines") or {}).get(line) or {}).get("status") if line else None
    if not key:
        problems.append(
            f"task {task!r} is not in the recipe map: a recipe is registered before it is launched,"
            " and a missing identity is not a default"
        )
    elif not entry:
        problems.append(f"task {task!r} maps to recipe {key!r}, which the map does not describe")
    elif line not in (lines.get("lines") or {}):
        problems.append(
            f"line {line!r} has no lifecycle entry; a missing lifecycle must not read as active"
        )
    return {"task": task, "recipe": key, "line": line, "status": status, "problems": problems}


def retirement_due(entry: dict | None, revision, today: datetime.date | None = None) -> bool:
    """Whether the line's announced retirement condition already holds.

    Only the offline gate acts on this: a condition that is met while the directory still says
    ``active`` is a warning the run records, and the permission still comes from ``status``
    (2.1a). The condition is evaluated with the offline gate's own function, so the two cannot
    drift into different readings of the same announcement.

    Args:
        entry: the line's lifecycle entry, if any.
        revision: the directory revision the condition may be expressed against.
        today: the date to evaluate a ``date`` condition against.

    Returns:
        True only when the condition holds under a machine-decidable reading.
    """
    condition = ((entry or {}).get("deprecation") or {}).get("retire_not_before")
    if not condition:
        return False
    satisfied = check_recipe_registry.condition_satisfied(
        condition,
        revision=revision if isinstance(revision, int) else -1,
        today=today or datetime.date.today(),
    )
    return bool(satisfied)


def flag_in(argv: list[str] | None, name: str) -> bool:
    """Whether a bare command-line flag was passed.

    Args:
        argv: the command line.
        name: the flag, with its leading dashes.

    Returns:
        True when the flag appears as ``name`` or ``name=...``.
    """
    return any(token == name or token.startswith(f"{name}=") for token in (argv or []))


def source_checkpoint(log_root, load_run: str | None, load_checkpoint: str | None) -> str | None:
    """The checkpoint a resume would load, or None when none resolves.

    Delegated to the framework's own resolver instead of a second glob here: a private copy of
    "which run and which file" would be a second answer to a question that already has one, and
    the two would drift. A resume is a *requested* checkpoint; this is the resolved one, which
    is the only thing that may exempt a retired line.

    Args:
        log_root: the experiment's log directory (the parent of this run's directory).
        load_run: the run selector, as the agent config carries it.
        load_checkpoint: the checkpoint selector, as the agent config carries it.

    Returns:
        The resolved checkpoint path, or None (unresolvable, or no framework to ask).
    """
    try:
        from isaaclab_tasks.utils import get_checkpoint_path
    except Exception:  # noqa: BLE001 - no framework to ask: unknown, so nothing may be exempted
        return None
    try:
        return get_checkpoint_path(str(log_root), load_run or ".*", load_checkpoint or "model_.*.pt")
    except Exception:  # noqa: BLE001 - "no run/checkpoint matched" is a refusal, not a crash
        return None


def startup_check(
    *,
    task: str | None,
    argv: list[str] | None,
    agent_cfg,
    log_dir,
    root: pathlib.Path | None = None,
    today: datetime.date | None = None,
    declared_line: str | None = None,
) -> tuple[recipe_lifecycle.Verdict, dict]:
    """Decide whether this launch may proceed, and produce what T0 records about it.

    Args:
        task: the gym task id being launched.
        argv: the command line (the two flags are read from it, so the fork patch needs no
            extra call site).
        agent_cfg: the resolved agent config (whether this is a resume, and from where).
        log_dir: this run's directory; its parent is where a resume resolves from.
        root: repository root to read, defaulting to this checkout.
        today: the date for a ``date``-condition announcement (tests inject it).
        declared_line: the line the *config class* declares (``params_line``). Two answers to
            "which line is this" that disagree is a refusal: the map and the code cannot both
            be describing this launch.

    Returns:
        ``(verdict, evidence)``. The evidence is what goes into the record verbatim, refused
        verdicts included -- a refusal that leaves no trace is indistinguishable from a run
        that never started.
    """
    index = read_index(root)
    identity_ = identity(task, index)
    is_resume = bool(getattr(agent_cfg, "resume", False))
    operation = "resume" if is_resume else "new_train"
    allow_retired_resume = flag_in(argv, "--allow_retired_resume")
    drop_curriculum_state = flag_in(argv, "--drop_curriculum_state") or flag_in(argv, "--weights_only")
    source = None
    if is_resume:
        try:
            source = source_checkpoint(
                pathlib.Path(log_dir).parent,
                getattr(agent_cfg, "load_run", None),
                getattr(agent_cfg, "load_checkpoint", None),
            )
        except Exception:  # noqa: BLE001 - a resolver that raises resolved nothing, so: unknown
            source = None
    line_entry = ((index.get("lines") or {}).get("lines") or {}).get(identity_["line"]) or {}
    due = retirement_due(line_entry, index.get("revision"), today)
    verdict = recipe_lifecycle.judge(
        operation,
        identity_["status"],
        allow_retired_resume=allow_retired_resume,
        has_source_checkpoint=bool(source),
        drop_curriculum_state=drop_curriculum_state,
        retirement_due=due,
    )
    disagreements = list(identity_["problems"])
    if declared_line and identity_["line"] and declared_line != identity_["line"]:
        disagreements.append(
            f"identity disagreement: the config class declares params_line={declared_line!r} while"
            f" the map names line {identity_['line']!r} for task {task!r}"
        )
    if disagreements:
        verdict = recipe_lifecycle.Verdict(False, "; ".join(disagreements), verdict.warn)
    evidence = {
        "operation": operation,
        "task": task,
        "recipe": identity_["recipe"],
        "line": identity_["line"],
        "status": identity_["status"],
        "declared_params_line": declared_line,
        "directory_revision": index.get("revision"),
        "directory_sha256": index.get("digests"),
        "allow_retired_resume": allow_retired_resume,
        "drop_curriculum_state": drop_curriculum_state,
        "source_checkpoint": cs.relativize(source) if source else None,
        "retirement_due": due,
        "allowed": verdict.allowed,
        "reason": verdict.reason,
        "warn": verdict.warn,
    }
    return verdict, evidence
