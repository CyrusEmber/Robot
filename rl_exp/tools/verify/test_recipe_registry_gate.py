# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Negative control for ``check_recipe_registry``: every refusal must actually fire.

A lifecycle gate that only ever prints "OK" is indistinguishable from no gate. Each case below
is one rule of ARCH_PLAN 2.1 driving a synthetic tree through ``validate`` -- the tree is built
on the fly so a case can be "a line retired without its evidence" without editing the real
index.

The one property a reviewer cannot see by reading the happy path gets its own cases: ``active``
and ``retired`` carry mutually exclusive evidence, and a ``successor`` is a claim about another
line that has to hold up.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from check_recipe_registry import validate  # noqa: E402
from recipe_lines import discover  # noqa: E402

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
    entry = {"status": "active", "successor": None, "retired_at": None, "reason": None}
    entry.update(over)
    return entry


def _registry(main=None, side=None, fmt: int = 1) -> dict:
    return {
        "format": fmt,
        "lines": {MAIN: main or _entry(), SIDE: side or _entry()},
    }


def _retired(**over) -> dict:
    entry = _entry(status="retired", retired_at="2026-09-16", reason="superseded by the new line")
    entry.update(over)
    return entry


CASES: list[tuple[str, dict, str | None]] = [
    # -- identity (L01): which line is which, and nothing is guessed ------------------
    ("line discovered but never registered", {"format": 1, "lines": {}}, "has no lifecycle entry"),
    ("dangling line", {"format": 1, "lines": {MAIN: _entry(), "lizard/ghost": _entry()}},
     "names no recipe line"),
    ("entry carries a run-scoped field", _registry(main=_entry(run_id="abc")), "unknown fields"),
    ("entry omits a field instead of stating null", _registry(main={"status": "active"}), "entry is missing"),
    ("third status invented", _registry(main=_entry(status="deprecated")), "lifecycle is binary"),
    # -- retirement evidence stays consistent (L05) ----------------------------------
    ("retired without a date or a reason", _registry(main=_entry(status="retired")), "needs retired_at"),
    ("retired with a non-date", _registry(main=_retired(retired_at="yesterday")), "as an ISO date"),
    ("retired with an empty reason", _registry(main=_retired(reason="   ")), "needs a reason"),
    ("active line keeps retirement evidence", _registry(main=_entry(retired_at="2026-09-01")),
     "retirement evidence left behind"),
    ("successor does not exist", _registry(main=_retired(successor="lizard/nowhere")), "is not a registered line"),
    ("successor points at itself", _registry(main=_retired(successor=MAIN)), "points at itself"),
    ("successor is itself retired", _registry(main=_retired(successor=SIDE), side=_retired()),
     f"{SIDE!r} is not active"),
    # -- format ----------------------------------------------------------------------
    ("registry format changed without this gate", _registry(fmt=2), "format"),
    # -- the clean shapes ------------------------------------------------------------
    ("plain active line", _registry(), None),
    ("a retired line that states its date and reason", _registry(main=_retired()), None),
    ("a retired line pointing at an active successor",
     _registry(main=_retired(successor=SIDE), side=_entry()), None),
]


def main() -> int:
    """Run every case; each one asserts a rule that would otherwise rot unenforced."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        lines = _tree(pathlib.Path(tmp))
        if sorted(lines) != [MAIN, SIDE]:
            print(f"FAIL synthetic tree discovered {sorted(lines)}, expected {[MAIN, SIDE]}")
            return 1
        for label, registry, expected in CASES:
            problems = validate(registry, lines)
            if expected is None:
                if problems:
                    failures.append(f"{label}: expected clean, got {problems}")
            elif not any(expected in problem for problem in problems):
                failures.append(f"{label}: expected {expected!r}, got {problems}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"recipe lifecycle gate: {len(failures)}/{len(CASES)} case(s) wrong")
        return 1
    print(f"  {len(CASES)} refusals fired, clean shapes stayed clean")
    print("RECIPE_REGISTRY_GATE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
