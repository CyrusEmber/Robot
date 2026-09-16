# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Negative control for ``check_recipe_registry``: every refusal must actually fire.

A lifecycle gate that only ever prints "OK" is indistinguishable from no gate. Each case
below is one rule of ARCH_PLAN 2.1/L06 driving a synthetic tree through ``validate`` --
the tree is built on the fly so a case can be "an announced retirement that already came
due" without waiting for a date or editing the real index.

Two properties get their own cases because they are the ones a reviewer cannot see by
reading the happy path:

* the ``retire_not_before`` condition is machine-decidable and clock-free when it is a
  revision condition -- same registry, two different "today" values, same verdict;
* the notice period does not change permissions: ``active`` + announced + not yet due is
  clean, which is what "the announcement must not block" means in practice.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from check_recipe_registry import condition_satisfied, validate  # noqa: E402
from recipe_lines import discover  # noqa: E402

NOTICE_DAY = _dt.date(2026, 9, 16)
DUE_DAY = _dt.date(2026, 10, 15)
FREEZE = "2026-10-15"
MAIN = "lizard/main"
SIDE = "lizard/parkour"


def _tree(tmp: pathlib.Path) -> dict:
    """A synthetic versions tree with a main line and a side line."""
    root = tmp / "versions"
    for line, name, versions in (
        (root / "lizard" / "main", "main", ["v0"]),
        (root / "lizard" / "parkour", "parkour", ["v1"]),
    ):
        line.mkdir(parents=True, exist_ok=True)
        (line / f"{name}_params.yaml").write_text("", encoding="utf-8")
        for version in versions:
            (line / version).mkdir()
            (line / version / f"{name}_params.yaml").write_text("", encoding="utf-8")
    return discover(root)


def _entry(**over) -> dict:
    entry = {"status": "active", "successor": None, "retired_at": None, "reason": None, "deprecation": None}
    entry.update(over)
    return entry


def _dep(**over) -> dict:
    block = {"notice": "new work goes to the successor line", "declared_at": "2026-09-16",
             "retire_not_before": {"kind": "date", "not_before": FREEZE}}
    block.update(over)
    return block


def _registry(main=None, side=None, revision: int = 1, fmt: int = 1) -> dict:
    return {
        "format": fmt,
        "revision": revision,
        "lines": {MAIN: main or _entry(), SIDE: side or _entry()},
    }


def _retired(**over) -> dict:
    return _entry(status="retired", retired_at="2026-09-16", reason="superseded by the new line", **over)


CASES: list[tuple[str, dict, _dt.date, str | None]] = [
    # -- identity (L01): which line is which, and nothing is guessed ------------------
    ("line discovered but never registered", {"format": 1, "revision": 1, "lines": {}}, NOTICE_DAY,
     "has no lifecycle entry"),
    ("dangling line", {"format": 1, "revision": 1, "lines": {MAIN: _entry(), "lizard/ghost": _entry()}},
     NOTICE_DAY, "names no recipe line"),
    ("entry carries a run-scoped field", _registry(main=_entry(run_id="abc")), NOTICE_DAY, "unknown fields"),
    ("entry omits a field instead of stating null", _registry(main={"status": "active"}), NOTICE_DAY,
     "entry is missing"),
    ("third status invented", _registry(main=_entry(status="deprecated")), NOTICE_DAY, "lifecycle is binary"),
    # -- retirement evidence stays consistent (L05) ----------------------------------
    ("retired without a date or a reason", _registry(main=_entry(status="retired")), NOTICE_DAY,
     "needs retired_at"),
    ("active line keeps retirement evidence", _registry(main=_entry(retired_at="2026-09-01")), NOTICE_DAY,
     "retirement evidence left behind"),
    ("successor does not exist", _registry(main=_retired(successor="lizard/nowhere")), NOTICE_DAY,
     "is not a registered line"),
    ("successor points at itself", _registry(main=_retired(successor=MAIN)), NOTICE_DAY, "points at itself"),
    ("successor is itself retired", _registry(main=_retired(successor=SIDE),
                                              side=_retired()), NOTICE_DAY, f"{SIDE!r} is not active"),
    # -- the announcement must be decidable (L06) ------------------------------------
    ("deprecation block incomplete", _registry(main=_entry(deprecation={"notice": "x"})), NOTICE_DAY,
     "deprecation is missing"),
    ("empty migration notice", _registry(main=_entry(deprecation=_dep(notice="   "))), NOTICE_DAY,
     "non-empty string"),
    ("condition is free text", _registry(main=_entry(deprecation=_dep(retire_not_before="when ready"))),
     NOTICE_DAY, "is not one of"),
    ("date condition is not a date",
     _registry(main=_entry(deprecation=_dep(retire_not_before={"kind": "date", "not_before": "soon"}))),
     NOTICE_DAY, "not machine-decidable"),
    ("revision condition takes a non-positive integer",
     _registry(main=_entry(deprecation=_dep(retire_not_before={"kind": "registry_revision", "at_least": 0}))),
     NOTICE_DAY, "not machine-decidable"),
    ("announced after its own due date",
     _registry(main=_entry(deprecation=_dep(declared_at="2026-11-01"))), NOTICE_DAY, "left no notice period"),
    # -- the two lifecycle/condition mismatches (L06) --------------------------------
    ("retired before its own condition holds", _registry(main=_retired(deprecation=_dep())), NOTICE_DAY,
     "retired before its own"),
    ("condition passed but the line is still active", _registry(main=_entry(deprecation=_dep())), DUE_DAY,
     "still active"),
    # -- format ----------------------------------------------------------------------
    ("registry format changed without this gate", _registry(fmt=2), NOTICE_DAY, "format"),
    ("revision is not a positive integer", _registry(revision=0), NOTICE_DAY, "positive integer"),
    # -- the clean shapes ------------------------------------------------------------
    ("notice period: active + announced + not yet due", _registry(main=_entry(deprecation=_dep())),
     NOTICE_DAY, None),
    ("explicit retirement after the due date", _registry(main=_retired(deprecation=_dep())), DUE_DAY, None),
    ("plain active line", _registry(), NOTICE_DAY, None),
]


def main() -> int:
    """Run every case; each one asserts a rule that would otherwise rot unenforced."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        lines = _tree(pathlib.Path(tmp))
        if sorted(lines) != [MAIN, SIDE]:
            print(f"FAIL synthetic tree discovered {sorted(lines)}, expected {[MAIN, SIDE]}")
            return 1
        for label, registry, today, expected in CASES:
            problems = validate(registry, lines, today)
            if expected is None:
                if problems:
                    failures.append(f"{label}: expected clean, got {problems}")
            elif not any(expected in problem for problem in problems):
                failures.append(f"{label}: expected {expected!r}, got {problems}")

    # clock independence of a revision condition: same registry, two days, same verdict
    condition = {"kind": "registry_revision", "at_least": 2}
    verdicts = {condition_satisfied(condition, revision=2, today=day) for day in (NOTICE_DAY, DUE_DAY)}
    if verdicts != {True}:
        failures.append(f"revision condition is not clock-free: {verdicts}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"recipe lifecycle falsifier: {len(failures)}/{len(CASES) + 1} cases wrong")
        return 1
    print(f"  lifecycle refusals fired: {len(CASES)} cases + 1 clock-independence check")
    print("RECIPE_REGISTRY_GATE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
