# -*- coding: utf-8 -*-
"""Negative control for check_cfg_lock.py: every drift it claims to catch must fire.

Runs against the real lock file and two real tasks (fast), then tampers copies of
the lock/current pair and requires a problem for each tamper. A gate whose failure
modes were never demonstrated is not a gate.
"""

import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import check_cfg_lock as g  # noqa: E402

TASKS = ["Lizard-Rough-v14", "Lizard-Velocity-Flat-v0"]
PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _fixture() -> tuple[dict, dict]:
    with open(g.LOCK_PATH, encoding="utf-8") as f:
        lock = json.load(f)
    specs = g.registered_tasks()
    current = {task: g.build_entry(task, specs[task]) for task in TASKS}
    return lock, current


def _fires(mutate_lock, mutate_current, tag: str, show_diff: bool = False, only: list[str] | None = None) -> bool:
    lock, current = _fixture()
    if mutate_lock is not None:
        mutate_lock(lock)
    if mutate_current is not None:
        mutate_current(current)
    problems: list[str] = []
    g.verify(lock, current, problems, show_diff=show_diff, only=TASKS if only is None else only)
    print(f"  {'FIRES' if problems else 'SILENT'} {tag}" + (f" <- {problems[0]}" if problems else ""))
    return bool(problems)


def main() -> int:
    lock, current = _fixture()
    base_problems: list[str] = []
    g.verify(lock, current, base_problems, show_diff=False, only=TASKS)
    check("baseline/clean", not base_problems, f"{base_problems[:2]}")

    check("drift/digest", _fires(lambda l: l["entries"][TASKS[0]].__setitem__("digest", "0" * 64), None, "digest"))
    check(
        "drift/hand-edited-lock",
        _fires(
            lambda l: l["entries"][TASKS[0]]["snapshot"]["env"].__setitem__("decimation", 999),
            None,
            "snapshot edited, digest untouched",
        ),
    )
    check(
        "drift/snapshot-leaf",
        _fires(
            lambda l: (
                l["entries"][TASKS[0]]["snapshot"]["env"].__setitem__("decimation", 999),
                l["entries"][TASKS[0]].__setitem__("digest", "0" * 64),
            ),
            None,
            "nested leaf",
            show_diff=True,
        ),
    )
    check(
        "drift/version",
        _fires(lambda l: l["entries"][TASKS[0]].__setitem__("version", "v3"), None, "lock version"),
    )
    check(
        "drift/task-id-vs-recipe",
        _fires(
            None,
            lambda c: c[TASKS[0]].__setitem__("version", "v3"),
            "id says v14, cfg loads v3",
        ),
    )
    check(
        "drift/retired-entry",
        _fires(
            lambda l: l["entries"].__setitem__("Lizard-Rough-v99", {"digest": "x"}),
            None,
            "bogus entry",
            only=["Lizard-Rough-v99"],
        ),
    )
    check(
        "drift/missing-entry",
        _fires(lambda l: l["entries"].pop(TASKS[0]), None, "entry removed"),
    )
    check(
        "drift/lock-format",
        _fires(lambda l: l.__setitem__("cfg_snapshot_format", 0), None, "format mismatch"),
    )

    rows: list = []
    g.walk_diff({"a": 1, "b": {"c": [1, 2]}}, {"a": 2, "b": {"c": [1, 2, 3]}, "d": 4}, "", rows)
    paths = sorted(path for path, _, _ in rows)
    check("diff/paths", paths == ["a", "b.c[]", "d"], f"{paths}")
    limited: list = []
    g.walk_diff({"a": 1, "b": 2, "c": 3}, {"a": 9, "b": 9, "c": 9}, "", limited, 1)
    check("diff/limit-honoured", len(limited) <= 2, f"{len(limited)} rows collected with limit=1")

    for problem in PROBLEMS:
        print(f"  {problem}")
    print("CFG_LOCK_GATE_FALSIFIABLE" if not PROBLEMS else "CFG_LOCK_GATE_SILENT")
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    raise SystemExit(main())
