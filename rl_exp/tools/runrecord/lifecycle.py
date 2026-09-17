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
  run is in flight cannot change what that run was launched under (2.2). The content digests of
  both files are captured with the verdict, which is what T0 records.
* **The launch arguments that only mean something with a resume**: ``--drop_curriculum_state``
  (and its deprecated ``--weights_only`` alias) discards the checkpoint's curriculum state, so
  without a resume there is nothing to discard. It is refused here, where the trainer's own CLI
  arrives, so both entries refuse it before a trainer starts.

Unknown is never permission (hard constraint 1): an unreadable index, a task missing from the
map or a line missing from the lifecycle index all end in a refusal, never in a default of
``active``.
"""

from __future__ import annotations

import pathlib

from rl_exp.tools.runrecord import provenance as prov
from rl_exp.tools.verify import check_recipe_map, check_recipe_registry, recipe_lifecycle

_REPO = pathlib.Path(__file__).resolve().parents[3]
LINES_PATH = _REPO / "rl_exp" / "versions" / "lines.json"
RECIPES_PATH = _REPO / "rl_exp" / "versions" / "recipes.json"


def read_index(root: pathlib.Path | None = None) -> dict:
    """Read both halves of the recipe directory, once, with what identifies that reading.

    Args:
        root: repository root to read from, defaulting to this checkout (tests pass a
            synthetic tree).

    Returns:
        ``{"lines", "recipes", "digests"}`` where the two parsed documents are returned as their
        loaders give them (including their missing/unreadable stand-ins) and ``digests`` maps each
        file to its SHA-256 -- the record names *which* directory granted the permission by
        content, which is the only identity that cannot go stale unnoticed.
    """
    root = pathlib.Path(root) if root is not None else _REPO
    lines_path = root / "rl_exp" / "versions" / "lines.json"
    recipes_path = root / "rl_exp" / "versions" / "recipes.json"
    lines = check_recipe_registry.load(lines_path)
    return {
        "lines": lines,
        "recipes": check_recipe_map.load(recipes_path),
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


def flag_in(argv: list[str] | None, name: str) -> bool:
    """Whether a bare command-line flag was passed.

    Args:
        argv: the command line.
        name: the flag, with its leading dashes.

    Returns:
        True when the flag appears as ``name`` or ``name=...``.
    """
    return any(token == name or token.startswith(f"{name}=") for token in (argv or []))


def curriculum_flag_problems(argv: list[str] | None, *, is_resume: bool) -> tuple[str, ...]:
    """Why the curriculum-state flag is unusable on this command line, if it is.

    The flag drops the curriculum state a resume restores, so without a resume there is nothing
    to drop and the caller has mistaken it for a general switch. Both spellings are read: the
    deprecated ``--weights_only`` alias is the same switch and must be refused the same way
    while it still exists.

    Args:
        argv: the command line.
        is_resume: whether this launch is a resume.

    Returns:
        One reason when the flag was passed without a resume, otherwise nothing.
    """
    passed = flag_in(argv, "--drop_curriculum_state") or flag_in(argv, "--weights_only")
    if not passed or is_resume:
        return ()
    return ("--drop_curriculum_state without a resume is a cold start; begin a new run",)


def startup_check(
    *,
    task: str | None,
    argv: list[str] | None,
    agent_cfg,
    root: pathlib.Path | None = None,
    declared_line: str | None = None,
) -> tuple[recipe_lifecycle.Verdict, dict]:
    """Decide whether this launch may proceed, and produce what T0 records about it.

    Args:
        task: the gym task id being launched.
        argv: the command line (the curriculum flag is read from it, so the fork patch needs no
            extra call site).
        agent_cfg: the resolved agent config (whether this is a resume).
        root: repository root to read, defaulting to this checkout.
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
    drop_curriculum_state = flag_in(argv, "--drop_curriculum_state") or flag_in(argv, "--weights_only")
    verdict = recipe_lifecycle.judge(operation, identity_["status"])
    problems = list(identity_["problems"])
    problems.extend(curriculum_flag_problems(argv, is_resume=is_resume))
    if declared_line and identity_["line"] and declared_line != identity_["line"]:
        problems.append(
            f"identity disagreement: the config class declares params_line={declared_line!r} while"
            f" the map names line {identity_['line']!r} for task {task!r}"
        )
    if problems:
        verdict = recipe_lifecycle.Verdict(False, "; ".join(problems))
    evidence = {
        "operation": operation,
        "task": task,
        "recipe": identity_["recipe"],
        "line": identity_["line"],
        "status": identity_["status"],
        "declared_params_line": declared_line,
        "directory_sha256": index.get("digests"),
        "drop_curriculum_state": drop_curriculum_state,
        "allowed": verdict.allowed,
        "reason": verdict.reason,
    }
    return verdict, evidence
