# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Recipe-line lifecycle gate: the offline half of ARCH_PLAN L01/L05/L06 (step 2.1).

One index answers "what is this experiment line allowed to do": ``versions/lines.json``,
keyed by the same handle ``recipe_lines.discover()`` produces (``"lizard"``,
``"lizard/parkour"``). Version directories, parameter files and golden locks keep their
own conventions -- this file only owns lifecycle.

Split of authority (ARCH_PLAN 2.2, decided 2026-09-16):

* ``status`` decides permissions. ``active``/``retired`` and nothing else. The runtime
  side of this gate reads the status it found at startup and never re-reads the clock,
  so the 2.2 table and the running trainer cannot disagree.
* ``deprecation`` announces a migration and carries ``retire_not_before`` -- the
  earliest condition at which retiring is allowed. It never blocks anything by itself:
  a date passing does not retire a line, an explicit directory revision does.
* This gate is where the clock lives. ``active`` with the condition already satisfied is
  red here (the directory is overdue for its explicit revision) while the runtime only
  warns and keeps the record -- an un-run gate must not become a silent permission.

Refusals, all of them deliberate:

* A discovered line with no entry is rejected -- missing lifecycle must never read as
  ``active``.
* ``active`` and ``retired`` carry mutually exclusive evidence: a retired line names its
  date and reason, an active line carries neither.
* A condition that is not machine-decidable (free text, unknown ``kind``) is rejected at
  the type level, because a condition that only a human can evaluate is not a condition.
* ``declared_at`` later than ``retire_not_before`` is rejected: the announcement would
  have left no notice period at all.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from recipe_lines import RecipeLineError, discover  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parents[3]
REGISTRY = _REPO / "rl_exp" / "versions" / "lines.json"
FORMAT_VERSION = 1
STATUSES = ("active", "retired")
ENTRY_KEYS = ("status", "successor", "retired_at", "reason", "deprecation")
DEPRECATION_KEYS = ("notice", "declared_at", "retire_not_before")
CONDITION_KINDS = ("date", "registry_revision")


def _date(text) -> _dt.date | None:
    """Parse an ISO date, or None when the value is not one."""
    if not isinstance(text, str):
        return None
    try:
        return _dt.date.fromisoformat(text)
    except ValueError:
        return None


def condition_satisfied(condition, *, revision: int, today: _dt.date) -> bool | None:
    """Whether a ``retire_not_before`` condition holds now.

    Args:
        condition: the declared condition, ``{"kind": ...}``.
        revision: the registry's own ``revision`` -- what ``registry_revision`` reads.
        today: the date to evaluate against. Injected so a caller (and the falsifier)
            can evaluate any day without touching the system clock.

    Returns:
        True/False when the condition is decidable, None when it is not (unknown kind or
        malformed operands). None is a refusal, never a "satisfied".
    """
    if not isinstance(condition, dict):
        return None
    if condition.get("kind") == "date":
        when = _date(condition.get("not_before"))
        return None if when is None else today >= when
    if condition.get("kind") == "registry_revision":
        at_least = condition.get("at_least")
        if isinstance(at_least, bool) or not isinstance(at_least, int) or at_least < 1:
            return None
        return revision >= at_least
    return None


def _check_deprecation(key: str, block, revision: int, today: _dt.date, out: list[str]) -> bool | None:
    """Validate a deprecation block; return its condition verdict, or None if unusable."""
    if not isinstance(block, dict):
        out.append(f"{key}: deprecation must be an object or null")
        return None
    missing = [name for name in DEPRECATION_KEYS if name not in block]
    extra = sorted(set(block) - set(DEPRECATION_KEYS))
    if missing:
        out.append(f"{key}: deprecation is missing {missing} (an unstated field is not a default)")
    if extra:
        out.append(f"{key}: deprecation carries unknown fields {extra}")
    if missing or extra:
        return None
    notice = block["notice"]
    if not isinstance(notice, str) or not notice.strip():
        out.append(f"{key}: deprecation.notice must be a non-empty string (nothing to tell users)")
    declared = _date(block["declared_at"])
    if declared is None:
        out.append(f"{key}: deprecation.declared_at {block['declared_at']!r} is not an ISO date")
    condition = block["retire_not_before"]
    if not isinstance(condition, dict) or condition.get("kind") not in CONDITION_KINDS:
        got = condition.get("kind") if isinstance(condition, dict) else condition
        out.append(
            f"{key}: retire_not_before.kind {got!r} is not one of {list(CONDITION_KINDS)}"
            f" -- a condition that only a human can evaluate is not a condition"
        )
        return None
    verdict = condition_satisfied(condition, revision=revision, today=today)
    if verdict is None:
        out.append(f"{key}: retire_not_before {condition!r} is not machine-decidable")
        return None
    if condition["kind"] == "date" and declared is not None:
        when = _date(condition.get("not_before"))
        if when is not None and declared > when:
            out.append(
                f"{key}: declared_at {declared} is later than retire_not_before {when}"
                f" -- the announcement left no notice period"
            )
    return verdict


