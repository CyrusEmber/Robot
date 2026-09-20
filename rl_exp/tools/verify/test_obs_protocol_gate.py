# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Negative control for check_obs_protocol.py: every drift it claims to catch must fire.

The real declaration is the fixture: each case tampers one thing in a copy and requires the
gate to say so. A gate whose failure modes were never demonstrated is not a gate -- and the
ordering cases matter most, because a same-members-different-order edit is exactly what a
"dimensions still match" check would pass.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import check_obs_protocol as g  # noqa: E402

PROBLEMS: list[str] = []
DECLARED = g.load(g.DECLARATION)
ANCHORED = g.load(g.ANCHORS)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def copy_of(document: dict) -> dict:
    return copy.deepcopy(document)


def fires(name: str, keyword: str, problems: list[str]) -> None:
    check(name, any(keyword in p for p in problems), f"no problem containing {keyword!r}: {problems[:4]}")


def first_protocol(document: dict, predicate=None) -> str:
    for key, entry in sorted(document["protocols"].items()):
        if predicate is None or predicate(entry):
            return key
    raise AssertionError("no protocol matched the predicate")


def task_of(document: dict, protocol: str) -> str:
    for task_id, route in sorted(document["tasks"].items()):
        if route["protocol"] == protocol:
            return task_id
    raise AssertionError(f"no task references {protocol}")


