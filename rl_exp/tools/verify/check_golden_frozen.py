# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Freeze the acceptance baseline that stage B measures against (``ARCH_PLAN.md`` 2.4).

Hard A ("the new builder expresses an existing recipe, field for field identical") only means
something while the golden it compares against is the one that existed *before* the builder.
That makes those bytes an acceptance expectation rather than a build artefact -- and a
convention ("do not run ``--update`` during B") is not a control.

Three ways move the bar: an ``--update``, a hand edit, a file swap. ``check_cfg_lock.py``
covers the first (``--reason`` required, per-field diff printed). This covers the other two
by digest, so a re-baseline needs two edits (the table below and the acceptance record) plus
a stated reason -- one more than a silent refresh can survive.

What this gate does NOT say: that the golden is correct, or that it is reproducible. Correct
is what B3 proves (hard A against a clean regeneration); reproducible is a property of the
commit the golden came from, measured in the record's B0 section.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]

# Frozen 2026-09-16 at rev 020e6fb, before any stage-B edit; see
# rl_exp/versions/lizard/ACCEPTANCE.md section "B0 · 基线冻结". Re-baselining is legitimate -- it
# just has to be deliberate: same change edits this table and that record, and states the
# reason. Refreshing one side alone is what the freeze forbids.
#
# One such edit already happened: A0 moved the main line into versions/lizard/main/ and this
# path followed it (reason and the digest-unchanged proof are in the record's B0 addendum).
FROZEN = {
    "rl_exp/versions/cfg_baselines.json": "b18a517c43ddef5f79609dc4dea94080ad8a15926a778835bb0aa8a079c95c03",
    "rl_exp/versions/lizard/main/cfg_lock.json": "4326bd0bbf0b0b263fd071d9f3f2b1cc0a51d5137d30050567917eaa6b92a12b",
    "rl_exp/versions/lizard/parkour/cfg_lock.json": "6c60a9263323547856f4984ee4e373893260f8c99ec88e0a116a17d7cbb4c20a",
}


def check(frozen: dict[str, str], root: pathlib.Path) -> list[str]:
    """Every frozen file that is missing or no longer has its frozen bytes.

    Args:
        frozen: repo-relative path -> sha256 hex digest.
        root: tree the paths are resolved against.

    Returns:
        One message per problem; empty means the baseline still is the frozen one.
    """
    problems: list[str] = []
    for rel, expected in sorted(frozen.items()):
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: missing -- the baseline it carries is the point of the freeze")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            problems.append(f"{rel}: {actual[:16]} != frozen {expected[:16]}")
    return problems


def self_test() -> int:
    """Prove the comparison itself: a match passes, a changed byte and a deletion fail."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "same.json").write_bytes(b"{}\n")
        (root / "moved.json").write_bytes(b"{}\n")
        frozen = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ("same.json",)}
        if check({**frozen, "absent.json": frozen["same.json"]}, root) != [
            "absent.json: missing -- the baseline it carries is the point of the freeze"
        ]:
            problems.append("a deleted baseline did not read as missing")
        (root / "moved.json").write_bytes(b'{"entry": 1}\n')
        fired = check({"moved.json": frozen["same.json"]}, root)
        if len(fired) != 1 or not fired[0].startswith("moved.json: ") or "!= frozen" not in fired[0]:
            problems.append(f"a changed baseline did not read as drift: {fired}")
        if check(frozen, root):
            problems.append("an unchanged baseline read as drift")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print("GOLDEN_FROZEN_SELFTEST_FAILED")
        return 1
    print("GOLDEN_FROZEN_SELFTEST_OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Gate entry point: compare the frozen baseline digests, or test the comparison."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-test", action="store_true", help="test this gate instead of the repo")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()

    problems = check(FROZEN, _REPO)
    for problem in problems:
        print(f"  DRIFT: {problem}")
    if problems:
        print("  A moved golden is legitimate only as a deliberate re-baseline: update the digest in")
        print("  this file AND in rl_exp/versions/lizard/ACCEPTANCE.md section 'B0', give the reason,")
        print("  and review the per-field diff. Until then stage B has no baseline to prove hard A")
        print("  against -- and an expectation the new builder can regenerate by itself proves nothing.")
        print("GOLDEN_FROZEN_DRIFT")
        return 1
    print(f"GOLDEN_FROZEN_OK ({len(FROZEN)} baseline file(s) unchanged since rev 020e6fb)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
