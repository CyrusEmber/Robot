# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""A0 layout migration (ARCH_PLAN 2.1a): the main line moves into ``versions/lizard/main/``.

One-shot migration, not a gate (underscore prefix, same as ``_migrate_lock_v3.py``). It
does the mechanical half only: the directory move and the parameter-file renames that the
``recipe_lines`` basename rule forces once the line directory is named ``main``. Everything
else A0 needs is printed as a checklist for the person holding the change, because those
edits land in files other work is touching.

Refusal is the point of the precondition check. The first attempt at this migration died
mid-flight for two reasons worth never repeating: ``git mv`` will not move a version
directory whose files are untracked (it reports "source directory is empty" and moves
nothing else), and moving a frozen tree out from under concurrent uncommitted work makes
two change sets fight over the same paths. Both are checked before anything is staged.

Usage:
    python rl_exp\\tools\\verify\\_a0_layout_migration.py            # plan only
    python rl_exp\\tools\\verify\\_a0_layout_migration.py --apply    # move
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
FAMILY = _REPO / "rl_exp" / "versions" / "lizard"
MAIN = FAMILY / "main"
_LINE = "lizard"
_TARGET_LINE = "lizard/main"
_VERSION_DIR = re.compile(r"^v[0-9]+$")

# paths whose uncommitted state would fight this migration (the batch's lock migration and
# the gates A0 has to edit afterwards). Moving frozen trees under them is how two change
# sets end up owning the same file.
CONTESTED = ("rl_exp/versions", "rl_exp/tasks", "rl_exp/tools/verify")

CHECKLIST = f"""follow-up edits A0 still needs (not done by this script):
  recipe_lines.py        drop the "main line is the family root" special case; key the
                         main line as {_TARGET_LINE!r}; is_main_line must become
                         name == "main" -- "/" not in key would now call every side line
                         a main line; relax the version-directory rule so a line's first
                         recipe need not be called v1
  check_dr_parity.py     version path lists and the asset-lock keys (regenerate with
                         --update-locks and review the diff field by field)
  check_version_docs.py  family-relative version keys ({_TARGET_LINE}/vN) + FAMILY/FILEMAP rows
  manifest.py            the asset-lock glob that guesses the directory from
                         params_version, and the hardcoded per-line lock path
  check_cfg_lock.py      baselines path and the --line handles
  versions/recipes.json  recipe "line" values: {_LINE!r} -> {_TARGET_LINE!r}
  versions/lines.json    line key: {_LINE!r} -> {_TARGET_LINE!r}
  docs                   FAMILY.md / FILEMAP.md / REWARDS.md / OBS.md / ACCEPTANCE.md /
                         README.md and the prose in each vN/PLAN.md mentioning
                         versions/{_LINE}/vN
  gate runs              [2] [12] [24] [28] [29] [31] all green again afterwards"""


def git(*args: str) -> str:
    """Run one git command in the repo.

    Args:
        args: the git arguments.

    Returns:
        Its stdout, stripped.
    """
    result = subprocess.run(["git", *args], cwd=_REPO, capture_output=True, text=True)
    return result.stdout.strip()


def tracked(path: pathlib.Path) -> bool:
    """Whether git knows any file under a directory (``git mv`` needs this).

    Args:
        path: the directory to ask about.

    Returns:
        True when at least one file below it is tracked.
    """
    return bool(git("ls-files", "--", str(path.relative_to(_REPO))))


def contested() -> list[str]:
    """Uncommitted changes that would fight this migration.

    Modified tracked files count everywhere under the contested paths. Untracked files only
    count under ``versions/`` -- a new gate next to this script is nobody's business, while
    an untracked version directory is exactly what made ``git mv`` refuse the first time.

    Returns:
        The ``git status --porcelain`` lines that matter.
    """
    self_path = pathlib.Path(__file__).resolve().relative_to(_REPO).as_posix()
    kept: list[str] = []
    for line in git("status", "--porcelain", "--", *CONTESTED).splitlines():
        if not line.strip():
            continue
        status, name = line[:2], line[3:].strip()
        if name == self_path:
            continue
        if "?" in status and not name.startswith("rl_exp/versions/"):
            continue
        kept.append(line)
    return kept


def plan() -> tuple[list[tuple[str, str]], list[str]]:
    """What would move, and why it cannot right now.

    Returns:
        ``(moves, refusals)``: ``(source, destination)`` pairs relative to the repo, and
        the reasons to stop instead.
    """
    moves: list[tuple[str, str]] = []
    refusals: list[str] = []
    if not FAMILY.is_dir():
        return moves, [f"{FAMILY} does not exist"]
    if MAIN.exists():
        refusals.append(f"{MAIN} already exists -- the migration either ran or started twice")

    versions = sorted(p.name for p in FAMILY.iterdir() if p.is_dir() and _VERSION_DIR.match(p.name))
    for name in versions + ["cfg_lock.json", f"{_LINE}_params.yaml"]:
        source = FAMILY / name
        if not source.exists():
            continue
        if not tracked(source):
            refusals.append(f"{source.relative_to(_REPO)} has no tracked files -- git mv would refuse it")
        moves.append((str(source.relative_to(_REPO)), str((MAIN / name).relative_to(_REPO))))

    # the basename rule: once the line directory is `main`, every parameter file is
    # main_params.yaml -- the dev file and one per frozen version
    for name in versions:
        source = MAIN / name / f"{_LINE}_params.yaml"
        if (FAMILY / name / f"{_LINE}_params.yaml").exists():
            moves.append((str(source.relative_to(_REPO)), str((MAIN / name / "main_params.yaml").relative_to(_REPO))))

    if contested():
        refusals.append("the tree carries uncommitted work under the contested paths (see below)")
    return moves, refusals


def main(argv: list[str] | None = None) -> int:
    """Print the plan, refuse on dirty preconditions, and move only with --apply.

    Args:
        argv: command line, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="run the moves (default: plan only)")
    args = parser.parse_args(argv)

    moves, refusals = plan()
    print(f"  moves planned: {len(moves)}")
    for source, destination in moves:
        print(f"    {source}  ->  {destination}")

    dirty = contested()
    if dirty:
        print("  uncommitted work under contested paths:")
        for line in dirty:
            print(f"    {line}")

    if refusals:
        for reason in refusals:
            print(f"  REFUSE {reason}")
        print("  nothing was moved")
        return 1

    if not args.apply:
        print(f"\n{CHECKLIST}")
        print("\n  plan only (pass --apply to move)")
        return 0

    MAIN.mkdir(parents=True, exist_ok=True)
    for source, destination in moves:
        result = subprocess.run(["git", "mv", source, destination], cwd=_REPO, capture_output=True, text=True)
        if result.returncode:
            print(f"  FAIL git mv {source} {destination}: {result.stderr.strip()}")
            return 1
    print(f"  moved {len(moves)} paths\n{CHECKLIST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
