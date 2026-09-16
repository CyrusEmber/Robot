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

Refusal is the point of the precondition check, but it is an intersection test, not "the
tree is clean": A0 stops only when uncommitted work overlaps the paths it moves or the files
it has to edit -- refusing on an unrelated dirty file is how a migration gets stuck behind
work it does not touch. The first attempt died mid-flight for two reasons worth never
repeating: ``git mv`` will not move a directory whose files are untracked (it reports
"source directory is empty" and then moves nothing at all), and moving a frozen tree out
from under concurrent work makes two change sets own the same paths.

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
PARAMS_SUFFIX = "_params.yaml"  # mirrors recipe_lines: a parameter file names its own line

# The files A0 has to write after the moves (its own checklist below). The precondition is an
# intersection against this set plus the paths that move -- an unrelated dirty file is not
# A0's business, and refusing on one is how a migration ends up stuck behind work it does not
# touch. The one thing never negotiable: a *moved* directory whose files are untracked,
# because git mv refuses the whole batch on those.
WRITE_SET = (
    "rl_exp/versions/recipes.json",
    "rl_exp/versions/lines.json",
    "FILEMAP.md",
    "README.md",
    "rl_exp/tools/verify/recipe_lines.py",
    "rl_exp/tools/verify/check_dr_parity.py",
    "rl_exp/tools/verify/check_version_docs.py",
    "rl_exp/tools/verify/check_cfg_lock.py",
    "rl_exp/tools/runrecord/manifest.py",
    "rl_exp/versions/lizard/FAMILY.md",
    "rl_exp/versions/lizard/PLAN.md",
    "rl_exp/versions/lizard/REWARDS.md",
    "rl_exp/versions/lizard/OBS.md",
    "rl_exp/versions/lizard/ACCEPTANCE.md",
)

CHECKLIST = f"""follow-up edits A0 still needs (not done by this script):
  recipe_lines.py        drop the "main line is the family root" special case; key the
                         main line as {_TARGET_LINE!r} (done, with the family directory
                         no longer a line at all); is_main_line must become
                         name == "main" -- "/" not in key would now call every side line
                         a main line (done); the version-directory rule still says v<N>,
                         and relaxing it is only needed when a line's first recipe is not
                         called v1 -- baseline chose v1, so nothing to do today
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


def dirty_lines() -> list[str]:
    """Every uncommitted path in the repo, as ``git status --porcelain`` lines."""
    return [line for line in git("status", "--porcelain").splitlines() if line.strip()]


def owned(path: str, moves: list[tuple[str, str]]) -> str | None:
    """Why A0 owns a dirty path, or None when it is none of A0's business.

    Args:
        path: repo-relative path of the dirty entry.
        moves: the ``(source, destination)`` pairs this run would perform.

    Returns:
        A reason string when A0 must not run on top of this change, else None.
    """
    if path in WRITE_SET:
        return "A0 edits this file"
    for source, _destination in moves:
        if path == source or path.startswith(f"{source}/"):
            return "A0 moves this path"
    return None


def contested(moves: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """Split the dirty tree into what A0 owns and what it can ignore.

    Args:
        moves: the ``(source, destination)`` pairs this run would perform.

    Returns:
        ``(owned, ignored)`` porcelain lines. The ignored ones are printed too: a narrower
        precondition is a decision that should be visible, not a silent loosening.
    """
    owned_lines: list[str] = []
    ignored: list[str] = []
    for line in dirty_lines():
        path = line[3:].strip().strip('"')
        (owned_lines if owned(path, moves) else ignored).append(line)
    return owned_lines, ignored


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
    params = f"{MAIN.name}{PARAMS_SUFFIX}"  # the basename rule: a file names its own line
    for name in [*versions, "cfg_lock.json"]:
        source = FAMILY / name
        if not source.exists():
            continue
        if not tracked(source):
            refusals.append(f"{source.relative_to(_REPO)} has no tracked files -- git mv would refuse it")
        moves.append((str(source.relative_to(_REPO)), str((MAIN / name).relative_to(_REPO))))

    # the line's own parameters: moved *and* renamed. The first attempt renamed only the
    # frozen copies and left main/lizard_params.yaml behind, which discovery then refused
    # -- the rule is that a path names its line.
    dev = FAMILY / f"{_LINE}{PARAMS_SUFFIX}"
    if dev.exists():
        if not tracked(dev):
            refusals.append(f"{dev.relative_to(_REPO)} has no tracked files -- git mv would refuse it")
        moves.append((str(dev.relative_to(_REPO)), str((MAIN / params).relative_to(_REPO))))

    # one per frozen version
    for name in versions:
        source = MAIN / name / f"{_LINE}{PARAMS_SUFFIX}"
        if (FAMILY / name / f"{_LINE}{PARAMS_SUFFIX}").exists():
            moves.append((str(source.relative_to(_REPO)), str((MAIN / name / params).relative_to(_REPO))))

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

    owned_lines, ignored = contested(moves)
    if ignored:
        print(f"  uncommitted files A0 does not touch: {len(ignored)} (ignored on purpose)")
    if owned_lines:
        print("  uncommitted work A0 needs settled first -- it moves or edits these:")
        for line in owned_lines:
            print(f"    {line}")
        refusals.append(f"{len(owned_lines)} dirty path(s) intersect A0's own write set")

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
