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
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
# The file-digest primitive has one home (work/active/record-variant-and-snapshot-specs.md ①): this gate hashes the frozen goldens
# *with* it rather than spelling its own ``sha256(read_bytes())``, so the scan that keeps that
# home single (``check_record_bindings.py``) does not have to carry an exception for it.
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import binding  # noqa: E402

# Frozen 2026-09-16 at rev 020e6fb, before any stage-B edit; see
# rl_exp/versions/lizard/ACCEPTANCE.md section "B0 · 基线冻结". Re-baselining is legitimate -- it
# just has to be deliberate: same change edits this table and that record, and states the
# reason. Refreshing one side alone is what the freeze forbids.
#
# One such edit already happened: A0 moved the main line into versions/lizard/main/ and this
# path followed it (reason and the digest-unchanged proof are in the record's B0 addendum).
#
# A second one, 2026-09-17: the version subclass bodies were deleted (work/closed/2026/recipe-registry-and-diff-declaration.md step 3), so the
# two locks' `env_cfg_class` column -- which records the entry the registry resolves, and had named
# those classes since well before the deletion -- was repointed to the generated classes one line at
# a time. 24 lines in main, 2 in baseline, no other leaf moved (the per-field diff is in the
# record's second B0 addendum), so the frozen numbers below changed while nothing they describe did.
#
# A third one, 2026-09-18 (baseline v1.1): the baseline recipe kept `reset_robot_joints` -- pinned to
# the default pose with zero velocity -- instead of removing it with the other randomization events.
# That term is the only writer of joint state at reset in this framework (the asset-level reset
# clears actuators and wrenches only), so removing it cancelled joint reset altogether. The
# baseline-only `--update` changed 2 entries: `reset_robot_joints` null -> the pinned scale term
# (2 x 23 lines) plus the two digests it feeds and the three reason fields; 51 inserted / 7 deleted
# lines close exactly on that count. Per-field diff and the independent size cross-check are in the
# record's third B0 addendum. Recipe change itself: baseline/v1/PLAN.md section '修订' (v1.1).
# A fourth one, 2026-09-20 (end-of-line policy): all four digests below changed while **not one
# stored byte did** -- `git status` reports these files unchanged, because the change was the
# *checkout form*. `.gitattributes` now declares `* text=auto eol=lf` (it had pinned only
# `*.patch`); the working tree held 311 CRLF / 207 LF / 9 mixed files over an all-LF index, so a
# digest taken from it read as drift on any other checkout -- this gate's four files on an LF
# machine, and `[2]`'s asset locks 4 files here and ~770 there. Re-recorded from the LF form every
# checkout now produces, which is what makes the freeze portable. The `FROZEN_REVS` entries below
# still name the revisions the *content* came from: the blobs are the same objects.
FROZEN = {
    "rl_exp/versions/cfg_baselines.json": "af9c01304d3a85f701d4989128b001c82f3a005a6ac2aa1d39e70a8b927606e4",
    "rl_exp/versions/lizard/main/cfg_lock.json": "0af2bfe082ebfdc1ba86129759d6d058f11588857b61f07e10e4e266dc74ea52",
    "rl_exp/versions/lizard/parkour/cfg_lock.json": "350ecdfc6e1b256e81cfde759edc88b739e20e4a42e3c4852c7cbdfe4600edce",
    # Frozen 2026-09-17 at rev ed4d35b, the commit that landed the line: the baseline lock was
    # written *after* 020e6fb, so it entered the table later than the other three (B0 addendum).
    # It is the lock of the line that trains next, and until it was here "this line's golden
    # moved" had no digest guard at all -- the hole the record had listed as A-side debt.
    # Re-baselined 2026-09-18 (baseline v1.1, see the comment above).
    # Re-baselined 2026-09-21 (baseline v2, the third re-anchor): the line gained its second
    # version, so the lock carries four entries instead of two. Nothing in v1's two entries moved
    # -- the re-baseline was reviewed as a diff against the previous digest, and this line is the
    # record of it (acceptance/records/2026-09-21-baseline-cfg-lock-rebaseline.md).
    # Re-baselined again the same day (the fourth re-anchor): v2's head-chain guard became a
    # *contact* criterion -- params load_n 1.0 / dwell_s 0.0 instead of load_fraction_of_weight 0.1
    # / dwell_s 0.5. The per-field diff was three fields across the two v2 tasks, v1's two entries
    # still byte-identical. Same record, second section.
    "rl_exp/versions/lizard/baseline/cfg_lock.json": "c20eb597be577118be6147b71f9e355f75d50b30d644604e511413bb6fa6b055",
    # Added 2026-09-22: the lizard2 line landed its lock and nothing here was required to notice --
    # the second time a new line's golden arrived unguarded (until 2026-09-17 the baseline line's
    # lock sat outside this table too, listed then as A-side debt). That repetition is why this
    # entry comes with :func:`uncovered` below: the covered set is read off the tree now, so leaving
    # a lock out has to be a deliberate edit rather than a silence. lizard2 v1 is untrained and
    # untagged, so this freezes the bytes the line landed with.
    "rl_exp/versions/lizard2/main/cfg_lock.json": "0d67afd05d66061b2557aca047393140fd855f3b315bff737cdc2965360c05ce",
}

