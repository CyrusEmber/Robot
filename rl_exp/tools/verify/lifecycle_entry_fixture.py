# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Build a fixture recipe directory for the entry-side cases (ARCH_PLAN 2.3, L02/L03/L05/L06).

The entry-side cases need a *retired* line driven through a *real* trainer process, and 2.1a
forbids retiring a real line to make a test pass. So the fixture is a copy of this checkout's
two index halves with one line flipped, read through ``RL_RECIPE_DIR`` (see
``rl_exp.tools.runrecord.lifecycle``): the verdict still comes from a directory, and T0 records
which one answered.

Nothing here is in the offline suite -- reaching the refusal means starting the trainer, which
means the sim app (OFFLINE_CHECKS.md 5). This tool only writes the fixture and prints the
command; the run itself is the C4 window's job.

    python rl_exp\\tools\\verify\\lifecycle_entry_fixture.py --out %TEMP%\\lz_fixture --retire lizard/main
    python rl_exp\\tools\\verify\\lifecycle_entry_fixture.py --out %TEMP%\\lz_fixture2 \\
        --announce lizard/baseline --notice-until 2026-10-15 --today 2026-10-20
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
LINES = _REPO / "rl_exp" / "versions" / "lines.json"
RECIPES = _REPO / "rl_exp" / "versions" / "recipes.json"


def _loads(path: pathlib.Path) -> dict:
    """Read one index half, or stop -- a fixture built from a missing index proves nothing."""
    if not path.is_file():
        raise SystemExit(f"[fixture] {path} is missing: nothing to copy")
    return json.loads(path.read_text(encoding="utf-8"))


def build(
    out: pathlib.Path,
    *,
    retire: str | None,
    announce: str | None,
    notice_until: str | None,
    today: _dt.date | None,
    successor: str | None,
) -> dict:
    """Write the fixture and describe what it should make the trainer do.

    Args:
        out: repository root of the fixture (``out/rl_exp/versions`` gets the two indexes).
        retire: line to retire, or None.
        announce: line to give a retirement announcement, or None.
        notice_until: the announcement's ``retire_not_before`` date.
        today: the date the announcement is judged against (written into the note, not the index:
            the index holds the condition, the runtime compares it to today).
        successor: the active line the retired one points at.

    Returns:
        ``{"out", "retired", "announced", "expected", "command"}`` -- what was written and what
        the run should therefore do.
    """
    lines = _loads(LINES)
    recipes = _loads(RECIPES)
    entries = lines.get("lines") or {}
    if (retire or announce) not in entries:
        raise SystemExit(f"[fixture] {(retire or announce)!r} is not a line in this checkout: {sorted(entries)}")
    if retire and announce:
        raise SystemExit("[fixture] one line per fixture: a retired line is not a warned active line")

    active = [key for key, entry in entries.items() if entry.get("status") == "active"]
    target = retire or announce
    if retire:
        if not active:
            raise SystemExit("[fixture] no active line is left to name as the successor")
        entries[retire].update(
            {
                "status": "retired",
                "successor": successor or active[0],
                "retired_at": (today or _dt.date.today()).isoformat(),
                "reason": "fixture: the entry-side refusal needs a retired line (2.1a forbids a real one)",
                "deprecation": None,
            }
        )
        expected = "refuse the launch before anything is built, naming the successor"
    else:
        entries[announce].update(
            {
                "deprecation": {
                    "notice": f"fixture: new work belongs on {active[0] if active else 'the successor line'}",
                    "declared_at": _dt.date.today().isoformat(),
                    "retire_not_before": {"kind": "date", "not_before": notice_until or "2099-01-01"},
                }
            }
        )
        due = notice_until is not None and (today or _dt.date.today()) >= _dt.date.fromisoformat(notice_until)
        expected = (
            "proceed, and record the overdue announcement (warn only)"
            if due
            else "proceed, and record the announcement without a warning"
        )
    lines["revision"] = int(lines.get("revision") or 1) + 1

    versions = out / "rl_exp" / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (versions / "lines.json").write_text(json.dumps(lines, indent=1) + "\n", encoding="utf-8")
    (versions / "recipes.json").write_text(
        json.dumps(recipes, indent=1) + "\n", encoding="utf-8"
    )
    (out / "FIXTURE.md").write_text(
        "# Lifecycle fixture (ARCH_PLAN 2.3 entry side)\n\n"
        f"Written by `rl_exp/tools/verify/lifecycle_entry_fixture.py` on {_dt.date.today().isoformat()}.\n"
        f"Line under test: `{target}` (fixture revision {lines['revision']}).\n\n"
        f"Expected: {expected}.\n\n"
        "Run it with the real trainer and the fixture directory:\n\n"
        "```\n"
        f'set RL_RECIPE_DIR={out}\n'
        "python scripts\\reinforcement_learning\\rsl_rl\\train.py --task <task> --headless --num_envs 64 --max_iterations 1\n"
        "```\n\n"
        "A retire fixture must print the refusal and exit before the environment is built; an\n"
        "announce fixture must run, with the warning in the log and the verdict in T0.\n",
        encoding="utf-8",
    )
    return {
        "out": str(out),
        "retired": retire,
        "announced": announce,
        "expected": expected,
        "command": f'set RL_RECIPE_DIR={out} && <python> scripts\\reinforcement_learning\\rsl_rl\\train.py '
        f"--task <task> --headless --num_envs 64 --max_iterations 1",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=pathlib.Path, help="fixture repository root to write")
    parser.add_argument("--retire", default=None, help="line to retire (refusal case)")
    parser.add_argument("--announce", default=None, help="line to announce a retirement for (warning case)")
    parser.add_argument("--notice-until", default=None, help="the announcement's retire_not_before date")
    parser.add_argument("--today", default=None, help="date to judge the announcement against")
    parser.add_argument("--successor", default=None, help="the active line the retired one points at")
    args = parser.parse_args(argv)

    if not args.retire and not args.announce:
        parser.error("one of --retire / --announce is required: a fixture with no change tests nothing")
    described = build(
        args.out,
        retire=args.retire,
        announce=args.announce,
        notice_until=args.notice_until,
        today=_dt.date.fromisoformat(args.today) if args.today else None,
        successor=args.successor,
    )
    print(json.dumps(described, indent=1))
    print("LIFECYCLE_FIXTURE_WRITTEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
