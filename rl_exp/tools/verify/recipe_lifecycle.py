# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The recipe-line lifecycle decision contract (ARCH_PLAN 2.2; frozen as part of phase A).

One function answers "may this operation proceed on this line", so the old trainer, the new
launcher and the tuning entry cannot answer differently. Three callers with three private
copies of that table is the failure this section exists to prevent, and it is not visible
from any one of them.

The contract, frozen here (phase A's exit requires a frozen contract, not just a frozen
signature):

* ``status`` decides. It is the status read once at startup; unknown or absent status is a
  refusal and never a default of ``active``.
* ``allow_retired_resume`` affects ``resume`` and nothing else, and only when a source
  checkpoint actually resolved. It is not a general "anything goes on a retired line" switch.
* ``drop_curriculum_state`` is a separate decision: the two flags never imply one another, and
  the verdict reports both so no caller can infer one from the other.
* A passed ``retire_not_before`` does not block. The clock is the offline gate's business; the
  runtime warns and records, and permission still comes from ``status``.
* Reading, evaluation, export and rebuild stay allowed on a retired line. Retirement stops new
  work, it does not revoke history -- and it never relaxes protocol, asset or model checks,
  which live elsewhere.

The cases below are the contract's lock: this file carries its own falsifier so a future edit
cannot quietly change what the three callers will do. Runtime callers import ``judge``; the
suite runs this file to prove the table still says what it says.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

STATUSES = ("active", "retired")
NEW_WORK = ("new_train", "tune", "new_recipe")
HISTORY_ONLY = ("load_ckpt", "eval", "export", "rebuild")
OPERATIONS = (*NEW_WORK, "resume", *HISTORY_ONLY, "modify_recipe")
FORBIDDEN = ("modify_recipe",)


@dataclass(frozen=True)
class Verdict:
    """The answer for one operation on one line.

    Attributes:
        allowed: whether the operation may proceed.
        reason: the sentence a caller prints when refusing, or why it proceeded.
        warn: a non-blocking warning to record (a due-but-unapplied retirement announcement).
    """

    allowed: bool
    reason: str
    warn: str | None = None


@dataclass(frozen=True)
class FlagEffects:
    """What the two flags actually do, each computed from its own flag alone.

    Attributes:
        lifecycle_exempted: the retired-line restriction was lifted (requires a resume and a
            resolved source checkpoint).
        curriculum_dropped: restored curriculum state will be discarded.
        problems: refusals raised by the flags themselves.
    """

    lifecycle_exempted: bool
    curriculum_dropped: bool
    problems: tuple[str, ...] = field(default_factory=tuple)


def flag_effects(
    *,
    is_resume: bool,
    allow_retired_resume: bool = False,
    has_source_checkpoint: bool = False,
    drop_curriculum_state: bool = False,
) -> FlagEffects:
    """Resolve the two independent flags into their effects.

    Args:
        is_resume: whether the operation is a resume, which both flags depend on.
        allow_retired_resume: the request to continue on a retired line.
        has_source_checkpoint: whether a source checkpoint actually resolved.
        drop_curriculum_state: the request to discard restored curriculum state.

    Returns:
        The two effects, each derived only from its own flag, plus any flag-level refusal.
    """
    problems: list[str] = []
    if allow_retired_resume and not is_resume:
        problems.append("--allow_retired_resume needs a resume; it is not a general permission")
    if allow_retired_resume and is_resume and not has_source_checkpoint:
        problems.append("--allow_retired_resume needs a resolved source checkpoint")
    if drop_curriculum_state and not is_resume:
        problems.append("--drop_curriculum_state without a resume is a cold start; begin a new run")
    return FlagEffects(
        lifecycle_exempted=bool(allow_retired_resume and is_resume and has_source_checkpoint),
        curriculum_dropped=bool(drop_curriculum_state and is_resume),
        problems=tuple(problems),
    )


def judge(
    operation: str,
    status: str | None,
    *,
    allow_retired_resume: bool = False,
    has_source_checkpoint: bool = False,
    drop_curriculum_state: bool = False,
    retirement_due: bool = False,
) -> Verdict:
    """Decide whether one operation may proceed on a line.

    Args:
        operation: one of :data:`OPERATIONS`.
        status: the line's status as read at startup, or None when the index is missing or
            says nothing about it.
        allow_retired_resume: the historical-continuation flag.
        has_source_checkpoint: whether a source checkpoint resolved.
        drop_curriculum_state: the separate curriculum-state flag.
        retirement_due: whether the line's announced retirement condition is already met
            (the offline gate is red; the run warns and records).

    Returns:
        The verdict. Flags that are unusable on their own are refused before any permission is
        considered, so a caller cannot get a green answer out of a misused flag.
    """
    if operation not in OPERATIONS:
        return Verdict(False, f"unknown operation {operation!r}; refusing rather than guessing")
    if status not in STATUSES:
        return Verdict(
            False,
            f"lifecycle status {status!r} is missing or unknown; a missing lifecycle must not read as active",
        )

    effects = flag_effects(
        is_resume=operation == "resume",
        allow_retired_resume=allow_retired_resume,
        has_source_checkpoint=has_source_checkpoint,
        drop_curriculum_state=drop_curriculum_state,
    )
    if effects.problems:
        return Verdict(False, "; ".join(effects.problems))

    if operation in FORBIDDEN:
        return Verdict(False, "published recipe content is never modified in place; publish a new revision")

    warn = None
    if retirement_due and status == "active":
        warn = (
            "the line's announced retirement is due and the directory has not been revised;"
            " recording the overdue directory, proceeding under status=active"
        )

    if operation in HISTORY_ONLY:
        return Verdict(True, f"{operation} reads history; retirement never revokes it", warn)

    if status == "active":
        return Verdict(True, f"{operation} allowed on an active line", warn)

    if operation == "resume" and effects.lifecycle_exempted:
        return Verdict(True, "historical continuation explicitly allowed on a retired line", warn)
    if operation == "resume":
        return Verdict(False, "retired line: refusing to resume without --allow_retired_resume")
    return Verdict(
        False,
        f"retired line: refusing {operation}; new work belongs to an active successor line",
    )