def main() -> int:
    PROBLEMS.clear()
    # --- the real declaration is clean on both halves it can run offline ---------------
    check("real/self-consistent", g.check_self(DECLARED) == [], f"{g.check_self(DECLARED)}")
    check("real/anchors-approved", g.check_anchors(DECLARED, ANCHORED) == [], f"{g.check_anchors(DECLARED, ANCHORED)}")
    recorded, count = g.check_recorded(DECLARED, [])
    check("real/goldens-agree", recorded == [] and count == len(DECLARED["tasks"]), f"{recorded[:3]} (checked {count})")

    # --- a protocol must describe itself ----------------------------------------------
    stale = copy_of(DECLARED)
    key = first_protocol(stale)
    stale["protocols"][key]["groups"] = {**stale["protocols"][key]["groups"], "_smuggled": {}}
    fires("self/key-no-longer-describes-content", "no longer describes", g.check_self(stale))

    lied = copy_of(DECLARED)
    lied["protocols"][first_protocol(lied)]["digest"] = "0" * 64
    fires("self/recorded-digest-mismatch", "!= recomputed", g.check_self(lied))

    dangling = copy_of(DECLARED)
    next(iter(dangling["tasks"].values()))["protocol"] = "ffffffffffff"
    fires("self/task-names-undefined-protocol", "does not define", g.check_self(dangling))

    check("self/format-version", any("format" in p for p in g.check_self({"format": 99})))

    # --- approved digests are reviewed, never recomputed ------------------------------
    unapproved = copy_of(DECLARED)
    unapproved["protocols"]["0123456789ab"] = copy_of(unapproved["protocols"][key])
    fires("anchors/unapproved-protocol", "no approved anchor", g.check_anchors(unapproved, ANCHORED))

    mismatched = copy_of(ANCHORED)
    mismatched["protocols"][key] = {**mismatched["protocols"][key], "digest": "0" * 64}
    fires("anchors/digest-mismatch", "!= declared", g.check_anchors(DECLARED, mismatched))

    orphan = copy_of(ANCHORED)
    orphan["protocols"]["ffffffffffff"] = {"digest": "0" * 64, "purpose": ""}
    fires("anchors/unknown-protocol", "does not define", g.check_anchors(DECLARED, orphan))

    unreferenced = copy_of(DECLARED)
    lone = copy_of(unreferenced["protocols"][key])
    unreferenced["protocols"].update({"111111111111": lone})
    # drop every task that referenced the original so the copy has an unused protocol
    unreferenced["tasks"] = {t: r for t, r in unreferenced["tasks"].items() if r["protocol"] != key}
    anchors = copy_of(ANCHORED)
    anchors["protocols"]["111111111111"] = {"digest": lone["digest"], "purpose": ""}
    fires("anchors/unreferenced-without-purpose", "states no purpose", g.check_anchors(unreferenced, anchors))
    anchors["protocols"]["111111111111"]["purpose"] = "kept for the frozen vN history"
    anchors["protocols"][key]["purpose"] = "kept because the copy dropped its tasks"  # this copy also unreferenced it
    check(
        "anchors/unreferenced-with-purpose-passes",
        g.check_anchors(unreferenced, anchors) == [],
        f"{g.check_anchors(unreferenced, anchors)[:3]}",
    )

    # --- the approved widths are pinned by their own digest --------------------------
    dimmed = sorted(key for key, entry in ANCHORED["protocols"].items() if entry.get("dims"))[0]

    edited = copy_of(ANCHORED)
    first_group = sorted(edited["protocols"][dimmed]["dims"])[0]
    edited["protocols"][dimmed]["dims"][first_group] += 1
    fires("dims/in-place-edit", "without a re-approval", g.check_anchors(DECLARED, edited))

    unapproved = copy_of(ANCHORED)
    unapproved["protocols"][dimmed].pop("dims_digest")
    fires("dims/no-approved-digest", "without a re-approval", g.check_anchors(DECLARED, unapproved))

    # an approved width has to say what asserted it: the digest is recomputable, the citation is not
    uncited = copy_of(ANCHORED)
    uncited["protocols"][dimmed].pop("evidence")
    fires("dims/no-evidence", "cite no evidence", g.check_anchors(DECLARED, uncited))

    cited_void = copy_of(ANCHORED)
    cited_void["protocols"][dimmed]["dims"] = {}
    cited_void["protocols"][dimmed].pop("dims_digest")
    fires("dims/evidence-without-widths", "nothing to cite", g.check_anchors(DECLARED, cited_void))

    stray = copy_of(ANCHORED)
    stray["protocols"][dimmed]["dims"]["invented_group"] = 5
    fires("dims/unknown-group", "does not carry live", g.check_anchors(DECLARED, stray))

    typed = copy_of(ANCHORED)
    typed["protocols"][dimmed]["dims"][first_group] = True
    fires("dims/bool-is-not-a-width", "not a positive integer", g.check_anchors(DECLARED, typed))

    # all-or-nothing needs a protocol that carries more than one width to be testable at all
    multi = sorted(key for key, entry in ANCHORED["protocols"].items() if len(entry.get("dims") or {}) > 1)
    check("dims/a-multi-group-protocol-exists", bool(multi), "no multi-group width map to test the rule against")
    if multi:
        partial = copy_of(ANCHORED)
        partial["protocols"][multi[0]]["dims"].pop(sorted(partial["protocols"][multi[0]]["dims"])[0])
        fires("dims/partial-map", "all or nothing", g.check_anchors(DECLARED, partial))

    # --- ordering: the case a dimension check would pass ------------------------------
    swapped = copy_of(DECLARED)
    groups = swapped["protocols"][key]["groups"]
    first_group = next(iter(groups))
    terms = groups[first_group]["terms"]
    if len(terms) >= 2:
        terms[0], terms[1] = terms[1], terms[0]
        _, swapped_count = g.check_recorded(swapped, [])
        fired = g.check_recorded(swapped, [])[0]
        fires("order/term-swap", "same members, different order", fired)
        check("order/term-swap-still-compares", swapped_count == len(DECLARED["tasks"]), f"checked {swapped_count}")

    regrouped = copy_of(DECLARED)
    body = regrouped["protocols"][key]["groups"]
    if len(body) >= 2:
        names = list(body)
        regrouped["protocols"][key]["groups"] = {names[1]: body[names[1]], names[0]: body[names[0]], **{n: body[n] for n in names[2:]}}
        fires("order/group-order", "group order", g.check_recorded(regrouped, [])[0])

    dropped = copy_of(DECLARED)
    dropped["protocols"][key]["groups"][first_group]["dropped_terms"] = ["invented"]
    fires("field/dropped-terms", "dropped_terms", g.check_recorded(dropped, [])[0])

    flagged = copy_of(DECLARED)
    flag_group = next((n for n, v in flagged["protocols"][key]["groups"].items() if "enable_corruption" in v.get("flags", {})), None)
    if flag_group is not None:
        flags = flagged["protocols"][key]["groups"][flag_group]["flags"]
        flags["enable_corruption"] = not flags["enable_corruption"]
        fires("field/corruption-flag", "flags", g.check_recorded(flagged, [])[0])

    # --- coverage in both directions --------------------------------------------------
    missing_task = copy_of(DECLARED)
    missing_task["tasks"].pop(task_of(DECLARED, key))
    fires("coverage/golden-task-undeclared", "absent from the declaration", g.check_recorded(missing_task, [])[0])
    fabricated = copy_of(DECLARED)
    fabricated["tasks"]["Lizard-Invented-v99"] = {"protocol": key, "version": "v99", "line": "main"}
    fires("coverage/declared-task-unrecorded", "no golden records it", g.check_recorded(fabricated, [])[0])

    # --- scoping: a mid-edit sibling must not turn one task's problem into all of them --
    scoped = copy_of(DECLARED)
    scoped["tasks"].pop(task_of(DECLARED, key))
    other = next(t for t in DECLARED["tasks"] if t != task_of(DECLARED, key))
    problems, _ = g.check_recorded(scoped, [other])
    check("only/filters-other-tasks", problems == [], f"{problems[:3]}")
    problems, _ = g.check_recorded(scoped, [task_of(DECLARED, key)])
    fires("only/still-catches-in-scope", "absent from the declaration", problems)

    # --- a retirement is a legal state, not a fault ------------------------------------
    tasks = DECLARED["tasks"]
    one = sorted(tasks)[0]
    other = next(task for task in sorted(tasks) if task != one)
    registered = {task: {} for task in tasks}
    check(
        "coverage/complete-set-is-clean",
        g.coverage_problems(tasks, registered, set()) == [],
        f"{g.coverage_problems(tasks, registered, set())[:3]}",
    )
    extra = {**registered, "Lizard-NotDeclared-v1": {}}
    fires("coverage/registered-but-undeclared", "no protocol mapping", g.coverage_problems(tasks, extra, set()))
    fewer = {task: route for task, route in registered.items() if task != one}
    fires("coverage/declared-but-unregistered", "declared but not registered", g.coverage_problems(tasks, fewer, set()))
    check(
        "coverage/retired-line-is-history",
        g.coverage_problems(tasks, fewer, {tasks[one]["line"]}) == [],
        f"{g.coverage_problems(tasks, fewer, {tasks[one]['line']})[:3]}",
    )
    check(
        "coverage/only-scopes",
        g.coverage_problems(tasks, fewer, set(), [other]) == [],
        f"{g.coverage_problems(tasks, fewer, set(), [other])[:3]}",
    )

    # the reader itself, not an injected answer: the first retirement control patched the module
    # and still read the live file, because the path was bound as a default argument -- a unit
    # test that hands in its own set never touches the reader it is supposedly testing
    with tempfile.TemporaryDirectory() as tmp:
        line_of_one = tasks[one]["line"]
        lines_path = pathlib.Path(tmp) / "lines.json"
        lines_path.write_text(
            json.dumps({"format": 2, "lines": {line_of_one: {"status": "retired"}, "lizard/other": {"status": "active"}}}),
            encoding="utf-8",
        )
        check(
            "retirement/reader-reads-the-index",
            g.retired_lines(lines_path) == {line_of_one},
            f"{g.retired_lines(lines_path)}",
        )
        check(
            "retirement/reader-drives-coverage",
            g.coverage_problems(tasks, fewer, g.retired_lines(lines_path), [one]) == [],
            f"{g.coverage_problems(tasks, fewer, g.retired_lines(lines_path), [one])[:3]}",
        )

    # --- the exported deployment artifact must agree with the pin ----------------------
    with tempfile.TemporaryDirectory() as tmp:
        pin_path, out_path = pathlib.Path(tmp) / "pin.json", pathlib.Path(tmp) / "export.json"
        order = ["a", "b", "c"]
        digest = hashlib.sha256("\n".join(order).encode("utf-8")).hexdigest()
        pin_path.write_text(json.dumps({"assets": {"asset/x": {"joint_order": order}}}), encoding="utf-8")

        def exported(**overrides) -> pathlib.Path:
            body = {
                "meta": {"asset": "asset/x"},
                "joint_order_runtime": order,
                "joint_order_runtime_digest": digest,
                **overrides,
            }
            out_path.write_text(json.dumps(body), encoding="utf-8")
            return out_path

        check("export/clean", g.check_export_agreement(exported(), pin_path) == [], f"{g.check_export_agreement(exported(), pin_path)}")
        fires(
            "export/runtime-order-stale",
            "re-export after re-measuring",
            g.check_export_agreement(exported(joint_order_runtime=["a", "c", "b"]), pin_path),
        )
        fires(
            "export/digest-stale",
            "joint_order_runtime_digest",
            g.check_export_agreement(exported(joint_order_runtime_digest="0" * 64), pin_path),
        )
        fires(
            "export/no-asset",
            "meta.asset is missing",
            g.check_export_agreement(exported(meta={}), pin_path),
        )

    if PROBLEMS:
        print(f"OBS_PROTOCOL_GATE_FAILED ({len(PROBLEMS)})")
        return 1
    print("OBS_PROTOCOL_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
