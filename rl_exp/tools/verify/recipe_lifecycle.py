# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The recipe-line lifecycle decision contract (ARCH_PLAN 2.2; frozen as part of phase A).

One function answers "may this launch proceed on this line", so the old trainer, the new
launcher and the tuning entry cannot answer differently. Three callers with three private
copies of that table is the failure this section exists to prevent, and it is not visible
from any one of them.

The contract, frozen here:

* ``status`` decides, and it is the status read once at startup. Unknown, absent or invented
  status is a refusal and never a default of ``active``.
* ``operation`` is the record's word for what is being started (``new_train`` without
  ``--resume``, ``resume`` with it). It selects the refusal sentence, not the permission:
  a retired line refuses both, an active line allows both.
* A passed retirement notice does not exist here: retirement is a directory revision, and the
  clock is not consulted anywhere in this file.
* Only ``new_train`` and ``resume`` are modelled. They are the operations a launch actually
  performs, and both entries derive them from the same ``agent_cfg.resume``. A further
  operation is added with the entry that performs it, not before.

The cases below are the contract's lock: this file carries its own falsifier so a future edit
cannot quietly change what the callers will do. Runtime callers import ``judge``; the suite
runs this file to prove the table still says what it says.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

STATUSES = ("active", "retired")
OPERATIONS = ("new_train", "resume")


@dataclass(frozen=True)
class Verdict:
    """The answer for one operation on one line.

    Attributes:
        allowed: whether the launch may proceed.
        reason: the sentence a caller prints when refusing, or why it proceeded.
    """

    allowed: bool
    reason: str


def judge(operation: str, status: str | None) -> Verdict:
    """Decide whether one operation may proceed on a line.

    Args:
        operation: one of :data:`OPERATIONS`. The caller derives it from ``agent_cfg.resume``.
        status: the line's status as read at startup, or None when the index is missing or
            says nothing about it.

    Returns:
        The verdict. Nothing is defaulted: an unknown operation, an unknown status or a missing
        lifecycle refuses, so no caller can turn "not known" into permission.
    """
    if operation not in OPERATIONS:
        return Verdict(False, f"unknown operation {operation!r}; refusing rather than guessing")
    if status not in STATUSES:
        return Verdict(
            False,
            f"lifecycle status {status!r} is missing or unknown; a missing lifecycle must not read as active",
        )
    if status == "active":
        return Verdict(True, f"{operation} allowed on an active line")
    return Verdict(
        False,
        f"retired line: refusing {operation}; retirement stops new work on this line",
    )


CASES: list[tuple[str, dict, bool, str | None]] = [
    # operation x status, the 2.2 table
    ("new training on an active line", {"operation": "new_train", "status": "active"}, True, None),
    ("resume on an active line", {"operation": "resume", "status": "active"}, True, None),
    ("new training on a retired line", {"operation": "new_train", "status": "retired"}, False, "refusing new_train"),
    ("resume on a retired line", {"operation": "resume", "status": "retired"}, False, "refusing resume"),
    # nothing is defaulted
    ("lifecycle missing", {"operation": "new_train", "status": None}, False, "must not read as active"),
    ("lifecycle invented", {"operation": "new_train", "status": "deprecated"}, False, "unknown"),
    ("operation invented", {"operation": "train_ish", "status": "active"}, False, "unknown operation"),
]


def main() -> int:
    """Run the contract's own cases: the table must say what it claims to say."""
    failures: list[str] = []
    for label, kwargs, expected_allowed, expected_fragment in CASES:
        verdict = judge(**kwargs)
        if verdict.allowed != expected_allowed:
            failures.append(f"{label}: expected allowed={expected_allowed}, got {verdict!r}")
        elif expected_fragment and expected_fragment not in verdict.reason:
            failures.append(f"{label}: expected {expected_fragment!r} in {verdict!r}")

    # a refusal must not promise a successor: the index may register none (lizard/parkour does not)
    for operation in OPERATIONS:
        reason = judge(operation, "retired").reason
        if "successor" in reason:
            failures.append(f"{operation} on a retired line promises a successor: {reason!r}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"lifecycle contract: {len(failures)}/{len(CASES) + len(OPERATIONS)} cases wrong")
        return 1
    print(f"  contract cases: {len(CASES)} verdicts + {len(OPERATIONS)} refusal-wording checks")
    print("LIFECYCLE_CONTRACT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
