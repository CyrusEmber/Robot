# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""A0's path half: every hardcoded main-line path, in one auditable pass.

A0 moved the main line into ``versions/lizard/main/`` and renamed its parameters to
``main_params.yaml``. Everything that spelled the old path has to move with it, and the
list is longer than the move itself: three gates read a frozen yaml directly, two pipeline
tools read the dev yaml, the family history and the file map carry one row per version.

Two deliberate exclusions:

* frozen records (``vN/PLAN.md``, ``vN/NOTES.md``) keep the paths they were written with.
  They describe the tree as it was when the recipe was frozen, and a record that gets
  quietly rewritten to match today's layout stops being evidence of anything.
* ``ACCEPTANCE.md``'s earlier sections are records too; only the A0 section speaks about
  the new layout, and it is written by hand.

One-shot tool, not a gate (underscore prefix, like ``_migrate_lock_v3.py``).

Usage:
    python rl_exp\\tools\\verify\\_a0_paths.py            # report only
    python rl_exp\\tools\\verify\\_a0_paths.py --apply    # rewrite
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]

# code: the frozen-yaml readers spell the path out, so the replacement keeps their shape
CODE = (
    "rl_exp/tools/verify/check_obs_layout.py",
    "rl_exp/tools/verify/check_reward_v13.py",
    "rl_exp/tools/verify/check_terminations_v14.py",
    "rl_exp/tools/verify/teacher_smoke_runner.py",
    "rl_exp/tools/pipeline/convert_urdf.py",
    "rl_exp/tools/pipeline/export_ue.py",
)

# living documents: indexes and prose that describe today's tree
DOCS = (
    "rl_exp/versions/lizard/FAMILY.md",
    "rl_exp/versions/lizard/PLAN.md",
    "rl_exp/versions/lizard/REWARDS.md",
    "rl_exp/versions/lizard/OBS.md",
    "FILEMAP.md",
    "README.md",
)

FAMILY = "rl_exp/versions/lizard/FAMILY.md"

# quoted path fragments in python source
RULE_CODE = (
    (re.compile(r'"lizard" / "v(\d+)" / "lizard_params\.yaml"'), r'"lizard" / "main" / "v\1" / "main_params.yaml"'),
    (re.compile(r'"lizard" / "lizard_params\.yaml"'), r'"lizard" / "main" / "main_params.yaml"'),
)

# prose paths, both separators, main line only (parkour/baseline keep their own spelling).
# The short forms matter: the file map's version rows are `lizard\v14\`, not full paths.
RULES_DOCS = (
    (re.compile(r"versions/lizard/v"), "versions/lizard/main/v"),
    (re.compile(r"versions\\lizard\\v"), r"versions\\lizard\\main\\v"),
    (re.compile(r"versions/lizard/lizard_params\.yaml"), "versions/lizard/main/main_params.yaml"),
    (re.compile(r"lizard/v(?=\d)"), "lizard/main/v"),
    (re.compile(r"lizard\\v(?=\d)"), r"lizard\\main\\v"),
)

# the family history's first column is the line-relative key
RULE_FAMILY = (re.compile(r"^\| v(\d+) \|", re.MULTILINE), r"| main/v\1 |")


def rewrite(text: str, rules) -> tuple[str, list[str]]:
    """Apply every rule once, reporting which ones matched.

    Args:
        text: file contents.
        rules: ``(pattern, replacement)`` pairs.

    Returns:
        The rewritten text and the patterns that changed something.
    """
    hits: list[str] = []
    for pattern, replacement in rules:
        new_text, count = pattern.subn(replacement, text)
        if count:
            hits.append(f"{pattern.pattern} x{count}")
        text = new_text
    return text, hits


def main(argv: list[str] | None = None) -> int:
    """Report or apply the path updates.

    Args:
        argv: command line, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the files (default: report only)")
    args = parser.parse_args(argv)

    targets = [(name, RULE_CODE) for name in CODE]
    targets.append((FAMILY, RULES_DOCS + (RULE_FAMILY,)))
    targets += [(name, RULES_DOCS) for name in DOCS if name != FAMILY]
    total = 0
    for name, rules in targets:
        path = _REPO / name
        if not path.is_file():
            print(f"  MISSING {name}")
            continue
        text = path.read_text(encoding="utf-8")
        updated, hits = rewrite(text, rules)
        total += len(hits)
        print(f"  {name}: {len(hits)} rule(s) -> {hits}")
        if args.apply and updated != text:
            path.write_text(updated, encoding="utf-8")
    print(f"  {'applied' if args.apply else 'report only'}: {total} rule hit(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
