# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Recipe-line lifecycle gate: the offline half of ARCH_PLAN L01/L05 (step 2.1).

One index answers "what is this experiment line allowed to do": ``versions/lines.json``,
keyed by the same handle ``recipe_lines.discover()`` produces (``"lizard"``,
``"lizard/parkour"``). Version directories, parameter files and golden locks keep their
own conventions -- this file only owns lifecycle.

``status`` decides, it is binary (``active``/``retired``), and it is the whole permission
model: retirement is an explicit change to this directory, never a date, so nothing here reads
the clock. The runtime side reads the status it found at startup and never re-reads anything, so
the 2.2 table and the running trainer cannot disagree. What identifies a directory in the record
is the content digest of its two files, not a counter someone has to remember to bump.

Version-level exceptions ride in each entry's ``versions`` map (``null`` when there are none):
an exception may only **retire** a version -- ``active`` is what inheriting the line's status
already means -- and it carries the same evidence a retired line does. There is one exception
type on purpose: algorithm, body or recipe-plan reasons all mean the same thing (this version is
out; it is not trained again, and nothing is promised about re-running it), so the *reason* is
prose in ``reason``, never a classification field. :func:`effective_status` is the single reader
of "line status + version exception", so a gate and a launch cannot answer differently.

Refusals, all of them deliberate:

* A discovered line with no entry is rejected -- missing lifecycle must never read as
  ``active``.
* ``active`` and ``retired`` carry mutually exclusive evidence: a retired line names its
  date and reason, an active line carries neither.
* A ``successor`` must be a different, registered line that is itself active.
* A version exception must retire a version this line actually has, with a date and a reason.
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
ENTRY_KEYS = ("status", "successor", "retired_at", "reason", "versions")
VERSION_KEYS = ("status", "retired_at", "reason")


def _date(text) -> _dt.date | None:
    """Parse an ISO date, or None when the value is not one."""
    if not isinstance(text, str):
        return None
    try:
        return _dt.date.fromisoformat(text)
    except ValueError:
        return None


def _check_versions(key: str, versions, line, out: list[str]) -> None:
    """Validate one line's version-level exceptions against every rule."""
    if versions is None:
        return
    if not isinstance(versions, dict):
        out.append(f"{key}: versions must be null or an object keyed by version")
        return
    known = set(getattr(line, "versions", {}) or {})
    for version in sorted(versions):
        tag = f"{key}/{version}"
        entry = versions[version]
        if version not in known:
            out.append(f"{tag}: exception names no version of this line (dangling or misspelled)")
        if not isinstance(entry, dict):
            out.append(f"{tag}: exception must be an object")
            continue
        missing = [name for name in VERSION_KEYS if name not in entry]
        extra = sorted(set(entry) - set(VERSION_KEYS))
        if missing:
            out.append(f"{tag}: exception is missing {missing} (state it explicitly, null included)")
        if extra:
            out.append(f"{tag}: exception carries unknown fields {extra} (run-scoped data belongs in the run record)")
        if missing or extra:
            continue
        if entry["status"] != "retired":
            out.append(f"{tag}: exception status {entry['status']!r} is not 'retired' -- inheriting the "
                       "line's status is what active already means")
            continue
        if _date(entry["retired_at"]) is None:
            out.append(f"{tag}: retired needs retired_at as an ISO date, got {entry['retired_at']!r}")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            out.append(f"{tag}: retired needs a reason (why this version is out)")


def _check_entry(key: str, entry, entries: dict, line, out: list[str]) -> None:
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

    _check_versions(key, entry["versions"], line, out)


def effective_status(registry, key: str, version: str | None) -> str | None:
    """The status that decides a launch of ``version`` on line ``key``.

    The one reader of "line status + version exception": a version exception wins for that
    version, everything else inherits the line's status. The line's ``retired`` outranks every
    exception -- an exception is a claim about one version of a line that is still running, and
    reading it as "active" would let a hand-edited index put a retired line back into service.
    That case is reachable: the gates that call this one do not all run :func:`validate` first.
    ``None`` means the index cannot answer (unknown line, missing entry, invented status, an
    exception that is not a status) and every caller must refuse rather than default to ``active``.
    """
    entries = (registry or {}).get("lines")
    if not isinstance(entries, dict) or key not in entries:
        return None
    entry = entries[key]
    if not isinstance(entry, dict):
        return None
    line_status = entry.get("status")
    if line_status not in STATUSES:
        return None
    if line_status == "retired":
        return "retired"
    if version is not None:
        exceptions = entry.get("versions")
        if isinstance(exceptions, dict) and version in exceptions:
            chosen = exceptions[version]
            if isinstance(chosen, dict) and chosen.get("status") in STATUSES:
                return chosen["status"]
            return None  # an exception this reader cannot parse must not fall back to the line's status
    return line_status


def validate(registry, lines) -> list[str]:
    """Every lifecycle problem in one pass (empty list = the index is consistent).

    Args:
        registry: parsed ``lines.json``.
        lines: :class:`recipe_lines.RecipeLine` map of the tree under test.

    Returns:
        All problems, in registry order; empty means clean.
    """
    out: list[str] = []
    if not isinstance(registry, dict):
        return ["lines.json must be an object"]
    if registry.get("format") != FORMAT_VERSION:
        out.append(f"format {registry.get('format')!r} != {FORMAT_VERSION} (this gate reads one format)")
    entries = registry.get("lines")
    if not isinstance(entries, dict):
        return out + ["lines must be an object keyed by recipe-line handle"]

    for key in sorted(set(lines) - set(entries)):
        out.append(f"{key}: discovered recipe line has no lifecycle entry (missing must not read as active)")
    for key in sorted(set(entries) - set(lines)):
        out.append(f"{key}: lifecycle entry names no recipe line in this tree (dangling or misspelled)")
    for key in sorted(set(entries) & set(lines)):
        _check_entry(key, entries[key], entries, lines[key], out)
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
        return {"lines": None, "format": None, "_missing": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {"lines": None, "format": None, "_unreadable": f"{path}: {err}"}


def main() -> int:
    """Gate entry point: discover the tree, read the index, print every problem."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-test", action="store_true", help="also falsify the detector in-process")
    args = parser.parse_args()
    if args.self_test:
        import test_recipe_registry_gate as falsifier

        if falsifier.main() != 0:
            return 1

    try:
        lines = discover()
    except RecipeLineError as err:
        print(err)
        return 1

    registry = load(REGISTRY)
    problems = validate(registry, lines)
    for key in ("_missing", "_unreadable"):
        if key in registry:
            problems.insert(0, f"{key[1:]}: {registry[key]}")

    print(f"  recipe lines discovered: {len(lines)} {sorted(lines)}")
    print(f"  index: {REGISTRY.name} entries={len(registry.get('lines') or {})}")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"recipe lifecycle: {len(problems)} problem(s)")
        return 1
    print("  lifecycle consistent (L01 identity, L05 structure)")
    return 0


if __name__ == "__main__":
    # The in-process falsifier must import this instance, not execute a second copy.
    sys.modules.setdefault("check_recipe_registry", sys.modules[__name__])
    sys.exit(main())