def _check_entry(key: str, entry, entries: dict, revision: int, today: _dt.date, out: list[str]) -> None:
    """Validate one line entry against every lifecycle rule."""
    if not isinstance(entry, dict):
        out.append(f"{key}: entry must be an object")
        return
    missing = [name for name in ENTRY_KEYS if name not in entry]
    extra = sorted(set(entry) - set(ENTRY_KEYS))
    if missing:
        out.append(f"{key}: entry is missing {missing} (state it explicitly, null included)")
    if extra:
        out.append(f"{key}: entry carries unknown fields {extra} (run-scoped data belongs in the run record)")
    if missing or extra:
        return

    status = entry["status"]
    if status not in STATUSES:
        out.append(f"{key}: status {status!r} is not one of {list(STATUSES)} -- lifecycle is binary by design")
        return

    retired_at, reason, successor = entry["retired_at"], entry["reason"], entry["successor"]
    if status == "retired":
        if _date(retired_at) is None:
            out.append(f"{key}: retired needs retired_at as an ISO date, got {retired_at!r}")
        if not isinstance(reason, str) or not reason.strip():
            out.append(f"{key}: retired needs a reason (why this line was closed)")
    else:
        for name, value in (("retired_at", retired_at), ("reason", reason)):
            if value is not None:
                out.append(f"{key}: active line still carries {name}={value!r} (retirement evidence left behind)")

    if successor is not None:
        if successor not in entries:
            out.append(f"{key}: successor {successor!r} is not a registered line")
        elif successor == key:
            out.append(f"{key}: successor points at itself")
        elif isinstance(entries[successor], dict) and entries[successor].get("status") != "active":
            out.append(f"{key}: successor {successor!r} is not active")

    block = entry["deprecation"]
    if block is None:
        return
    verdict = _check_deprecation(key, block, revision, today, out)
    if verdict is None:
        return
    if status == "retired" and not verdict:
        out.append(
            f"{key}: retired before its own retire_not_before condition holds"
            f" -- amend or drop the announcement in the same revision, do not cross it"
        )
    elif status == "active" and verdict:
        out.append(
            f"{key}: retire_not_before has passed but the line is still active"
            f" -- the directory owes an explicit revision to retired (offline red; runtime warns and records)"
        )


def validate(registry, lines, today: _dt.date) -> list[str]:
    """Every lifecycle problem in one pass (empty list = the index is consistent).

    Args:
        registry: parsed ``lines.json``.
        lines: :class:`recipe_lines.RecipeLine` map of the tree under test.
        today: date used to evaluate ``date`` conditions.

    Returns:
        All problems, in registry order; empty means clean.
    """
    out: list[str] = []
    if not isinstance(registry, dict):
        return ["lines.json must be an object"]
    if registry.get("format") != FORMAT_VERSION:
        out.append(f"format {registry.get('format')!r} != {FORMAT_VERSION} (this gate reads one format)")
    revision = registry.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        out.append(f"revision {revision!r} must be a positive integer -- registry_revision conditions read it")
        revision = 1
    entries = registry.get("lines")
    if not isinstance(entries, dict):
        return out + ["lines must be an object keyed by recipe-line handle"]

    for key in sorted(set(lines) - set(entries)):
        out.append(f"{key}: discovered recipe line has no lifecycle entry (missing must not read as active)")
    for key in sorted(set(entries) - set(lines)):
        out.append(f"{key}: lifecycle entry names no recipe line in this tree (dangling or misspelled)")
    for key in sorted(set(entries) & set(lines)):
        _check_entry(key, entries[key], entries, revision, today, out)
    return out


def load(path: pathlib.Path) -> dict:
    """Read the lifecycle index.

    Args:
        path: the ``lines.json`` to read.

    Returns:
        The parsed registry, or a ``{"lines": {}}`` stand-in plus an unusable-index
        problem string when the file is missing or unreadable.
    """
    if not path.is_file():
        return {"lines": None, "format": None, "revision": None, "_missing": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {"lines": None, "format": None, "revision": None, "_unreadable": f"{path}: {err}"}


def main() -> int:
    """Gate entry point: discover the tree, read the index, print every problem."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--now",
        default=None,
        help="evaluate date conditions as of this ISO date (default: today's date)",
    )
    args = parser.parse_args()
    today = _date(args.now) if args.now else _dt.date.today()
    if today is None:
        print(f"--now {args.now!r} is not an ISO date")
        return 1

    try:
        lines = discover()
    except RecipeLineError as err:
        print(err)
        return 1

    registry = load(REGISTRY)
    problems = validate(registry, lines, today)
    for key in ("_missing", "_unreadable"):
        if key in registry:
            problems.insert(0, f"{key[1:]}: {registry[key]}")

    print(f"  recipe lines discovered: {len(lines)} {sorted(lines)}")
    print(f"  index: {REGISTRY.name} revision={registry.get('revision')} entries={len(registry.get('lines') or {})}")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"recipe lifecycle: {len(problems)} problem(s)")
        return 1
    print("  lifecycle consistent (L01 identity, L05 structure, L06 declaration)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
