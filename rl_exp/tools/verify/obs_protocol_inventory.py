# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Read the observation layouts out of the recipe goldens, grouped by identity.

Authoring material for the protocol declaration (``ARCH_PLAN`` 3.1a) and the raw half of its
gate: the goldens are the constructed cfg trees the lock gate already verified, so this needs
no isaaclab import and stays usable while the task tree is mid-edit.

The cluster key is the layout itself -- ordered group names, ordered term names, the clip,
scale and noise values, and the group flags -- never the recipe version. Two recipes that share a
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
import hashlib
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
            out[group] = {
                "dropped": True,
                "flags": {},
                "terms": [],
                "dropped_terms": [],
                "clip": {},
                "scale": {},
                "noise": {},
            }
            continue
        if not isinstance(body, dict):
            unclassified.append(f"{group} (neither a mapping nor null)")
            continue
        terms, clipped, noisy, dropped, scaled = [], {}, {}, [], {}
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
            # the values, not just their presence: a noise sigma or a clip bound edited in
            # place is the change this record exists to catch, and "has noise" cannot see it
            if value.get("clip") is not None:
                clipped[name] = value["clip"]
            if value.get("scale") is not None:
                scaled[name] = value["scale"]
            if value.get("noise") is not None:
                noisy[name] = value["noise"]
        out[group] = {
            "dropped": False,
            "terms": terms,
            "dropped_terms": dropped,
            "clip": clipped,
            "scale": scaled,
            "noise": noisy,
        }
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


def record(clusters: dict[str, list[str]], facts: dict[str, dict]) -> dict:
    """The declaration draft: protocols keyed by their own content digest.

    The key is the digest rather than a human name because a name can drift from the content
    it claims to describe, and a silent edit would then keep the same key. Keyed by digest, an
    edit changes the key, the entry no longer describes itself, and the gate is red before any
    reviewer has to notice. Labels stay free text and never take part in the check.
    """
    protocols: dict[str, dict] = {}
    tasks: dict[str, dict] = {}
    for signature, task_ids in clusters.items():
        body = json.loads(signature)
        digest = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
        protocols.setdefault(digest[:12], {"digest": digest, "label": "", "groups": body})
        for task in task_ids:
            fact = facts[task]
            tasks[task] = {"protocol": digest[:12], "version": fact["version"], "line": fact["line"]}
    return {
        "format": 1,
        "note": (
            "Observation protocol declaration (ARCH_PLAN Step 3.1a). Protocols are keyed by the "
            "first 12 hex of their content digest over 'groups' in recorded order; the gate "
            "recomputes it and the approved digests live in versions/lizard/obs_protocol_anchors.json."
        ),
        "protocols": dict(sorted(protocols.items())),
        "tasks": dict(sorted(tasks.items())),
    }


def canonical(body) -> str:
    """Order-preserving canonical JSON: group and term order is part of the protocol."""
    return json.dumps(body, ensure_ascii=False, sort_keys=False, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    """Print the clusters (human table, or ``--json``), then every problem.

    ``--out`` writes the declaration draft instead of printing; it is the only mode that writes
    anything, and it exists so the draft is produced by the same reader that the gate's offline
    half uses rather than retyped.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit the survey as JSON instead of a table")
    parser.add_argument("--out", metavar="PATH", help="write the declaration draft to PATH (authoring only)")
    args = parser.parse_args(argv)

    paths = goldens()
    if not paths:
        print("  FAIL no cfg_lock.json found under rl_exp/versions")
        return 1
    clusters, facts, problems = survey(paths)
    if problems:
        for problem in problems:
            print(f"  FAIL {problem}")
        return 1
    print(f"  goldens: {len(paths)} | tasks: {len(facts)} | distinct layouts: {len(clusters)}")
    if args.out:
        document = record(clusters, facts)
        path = pathlib.Path(args.out)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"  wrote {path} ({len(document['protocols'])} protocol(s), {len(document['tasks'])} task(s))")
        return 0
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
