# -*- coding: utf-8 -*-
"""Negative control for check_cfg_lock.py: every drift it claims to catch must fire.

Runs against the real lock file and two real tasks (fast), then tampers copies of the
lock/current pair and requires a problem for each tamper. A gate whose failure modes
were never demonstrated is not a gate.

Beyond drift, this pins the three properties the lock format is required to hold:
growth is bounded by framework combinations (runs add nothing), the text diffs one
line per changed leaf and re-serializes byte-identically, and an update without a
stated reason is refused rather than silently re-baselining.
"""

import difflib
import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import check_cfg_lock as g  # noqa: E402

TASKS = ["Lizard-Rough-v14", "Lizard-Velocity-Flat-v0"]
PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _fixture() -> tuple[dict, dict, str]:
    with open(g.LOCK_PATH, encoding="utf-8") as f:
        lock = json.load(f)
    combo = g.combination()
    key = g.combination_key(combo)
    specs = g.registered_tasks()
    current = {task: g.build_entry(task, specs[task]) for task in TASKS}
    return lock, current, key


def _entries(lock: dict, key: str) -> dict:
    """The lock's entries for one combination, keyed by task id (as the code sees them)."""
    return {stored.split("|")[-1]: value for stored, value in lock["entries"].items() if stored.startswith(f"{key}|")}


def _fires(mutate_lock, mutate_current, tag: str, show_diff: bool = False, only: list[str] | None = None) -> bool:
    lock, current, key = _fixture()
    if mutate_lock is not None:
        mutate_lock(lock, _entries(lock, key), key)
    if mutate_current is not None:
        mutate_current(current)
    problems: list[str] = []
    g.verify(lock, current, problems, show_diff=show_diff, only=TASKS if only is None else only)
    print(f"  {'FIRES' if problems else 'SILENT'} {tag}" + (f" <- {problems[0]}" if problems else ""))
    return bool(problems)


def _rekey(lock: dict, old: str, new: str) -> None:
    """Move a whole baseline (block + its entries) to another combination key."""
    lock["baselines"][new] = lock["baselines"].pop(old)
    lock["entries"] = {
        (f"{new}|{stored.split('|', 1)[1]}" if stored.startswith(f"{old}|") else stored): value
        for stored, value in lock["entries"].items()
    }


