# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Observation protocol gate: the declaration against two independent sources.

``versions/obs_protocols.json`` states, per supported task, which protocol identity its
config carries and what that identity's observation layout is. This gate never accepts the
declaration on its own word:

* the **recorded** half compares it with the layouts the recipe goldens already recorded
  (stdlib only, so it runs while the task tree is mid-edit);
* the **live** half (``--live``) builds each registered cfg and compares the same layout from
  the constructed object, which is what the policy actually sees.

Two halves because one source describing itself is not a check. The declaration is authored,
the goldens are locked output, the live half is the running truth -- agreeing with both is the
claim, and a disagreement in either is red.

Keyed by content, not by name: a protocol's key is the first 12 hex of the digest over its own
``groups``, recomputed here. An edit that leaves the key alone is red immediately; the reviewed
digests live in ``versions/lizard/obs_protocol_anchors.json``, which this gate reads and never
rewrites (approving a protocol is a separate, deliberate act -- auto-recomputing an anchor
would approve whatever was just written).

Usage:
    python rl_exp/tools/verify/check_obs_protocol.py [--live] [--only TASK ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import obs_protocol_inventory as inv  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parents[3]
DECLARATION = _REPO / "rl_exp" / "versions" / "obs_protocols.json"
ANCHORS = _REPO / "rl_exp" / "versions" / "lizard" / "obs_protocol_anchors.json"
FORMAT_VERSION = 1
_ORDERED_FIELDS = ("terms", "dropped_terms", "clip", "scale", "noise")


def content_digest(groups) -> str:
    """The digest a protocol is keyed by: sha256 over its groups, order preserved."""
    return hashlib.sha256(inv.canonical(groups).encode("utf-8")).hexdigest()


def load(path: pathlib.Path) -> dict:
    """Read a JSON document, or return a stand-in that reports why it could not be read."""
    if not path.is_file():
        return {"_missing": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {"_unreadable": f"{path}: {err}"}


def check_self(document: dict) -> list[str]:
    """Each protocol must describe itself: key, recorded digest and content agree."""
    out: list[str] = []
    if document.get("format") != FORMAT_VERSION:
        out.append(f"format {document.get('format')!r} != {FORMAT_VERSION}")
    protocols = document.get("protocols")
    tasks = document.get("tasks")
    if not isinstance(protocols, dict) or not isinstance(tasks, dict):
        return out + ["protocols and tasks must both be objects"]
    for key, entry in sorted(protocols.items()):
        if not isinstance(entry, dict) or "groups" not in entry:
            out.append(f"{key}: protocol must be an object with 'groups'")
            continue
        digest = content_digest(entry["groups"])
        if digest[:12] != key:
            out.append(f"{key}: content digest is {digest[:12]} -- the key no longer describes its own groups")
        if entry.get("digest") != digest:
            out.append(f"{key}: recorded digest {entry.get('digest')!r} != recomputed {digest!r}")
    for task_id, route in sorted(tasks.items()):
        if not isinstance(route, dict):
            out.append(f"{task_id}: route must be an object")
            continue
        if route.get("protocol") not in protocols:
            out.append(f"{task_id}: names protocol {route.get('protocol')!r}, which the declaration does not define")
    return out


def check_anchors(document: dict, anchors: dict) -> list[str]:
    """Reviewed digests: every protocol approved, and an unreferenced one still has a purpose."""
    if "_missing" in anchors or "_unreadable" in anchors:
        return [next(iter(anchors.values()))]
    approved = anchors.get("protocols")
    if not isinstance(approved, dict):
        return ["anchors: no protocols mapping"]
    out: list[str] = []
    referenced = {entry.get("protocol") for entry in (document.get("tasks") or {}).values() if isinstance(entry, dict)}
    for key, entry in sorted((document.get("protocols") or {}).items()):
        anchor = approved.get(key)
        if anchor is None:
            out.append(f"{key}: no approved anchor -- a new or edited protocol is red until a human approves its digest")
            continue
        digest = entry.get("digest") if isinstance(entry, dict) else None
        if isinstance(anchor, dict):
            if anchor.get("digest") != digest:
                out.append(f"{key}: approved digest {anchor.get('digest')!r} != declared {digest!r}")
            if key not in referenced and not anchor.get("purpose"):
                out.append(f"{key}: no task references this protocol and its anchor states no purpose")
        else:
            out.append(f"{key}: anchor must be an object carrying the approved digest")
    for key in sorted(set(approved) - set(document.get("protocols") or {})):
        out.append(f"{key}: anchor for a protocol the declaration does not define")
    return out


def compare(declared: dict, observed: dict, where: str) -> list[str]:
    """Order-sensitive layout comparison, with the same-set-different-order case named."""
    out: list[str] = []
    if list(declared) != list(observed):
        out.append(f"{where}: group order {list(observed)} != declared {list(declared)}")
        return out
    for group, expected in declared.items():
        found = observed[group]
        if bool(expected.get("dropped")) != bool(found.get("dropped")):
            out.append(f"{where}: group {group} dropped={found.get('dropped')} != declared {expected.get('dropped')}")
            continue
        for field in _ORDERED_FIELDS:
            want, got = expected.get(field), found.get(field)
            if want == got:
                continue
            detail = "same members, different order" if sorted(want or []) == sorted(got or []) else "different members"
            out.append(f"{where}: group {group} {field} {got} != declared {want} ({detail})")
        if expected.get("flags") != found.get("flags"):
            out.append(f"{where}: group {group} flags {found.get('flags')} != declared {expected.get('flags')}")
    return out


def check_recorded(document: dict, only: list[str]) -> tuple[list[str], int]:
    """The golden half: the layouts the recipe locks recorded must be the declared ones."""
    clusters, facts, problems = inv.survey(inv.goldens())
    out = list(problems)
    protocols = document.get("protocols") or {}
    tasks = document.get("tasks") or {}
    checked = 0
    for task_id in sorted(set(tasks) - set(facts)):
        if only and task_id not in only:
            continue
        out.append(f"{task_id}: declared but no golden records it")
    for task_id in sorted(set(facts) - set(tasks)):
        if only and task_id not in only:
            continue
        out.append(f"{task_id}: recorded in a golden but absent from the declaration")
    for task_id in sorted(set(tasks) & set(facts)):
        if only and task_id not in only:
            continue
        protocol = (protocols.get(tasks[task_id].get("protocol")) or {}).get("groups")
        if protocol is None:
            continue
        checked += 1
        out.extend(compare(protocol, facts[task_id]["layout"], f"{task_id} (golden)"))
    return out, checked


def check_live(document: dict, only: list[str]) -> tuple[list[str], int]:
    """The live half: the constructed cfg the policy would read must match the declaration."""
    import check_cfg_lock as lock

    specs = lock.registered_tasks()
    out: list[str] = []
    tasks = document.get("tasks") or {}
    for task_id in sorted(set(specs) - set(tasks)):
        if only and task_id not in only:
            continue
        out.append(f"{task_id}: registered task with no protocol mapping")
    for task_id in sorted(set(tasks) - set(specs)):
        if only and task_id not in only:
            continue
        out.append(f"{task_id}: declared but not registered")
    checked = 0
    protocols = document.get("protocols") or {}
    for task_id in sorted(set(tasks) & set(specs)):
        if only and task_id not in only:
            continue
        try:
            entry = lock.build_entry(task_id, specs[task_id])
        except Exception as err:  # an identity that cannot be shown is not a verified one
            out.append(f"{task_id}: cannot build {specs[task_id]['env']!r}: {err!r}")
            continue
        env = (entry.get("snapshot") or {}).get("env") or {}
        observed, unclassified = inv.layout(env.get("observations"))
        for name in unclassified:
            out.append(f"{task_id}: {name} is neither a group field nor a term")
        declared = (protocols.get(tasks[task_id].get("protocol")) or {}).get("groups")
        if declared is None:
            continue
        checked += 1
        out.extend(compare(declared, observed, f"{task_id} (live)"))
    return out, checked


def main(argv: list[str] | None = None) -> int:
    """Gate entry point.

    Args:
        argv: command line, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 when the declaration describes the tree, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="also build each registered cfg (needs isaaclab)")
    parser.add_argument("--only", nargs="*", default=[], help="check only these task ids")
    args = parser.parse_args(argv)

    document = load(DECLARATION)
    for key in ("_missing", "_unreadable"):
        if key in document:
            print(f"  FAIL {document[key]}")
            return 1
    problems = check_self(document)
    problems += check_anchors(document, load(ANCHORS))
    recorded, recorded_count = check_recorded(document, args.only)
    problems += recorded
    live_count = 0
    if args.live:
        live, live_count = check_live(document, args.only)
        problems += live
    print(
        f"  protocols: {len(document.get('protocols') or {})} | tasks: {len(document.get('tasks') or {})}"
        f" | golden comparisons: {recorded_count} | live comparisons: {live_count}"
    )
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print(f"obs protocol: {len(problems)} problem(s)")
        return 1
    print("  declaration matches the goldens" + (" and the constructed cfgs" if args.live else "; run --live for the second half"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