CASES: list[tuple[str, dict, bool, str | None]] = [
    # operation x status, the 2.2 table
    ("new training on an active line", {"operation": "new_train", "status": "active"}, True, None),
    ("new training on a retired line", {"operation": "new_train", "status": "retired"}, False, "successor"),
    ("tuning on a retired line", {"operation": "tune", "status": "retired"}, False, "refusing tune"),
    ("a new recipe on a retired line", {"operation": "new_recipe", "status": "retired"}, False, "new_recipe"),
    ("resume on an active line", {"operation": "resume", "status": "active"}, True, None),
    ("resume on a retired line", {"operation": "resume", "status": "retired"}, False, "without --allow_retired"),
    ("explicit historical continuation",
     {"operation": "resume", "status": "retired", "allow_retired_resume": True, "has_source_checkpoint": True},
     True, "explicitly allowed"),
    ("continuation without a source checkpoint",
     {"operation": "resume", "status": "retired", "allow_retired_resume": True}, False, "source checkpoint"),
    ("reading history on a retired line", {"operation": "eval", "status": "retired"}, True, "never revokes"),
    ("loading a checkpoint on a retired line", {"operation": "load_ckpt", "status": "retired"}, True, None),
    ("export on a retired line", {"operation": "export", "status": "retired"}, True, None),
    ("rebuild on a retired line", {"operation": "rebuild", "status": "retired"}, True, None),
    ("modifying a published recipe on an active line", {"operation": "modify_recipe", "status": "active"},
     False, "new revision"),
    ("modifying a published recipe on a retired line", {"operation": "modify_recipe", "status": "retired"},
     False, "new revision"),
    # identity and index problems must not pass
    ("lifecycle missing", {"operation": "new_train", "status": None}, False, "must not read as active"),
    ("lifecycle invented", {"operation": "new_train", "status": "deprecated"}, False, "unknown"),
    ("operation invented", {"operation": "train_ish", "status": "active"}, False, "unknown operation"),
    # the announcement never blocks, and never passes silently
    ("announcement due on an active line", {"operation": "new_train", "status": "active", "retirement_due": True},
     True, None),
    ("announcement not due yet", {"operation": "new_train", "status": "active", "retirement_due": False}, True, None),
    # flag misuse is refused even where the line would allow the operation
    ("continuation flag without a resume",
     {"operation": "new_train", "status": "active", "allow_retired_resume": True}, False, "needs a resume"),
    ("curriculum drop without a resume",
     {"operation": "new_train", "status": "active", "drop_curriculum_state": True}, False, "cold start"),
    ("curriculum drop on a plain resume",
     {"operation": "resume", "status": "active", "drop_curriculum_state": True}, True, None),
    ("continuation and drop together",
     {"operation": "resume", "status": "retired", "allow_retired_resume": True,
      "has_source_checkpoint": True, "drop_curriculum_state": True}, True, None),
]


def main() -> int:
    """Run the contract's own cases: the table must say what it claims to say."""
    failures: list[str] = []
    for label, kwargs, expected_allowed, expected_fragment in CASES:
        verdict = judge(**kwargs)
        if verdict.allowed != expected_allowed:
            failures.append(f"{label}: expected allowed={expected_allowed}, got {verdict!r}")
        elif expected_fragment and expected_fragment not in f"{verdict.reason} {verdict.warn}":
            failures.append(f"{label}: expected {expected_fragment!r} in {verdict!r}")

    # the warning exists exactly when the announcement is due on an active line
    due = judge("new_train", "active", retirement_due=True).warn
    if not due:
        failures.append("a due announcement on an active line must produce a warning")
    if judge("new_train", "active").warn:
        failures.append("an active line with no due announcement must not warn")

    # the two flags never move each other
    both = flag_effects(is_resume=True, allow_retired_resume=True, has_source_checkpoint=True,
                        drop_curriculum_state=True)
    if not (both.lifecycle_exempted and both.curriculum_dropped):
        failures.append(f"both flags together must set both effects, got {both!r}")
    only_exempt = flag_effects(is_resume=True, allow_retired_resume=True, has_source_checkpoint=True)
    if only_exempt.curriculum_dropped:
        failures.append("allow_retired_resume must never drop curriculum state")
    only_drop = flag_effects(is_resume=True, drop_curriculum_state=True)
    if only_drop.lifecycle_exempted:
        failures.append("drop_curriculum_state must never exempt the lifecycle gate")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"lifecycle contract: {len(failures)}/{len(CASES) + 5} cases wrong")
        return 1
    print(f"  contract cases: {len(CASES)} verdicts + warning shape + 3 independence checks")
    print("LIFECYCLE_CONTRACT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
