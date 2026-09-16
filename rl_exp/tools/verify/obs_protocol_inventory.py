# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Read the observation layouts out of the recipe goldens, grouped by identity.

Authoring material for the protocol declaration (``ARCH_PLAN`` 3.1a) and the raw half of its
gate: the goldens are the constructed cfg trees the lock gate already verified, so this needs
no isaaclab import and stays usable while the task tree is mid-edit.

The cluster key is the layout itself -- ordered group names, ordered term names, and the
per-term clip/scale/noise presence -- never the recipe version. Two recipes that share a
layout share a protocol identity even when their version numbers are neighbours; two
neighbouring versions with different layouts must not be merged. Clustering by version would
paper over exactly that, which is the failure this file exists to make visible.

Stdlib only, read-only. Anything it cannot classify is printed, not skipped: a group-level
field the tables below do not know would otherwise be read as a term and quietly change the
cluster key.

Usage:
    python rl_exp/tools/verify/obs_protocol_inventory.py [--json]

Exit code is 0 on a readable set of goldens, 1 when a golden is missing or unreadable.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]

# The group-level fields a ``ObservationGroupCfg`` carries next to its terms.
_GROUP_FIELDS = frozenset(
    {"concatenate_terms", "concatenate_dim", "enable_corruption", "history_length", "flatten_history_dim"}
)
# The fields an ``ObsTerm`` carries. A dict with none of them is not a term this file knows.
_TERM_FIELDS = frozenset({"func", "params", "modifiers", "noise", "clip", "scale", "history_length", "flatten_history_dim"})

_TASK_IN_KEY = re.compile(r"\|(?P<task>[^|]+)$")


def goldens(root: pathlib.Path = _REPO) -> list[pathlib.Path]:
    """Every per-line recipe golden in the tree, sorted by path."""
    return sorted(root.glob("rl_exp/versions/**/cfg_lock.json"))


def entries(path: pathlib.Path) -> dict[str, dict]:
    """One golden's ``entries`` mapping, or a ``{"_error": ...}`` stand-in when unreadable."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return {"_error": f"{path}: {err}"}
    found = doc.get("entries")
    return found if isinstance(found, dict) else {"_error": f"{path}: no entries mapping"}


def layout(observations) -> tuple[dict[str, dict], list[str]]:
    """One cfg's observation layout: group name -> ``{dropped, terms, clip, noise}``.

    A removed piece is recorded, not omitted: PLAY variants null out the base ``policy`` group
    and drop single terms (``height_scan`` in the flat recipes), and a reader that skipped the
    nulls would put PLAY and TRAIN in the same cluster while the cfgs differ.

    Args:
        observations: the recorded ``observations`` subtree of one env cfg (or anything else).

    Returns:
        The layout in recorded order, plus the names of entries that are neither a known
        group-level field nor a known term field -- reported so they cannot pass as terms.
    """
    out: dict[str, dict] = {}
    unclassified: list[str] = []
    if not isinstance(observations, dict):
        return out, [repr(observations)]
    for group, body in observations.items():
        if body is None:
            out[group] = {"dropped": True, "flags": {}, "terms": [], "dropped_terms": [], "clip": [], "noise": []}
            continue
        if not isinstance(body, dict):
            unclassified.append(f"{group} (neither a mapping nor null)")
            continue
        terms, clipped, noisy, dropped = [], [], [], []
        for name, value in body.items():
            if name in _GROUP_FIELDS:
                continue
            if value is None:
                terms.append(name)
                dropped.append(name)
                continue
            if not isinstance(value, dict) or not (_TERM_FIELDS & set(value)):
                unclassified.append(f"{group}.{name}")
                continue
            terms.append(name)
            if value.get("clip") is not None:
                clipped.append(name)
            if value.get("noise") is not None:
                noisy.append(name)
        out[group] = {"dropped": False, "terms": terms, "dropped_terms": dropped, "clip": clipped, "noise": noisy}
        # group flags are part of the identity: TRAIN corrupts and applies noise, PLAY does
        # neither, so a cluster that ignored them would call two contracts the same.
        out[group]["flags"] = {name: body[name] for name in sorted(_GROUP_FIELDS & set(body))}
    return out, unclassified


def survey(paths: list[pathlib.Path]) -> tuple[dict[str, dict], dict[str, list[str]], list[str]]:
    """Layout signature -> tasks, task -> facts, and every problem found.

    Signatures are canonical JSON so that the same layout on two lines clusters together and
    an ordering change produces a different cluster rather than a silent match. The task facts
    keep ``line`` (the golden's parent line directory) and ``version`` (the recipe the lock
    recorded) so a cluster can be read against the tree it came from.
    """
    clusters: dict[str, list[str]] = {}
    facts: dict[str, dict] = {}
    problems: list[str] = []
    for path in paths:
        line = path.parent.relative_to(_REPO / "rl_exp" / "versions").as_posix()
        for key, entry in entries(path).items():
            if key == "_error":
                problems.append(entry)
                continue
            match = _TASK_IN_KEY.search(key)
            if match is None:
                problems.append(f"{path}: entry key {key!r} does not end in a task id")
                continue
            task = match.group("task")
            snapshot = entry.get("snapshot") if isinstance(entry, dict) else None
            env = snapshot.get("env") if isinstance(snapshot, dict) else None
            found, unclassified = layout((env or {}).get("observations"))
            for name in unclassified:
                problems.append(f"{path}: {task}: {name} is neither a group field nor a term")
            signature = json.dumps(found, ensure_ascii=False)
            clusters.setdefault(signature, []).append(task)
            facts[task] = {"line": line, "version": entry.get("version"), "layout": found}
    return clusters, facts, problems


def main(argv: list[str] | None = None) -> int:
    """Print the clusters (human table, or ``--json``), then every problem."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit the survey as JSON instead of a table")
    args = parser.parse_args(argv)

    paths = goldens()
    if not paths:
        print("  FAIL no cfg_lock.json found under rl_exp/versions")
        return 1
    clusters, facts, problems = survey(paths)
    print(f"  goldens: {len(paths)} | tasks: {len(facts)} | distinct layouts: {len(clusters)}")
    if args.json:
        print(json.dumps({"clusters": clusters, "tasks": facts}, ensure_ascii=False, indent=1))
    else:
        for index, (signature, tasks) in enumerate(sorted(clusters.items(), key=lambda kv: sorted(kv[1])), 1):
            body = json.loads(signature)
            shape = " | ".join(
                f"{group}: {'dropped' if v['dropped'] else len(v['terms'])}" for group, v in body.items()
            )
            print(f"\n  layout {index} ({len(tasks)} task(s)) [{shape}]")
            for group, value in body.items():
                if value["dropped"]:
                    print(f"    {group}: (dropped)")
                    continue
                live = [t if t not in value["dropped_terms"] else f"{t}(dropped)" for t in value["terms"]]
                print(f"    {group}: {', '.join(live)}")
            print(f"    tasks: {', '.join(sorted(tasks))}")
    for problem in problems:
        print(f"  FAIL {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