FROZEN_REVS: dict[str, str] = {
    "rl_exp/versions/cfg_baselines.json": "020e6fb",
    # The entry column moved twice: bbedd96 (the teacher line's 26 entries) and 27ca424 (the family
    # line's 8). These bytes are the later one's, so that is the revision they are from; the
    # snapshots they carry are still 020e6fb's (B0 addenda ② and ③).
    "rl_exp/versions/lizard/main/cfg_lock.json": "27ca424",
    "rl_exp/versions/lizard/parkour/cfg_lock.json": "020e6fb",
    # v1.1's bytes landed in 1ba6157, the same two-step shape the second re-baseline used (B0
    # addendum ②, last row): the new digest first, then this line to the revision it came from.
    # The fourth re-anchor took the same two steps: 817d64e carries the head-chain contact guard.
    "rl_exp/versions/lizard/baseline/cfg_lock.json": "817d64e",
    # The lizard2 line's bytes landed in dfdc2ae (the pre-training revision that repointed the head
    # guard); the digest above is that revision's bytes.
    "rl_exp/versions/lizard2/main/cfg_lock.json": "dfdc2ae",
}
"""Which revision each frozen file's bytes are from, for the banner only.

Separate from :data:`FROZEN` because :func:`check` is a pure function of digests and its self-test
falsifies it as one; this table adds no rule, just an honest provenance line (one file was frozen
later than the others, and a banner claiming 020e6fb for all four would be wrong).
"""


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
        actual = binding.sha256_file(path)
        if actual != expected:
            problems.append(f"{rel}: {(actual or 'unreadable')[:16]} != frozen {expected[:16]}")
    return problems


def subjects(root: pathlib.Path) -> list[str]:
    """The files this gate must cover, read off ``root`` instead of declared.

    A declared table can only list what someone remembered to add, so a lock that arrives with a new
    line is covered by nothing and the gate stays green -- which has now happened twice (the baseline
    line's lock until 2026-09-17, the lizard2 line's until 2026-09-22). Reading the set off the tree
    inverts that default: a new lock is covered the moment it lands, and leaving one out is an edit
    somebody has to make on purpose.

    Args:
        root: tree to read the subjects from.

    Returns:
        Repo-relative paths, sorted: the shared baseline file plus every line lock on disk.
    """
    patterns = ("rl_exp/versions/cfg_baselines.json", "rl_exp/versions/*/*/cfg_lock.json")
    return sorted(p.relative_to(root).as_posix() for pattern in patterns for p in root.glob(pattern))


def uncovered(root: pathlib.Path, frozen: dict[str, str]) -> list[str]:
    """Subjects present under ``root`` that ``frozen`` does not cover.

    Args:
        root: tree to read the subjects from.
        frozen: the declared subject -> digest table.

    Returns:
        One repo-relative path per uncovered subject; empty means the table covers the tree.
    """
    return [rel for rel in subjects(root) if rel not in frozen]


def self_test() -> int:
    """Prove the comparison itself: a match passes, a changed byte and a deletion fail."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "same.json").write_bytes(b"{}\n")
        (root / "moved.json").write_bytes(b"{}\n")
        frozen = {name: binding.sha256_file(root / name) for name in ("same.json",)}
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
        lock = root / "rl_exp" / "versions" / "family" / "line" / "cfg_lock.json"
        lock.parent.mkdir(parents=True)
        lock.write_bytes(b"{}\n")
        if uncovered(root, frozen) != ["rl_exp/versions/family/line/cfg_lock.json"]:
            problems.append(f"a lock nobody froze did not read as uncovered: {uncovered(root, frozen)}")
        if uncovered(root, {rel: "digest" for rel in subjects(root)}):
            problems.append("a table covering every subject read as uncovered")
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
    for rel in uncovered(_REPO, FROZEN):
        # a lock this table does not cover has no byte-level guard, and the table's silence about it
        # is what made that invisible: the entry has to be added deliberately, or the exemption
        # written down in the acceptance record.
        problems.append(
            f"{rel}: present but not frozen -- add its digest and a FROZEN_REVS entry, or state why"
            " this one is exempt in the record"
        )
    for rel in sorted(set(FROZEN) ^ set(FROZEN_REVS)):
        # a provenance entry for a file nobody checks (or the reverse) is a table that describes
        # something other than what is enforced -- one rename away from a banner that lies
        problems.append(f"{rel}: frozen and FROZEN_REVS disagree about which files are covered")
    for problem in problems:
        print(f"  DRIFT: {problem}")
    if problems:
        print("  A moved golden is legitimate only as a deliberate re-baseline: update the digest in")
        print("  this file AND in rl_exp/versions/lizard/ACCEPTANCE.md section 'B0', give the reason,")
        print("  and review the per-field diff. Until then stage B has no baseline to prove hard A")
        print("  against -- and an expectation the new builder can regenerate by itself proves nothing.")
        print("GOLDEN_FROZEN_DRIFT")
        return 1
    revs = ", ".join(f"{rev} x{list(FROZEN_REVS.values()).count(rev)}" for rev in dict.fromkeys(FROZEN_REVS.values()))
    print(f"GOLDEN_FROZEN_OK ({len(FROZEN)} baseline file(s) unchanged, frozen at: {revs})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