def main() -> int:
    lock, current, key = _fixture()
    print(f"  combination: {key}")
    base_problems: list[str] = []
    g.verify(lock, current, base_problems, show_diff=False, only=TASKS)
    check("baseline/clean", not base_problems, f"{base_problems[:2]}")
    check(
        "baseline/entry-is-recipe-only",
        all(set(entry) == g._ENTRY_KEYS for entry in lock["entries"].values()),
        "an entry carries non-recipe fields",
    )
    check(
        "baseline/keys-carry-combination",
        all(stored.startswith(f"{key}|") for stored in lock["entries"]) and key in lock["baselines"],
        "entry keys do not name the baseline they belong to",
    )

    # --- drift -------------------------------------------------------------------
    check(
        "drift/digest",
        _fires(lambda l, e, k: e[TASKS[0]].__setitem__("digest", "0" * 64), None, "digest"),
    )
    check(
        "drift/hand-edited-lock",
        _fires(lambda l, e, k: e[TASKS[0]]["snapshot"]["env"].__setitem__("decimation", 999), None, "snapshot only"),
    )
    check(
        "drift/snapshot-leaf",
        _fires(
            lambda l, e, k: (
                e[TASKS[0]]["snapshot"]["env"].__setitem__("decimation", 999),
                e[TASKS[0]].__setitem__("digest", "0" * 64),
            ),
            None,
            "nested leaf",
            show_diff=True,
        ),
    )
    check("drift/version", _fires(lambda l, e, k: e[TASKS[0]].__setitem__("version", "v3"), None, "lock version"))
    check(
        "drift/task-id-vs-recipe",
        _fires(None, lambda c: c[TASKS[0]].__setitem__("version", "v3"), "id says v14, cfg loads v3"),
    )
    check(
        "drift/run-scoped-entry",
        _fires(lambda l, e, k: e[TASKS[0]].__setitem__("run_id", "2026-09-15_14-00-00_v14"), None, "per-run field"),
    )
    check(
        "drift/retired-entry",
        _fires(
            lambda l, e, k: l["entries"].__setitem__(g.entry_key(k, "Lizard-Rough-v99"), {"digest": "x"}),
            None,
            "bogus entry",
            only=["Lizard-Rough-v99"],
        ),
    )
    check(
        "drift/missing-entry",
        _fires(lambda l, e, k: l["entries"].pop(g.entry_key(k, TASKS[0])), None, "entry removed"),
    )
    check(
        "drift/no-baseline-for-combination",
        _fires(lambda l, e, k: _rekey(l, k, "isaaclab=deadbeef|rsl_rl=-|python=0"), None, "combination moved"),
    )
    check(
        "drift/orphan-entry",
        _fires(
            lambda l, e, k: l["entries"].__setitem__(f"isaaclab=deadbeef|{TASKS[0]}", l["entries"][g.entry_key(k, TASKS[0])]),
            None,
            "entry names a baseline the lock does not describe",
        ),
    )
    check(
        "drift/snapshot-format",
        _fires(lambda l, e, k: l["baselines"][k].__setitem__("cfg_snapshot_format", 0), None, "stale snapshot format"),
    )

    # --- lock file level ---------------------------------------------------------
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="cfg_lock_"))
    real_lock = g.LOCK_PATH
    try:
        broken = tmp / "cfg_lock.json"
        broken.write_text(json.dumps({**lock, "lock_format": 1}), encoding="utf-8")
        g.LOCK_PATH = broken
        _, error = g.load_lock()
        check("lock/format-refused", bool(error) and "format" in error, f"{error}")
        gone = tmp / "absent.json"
        g.LOCK_PATH = gone
        _, error = g.load_lock()
        check("lock/missing-reported", bool(error) and "missing" in error, f"{error}")

        # update refuses without a reason, and (importantly) does not touch the file
        write_target = tmp / "written.json"
        g.LOCK_PATH = write_target
        check("update/refused-without-reason", g.update(current, None) == 1, "update wrote without a reason")
        check("update/refused-wrote-nothing", not write_target.exists(), "a refused update still wrote the file")
        check("update/writes-with-reason", g.update(current, "test baseline") == 0 and write_target.is_file())
        written = json.loads(write_target.read_text(encoding="utf-8"))
        check(
            "update/one-block-per-combination",
            written["lock_format"] == g.LOCK_FORMAT
            and len(written["baselines"]) == 1
            and len(written["entries"]) == len(TASKS)
            and written["baselines"][g.combination_key(g.combination())]["reason"] == "test baseline",
            f"baselines={list(written['baselines'])}, entries={len(written['entries'])}",
        )
        check(
            "update/entries-are-keyed-task-ids",
            {stored.split("|")[-1] for stored in written["entries"]} == set(TASKS)
            and all(stored.startswith(g.combination_key(g.combination()) + "|") for stored in written["entries"]),
            f"{list(written['entries'])[:2]}",
        )
    finally:
        g.LOCK_PATH = real_lock
        shutil.rmtree(tmp, ignore_errors=True)

    # --- text format: stable and one line per changed leaf -----------------------
    text = json.dumps(lock, indent=1, ensure_ascii=False) + "\n"
    again = json.dumps(json.loads(text), indent=1, ensure_ascii=False) + "\n"
    check("text/roundtrip-byte-identical", again == text, "re-serializing the lock changed its bytes")

    edited = json.loads(text)
    stored_key = g.entry_key(key, TASKS[0])
    leaf = edited["entries"][stored_key]["snapshot"]["env"]["decimation"]
    edited["entries"][stored_key]["snapshot"]["env"]["decimation"] = leaf + 1
    edited_text = json.dumps(edited, indent=1, ensure_ascii=False) + "\n"
    diff = [line for line in difflib.unified_diff(text.splitlines(), edited_text.splitlines(), lineterm="") if line[:1] in "+-" and line[:3] not in ("+++", "---")]
    check("text/one-line-per-changed-leaf", len(diff) == 2, f"{len(diff)} changed lines: {diff[:4]}")

    rows: list = []
    g.walk_diff({"a": 1, "b": {"c": [1, 2]}}, {"a": 2, "b": {"c": [1, 2, 3]}, "d": 4}, "", rows)
    check("diff/paths", sorted(path for path, _, _ in rows) == ["a", "b.c[]", "d"], f"{rows}")
    limited: list = []
    g.walk_diff({"a": 1, "b": 2, "c": 3}, {"a": 9, "b": 9, "c": 9}, "", limited, 1)
    check("diff/limit-honoured", len(limited) <= 2, f"{len(limited)} rows with limit=1")

    for problem in PROBLEMS:
        print(f"  {problem}")
    print("CFG_LOCK_GATE_FALSIFIABLE" if not PROBLEMS else "CFG_LOCK_GATE_SILENT")
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    raise SystemExit(main())
