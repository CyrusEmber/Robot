# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Ablation scheduler: spec yaml -> sequential train + eval jobs -> summary.

Each spec run is a (task, tag, seed, iterations, checkpoints, modes) tuple.
Training is skipped when the run already reached its budget; each eval is
skipped when its eval.json already exists -- so an interrupted sweep simply
re-runs and continues. Nothing here ever edits task source code: component
variants enter via registered task ids or hydra override strings.

An iteration budget of N is the trainer's own 0..N-1, so a run of that budget
ends on model_{N-1}.pt; a run naming no checkpoints is scored at its last one.

Usage (from the project repo root; the only machine fact left to name is the
IsaacLab tree -- ``paths.yaml`` or ``RL_ISAAC_ROOT``, see paths.example.yaml):
    python ablation_harness\\run_ablation.py --spec ablation_harness\\specs\\<name>.yaml
    python ablation_harness\\run_ablation.py --summarize --protocol locomotion_eval_v3
    python ablation_harness\\run_ablation.py --by-terrain --group v1

Train/eval subprocesses run under the interpreter recorded in ``paths.yaml``
(``python:``); ``--python`` overrides it, and with no paths.yaml they inherit
this interpreter as before.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import re
import subprocess
import sys

import host_paths
import record  # sibling module: the record's condition vocabulary (ARCH_PLAN Step 3.2d)

_HARNESS_DIR = pathlib.Path(__file__).absolute().parent
# The IsaacLab tree used to be "_HARNESS_DIR.parent", which only held while the
# harness was reached through the E:\IsaacLab junction; invoked by absolute path
# from the project repo it returns the repo itself, and train/eval would be
# launched with the wrong cwd against an empty logs glob. host_paths owns the
# question now (paths.yaml / RL_ISAAC_ROOT / upward probe).
_ISAAC_ROOT = host_paths.isaac_root()


def _isaac_root() -> pathlib.Path:
    """IsaacLab tree, or a hard stop -- the scheduler has no usable fallback.

    ``--summarize``/``--by-terrain`` never call this: they read results, which
    live next to the harness, and stay answerable on a machine with no IsaacLab
    install at all.
    """
    if _ISAAC_ROOT is None:
        raise SystemExit(
            "IsaacLab tree not found: copy paths.example.yaml to paths.yaml (or set "
            "RL_ISAAC_ROOT) so training and eval get a cwd with scripts/ and logs/."
        )
    return _ISAAC_ROOT


def _log_dir_for_tag(tag: str) -> pathlib.Path | None:
    """Newest training run directory named ``{timestamp}_{tag}`` (train.py naming).

    Note: tags must not be suffixes of each other ("base" vs "my_base") -- the
    suffix match cannot distinguish them.
    """
    candidates = [
        p for p in _isaac_root().glob("logs/rsl_rl/*/*")
        if p.is_dir() and p.name.endswith(f"_{tag}")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


_CHECKPOINT_NAME = re.compile(r"^model_(\d+)\.pt$")


def _latest_checkpoint(log_dir: pathlib.Path) -> tuple[int, pathlib.Path] | None:
    """Highest-numbered ``model_<it>.pt`` under a run directory, or None.

    The index is the trainer's, not ours: rsl_rl's loop runs ``range(start, start + budget)`` and
    its closing save names the file after the last index it ran, so a fresh run of ``budget``
    iterations ends on ``budget - 1``. Asking for ``model_{budget}.pt`` never resolves, which is
    why this reads the directory instead of composing a name from the spec.
    """
    found = [(int(m.group(1)), p) for p in log_dir.glob("model_*.pt")
             if (m := _CHECKPOINT_NAME.match(p.name))]
    return max(found) if found else None


def _trained_to_budget(log_dir: pathlib.Path | None, budget: int) -> bool:
    """Whether ``budget`` iterations have been run in this directory already.

    The evidence is a checkpoint at or past the last of them -- a run interrupted halfway leaves a
    lower index and is not a finished one.
    """
    if log_dir is None:
        return False
    latest = _latest_checkpoint(log_dir)
    return latest is not None and latest[0] >= budget - 1


def _eval_checkpoints(run: dict, log_dir: pathlib.Path, budget: int) -> list[int]:
    """Iterations to score: those the spec names, else the run's last checkpoint.

    The default was ``[max_iterations]``, the one index a run of that budget never saves.
    """
    named = run.get("eval_checkpoints")
    if named:
        return [int(i) for i in named]
    latest = _latest_checkpoint(log_dir)
    return [latest[0] if latest is not None else budget - 1]


def _run_train(run: dict, args_cli) -> pathlib.Path | None:
    task = run["task"]
    tag = run["tag"]
    iters = int(run["max_iterations"])
    cmd = [
        args_cli.python, "scripts/reinforcement_learning/rsl_rl/train.py",
        "--task", task, "--seed", str(run["seed"]),
        "--max_iterations", str(iters), "--run_name", tag,
        # forced headless, and not by omitting the flag: an omitted --viz means "headless
        # unless the cfg declares a visualizer", which makes this sweep depend on a tree
        # we do not own. '--viz none' is the deprecated '--headless' flag's replacement.
        "--viz", "none",
    ] + [str(o) for o in run.get("overrides", [])]
    if args_cli.device:
        cmd += ["--device", args_cli.device]
    print(f"[ABLATION] train: {' '.join(cmd)}", flush=True)
    try:
        subprocess.run(cmd, cwd=str(_ISAAC_ROOT), check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[ABLATION] train failed (exit {exc.returncode}): {tag}", flush=True)
        return None
    log_dir = _log_dir_for_tag(tag)
    if not _trained_to_budget(log_dir, iters):
        print(f"[ABLATION] ERROR: no checkpoint at or past iteration {iters - 1} under {log_dir} "
              f"-- a run of {iters} iterations saves model_{iters - 1}.pt last", flush=True)
        return None
    return log_dir


def _run_eval(run: dict, checkpoint: pathlib.Path, iteration: int, mode: str, args_cli) -> bool:
    task = run["task"]
    tag = run["tag"]
    protocol = run.get("protocol", args_cli.protocol)
    group = run.get("group")
    eval_tag = f"{tag}_it{iteration}"
    run_id = f"{task.replace('-v0', '')}_{eval_tag}_{mode}_seed{run.get('eval_seed', 123)}"
    out_json = _HARNESS_DIR / "results" / protocol / (group or "") / run_id / "eval.json"
    if out_json.exists():
        print(f"[ABLATION] eval exists, skip: {run_id}", flush=True)
        return True
    # by absolute path, not "ablation_harness/eval.py": the subprocess runs with cwd=IsaacLab,
    # where the harness was only reachable through the retired E:\IsaacLab junction. eval.py
    # locates its own results root, so no other part of the command depends on cwd.
    cmd = [
        args_cli.python, str(_HARNESS_DIR / "eval.py"),
        "--task", task, "--checkpoint", str(checkpoint),
        "--protocol", protocol, "--mode", mode,
        "--seed", str(run.get("eval_seed", 123)), "--tag", eval_tag,
        # same reason as the train half: forced headless, not "headless unless the cfg says otherwise"
        "--viz", "none",
    ] + (["--group", group] if group else []) + (
        ["--device", args_cli.device] if args_cli.device else [])
    print(f"[ABLATION] eval: {run_id}", flush=True)
    result = subprocess.run(cmd, cwd=str(_ISAAC_ROOT), check=False)
    if result.returncode == 0 and not out_json.is_file():
        print(f"[ABLATION] ERROR: eval exited successfully but did not write {out_json}", flush=True)
        return False
    return result.returncode == 0


def _sweep(args_cli) -> int:
    import yaml

    with open(args_cli.spec, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    failures = 0
    for run in spec["runs"]:
        run.setdefault("group", spec.get("group"))
        tag = run["tag"]
        iters = int(run["max_iterations"])
        log_dir = _log_dir_for_tag(tag)
        if not _trained_to_budget(log_dir, iters):
            log_dir = _run_train(run, args_cli)
            if log_dir is None:
                failures += 1
                continue
        for iteration in _eval_checkpoints(run, log_dir, iters):
            checkpoint = log_dir / f"model_{iteration}.pt"
            if not checkpoint.exists():
                print(f"[ABLATION] ERROR: checkpoint missing {checkpoint}", flush=True)
                failures += 1
                continue
            for mode in run.get("eval_modes", ["nominal", "robust"]):
                if not _run_eval(run, checkpoint, iteration, mode, args_cli):
                    failures += 1
    print(f"[ABLATION] sweep done, failures={failures}", flush=True)
    return failures


def _summary_paths(protocol_dir: pathlib.Path, group: str | None) -> list[pathlib.Path]:
    """Group filter narrows to one campaign; otherwise the protocol rollup = root + groups."""
    if group:
        return [protocol_dir / group / "summary.csv"]
    paths = [protocol_dir / "summary.csv", *sorted(protocol_dir.glob("*/summary.csv")),
             *[p.parent / "summary.csv" for p in sorted(protocol_dir.glob("*/.summary-write.lock"))]]
    return list(dict.fromkeys(paths))


def _condition_report(summary_path: pathlib.Path, rows: list[dict]) -> dict:
    """Do the rows beside this summary share their conditions? Reads the records, not the table.

    The check belongs at the table and not only in ``record.compare``: the summary is what people
    read *instead of* the records, so it is exactly where a row whose ground, protocol, judge or
    assets moved would otherwise sit next to its neighbours as if it were comparable. A run dir
    whose record is absent or unreadable is reported too -- dropping it silently would publish a
    population nobody can reconstruct.
    """
    records, no_record = [], []
    for row in rows:
        run_id = row.get("run_id") or "?"
        path = summary_path.parent / run_id / "record.json"
        if not path.is_file():
            no_record.append(run_id)
            continue
        try:
            records.append(record.load(path))
        except (OSError, json.JSONDecodeError):
            no_record.append(run_id)
    return {**record.table_conflicts(records), "no_record": no_record}


#: The one group name that is allowed to hold rows nobody scored. Everything else is a scores
#: table, and this is what turns that convention into a mechanism: ``--group`` decides where a row
#: lands, never what it is (HARNESS 挂账 #5).
_SMOKE_GROUP = "smoke"


def _identity_report(summary_path: pathlib.Path, rows: list[dict]) -> tuple[list[tuple[str, str]], list[str]]:
    """Rows in a scores table that were not measured by a policy: refusals, then uncertifiable ones.

    The table does not carry the policy identity, so it is read from each row's own ``record.json``
    -- the same place the condition check reads. Two things it must not do:

    * treat a diagnostic row as a reading: a zero-action rollout written into a scores group sits in
      the table beside real numbers, and the v3 smoke column is exactly the case where that reads as
      "v3 performance" (HARNESS.md says that column has no information on this run);
    * refuse a row written before ``policy.kind`` existed: that would make every historical table
      unreadable instead of safer, so those are reported as uncertified. A row with no usable record
      at all is already refused by :func:`_condition_report`.
    """
    if summary_path.parent.name == _SMOKE_GROUP:
        return [], []
    refused, uncertified = [], []
    for row in rows:
        run_id = row.get("run_id") or "?"
        path = summary_path.parent / run_id / "record.json"
        if not path.is_file():
            continue
        try:
            kind = ((record.load(path) or {}).get("policy") or {}).get("kind")
        except (OSError, json.JSONDecodeError):
            continue
        if kind is None:
            uncertified.append(run_id)
        elif kind != "checkpoint":
            refused.append((run_id, str(kind)))
    return refused, uncertified


def _summarize(args_cli) -> int:
    """Print a snapshot while excluding cooperating writers in this protocol."""
    protocol_dir = _HARNESS_DIR / "results" / args_cli.protocol
    if not protocol_dir.is_dir():
        print(f"[ABLATION] no results under {protocol_dir}")
        return 0
    lock = protocol_dir / ".summary-write.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        print(f"[ABLATION] {lock}: write in progress or stale lock -- cannot certify")
        return 1
    try:
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8")
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        with handle:
            handle.write(f"reader pid={os.getpid()}\n")
        return _summarize_locked(args_cli)
    finally:
        lock.unlink()


def _summarize_locked(args_cli) -> int:
    protocol_dir = _HARNESS_DIR / "results" / args_cli.protocol
    rows_by_path: dict[pathlib.Path, list[dict]] = {}
    problems = 0
    lock_paths = set()
    for path in _summary_paths(protocol_dir, args_cli.group):
        lock = path.parent / ".summary-write.lock"
        lock_paths.add(lock)
        if lock != protocol_dir / ".summary-write.lock" and lock.exists():
            problems += 1
            print(f"[ABLATION] {lock}: write in progress or stale lock -- cannot certify")
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f, strict=True)
                fields = reader.fieldnames
                if not fields or "run_id" not in fields or len(fields) != len(set(fields)) or any(not f for f in fields):
                    raise ValueError("missing or duplicate column headers")
                rows = list(reader)
                if any(None in row or any(value is None for value in row.values()) or not row["run_id"]
                       for row in rows):
                    raise ValueError("invalid row width or empty run_id")
                if (len({row["run_id"] for row in rows}) != len(rows) or
                        any(row["run_id"] in (".", "..") or "/" in row["run_id"] or "\\" in row["run_id"]
                            or ":" in row["run_id"] for row in rows)):
                    raise ValueError("duplicate or invalid run_id")
                rows_by_path[path] = rows
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            problems += 1
            print(f"[ABLATION] {path}: invalid summary.csv: {exc}")
    entries = [(path, row) for path, group_rows in rows_by_path.items() for row in group_rows]
    if not entries:
        print(f"[ABLATION] no results under {protocol_dir}")
        return problems
    columns = list(dict.fromkeys(c for _, row in entries for c in row if c != "timestamp"))
    widths = {c: max(len(c), *(len(row.get(c, "")) for _, row in entries)) for c in columns}
    show_source = len(rows_by_path) > 1
    source_width = max(len("source"), *(len(str(path.parent.relative_to(protocol_dir))) for path, _ in entries))
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    divider = "-|-".join("-" * widths[c] for c in columns)
    print(("source".ljust(source_width) + " | " if show_source else "") + header)
    print(("-" * source_width + "-|-" if show_source else "") + divider)
    for path, row in sorted(entries, key=lambda item: (item[1].get("mode", ""), item[1].get("run_id", ""))):
        source = str(path.parent.relative_to(protocol_dir))
        print((source.ljust(source_width) + " | " if show_source else "") +
              " | ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))
    records = []
    snapshots = {}
    for path, row in entries:
        run_id = row.get("run_id") or "?"
        record_path = path.parent / run_id / "record.json"
        if record_path not in snapshots:
            try:
                snapshots[record_path] = record.load(record_path)
            except (OSError, UnicodeError, json.JSONDecodeError):
                snapshots[record_path] = None
        rec = snapshots[record_path]
        if rec is None:
            problems += 1
            print(f"[ABLATION] {record_path}: no readable record.json -- it cannot be certified")
            continue
        state = record.read_state(rec)
        if state["state"] != "complete":
            problems += 1
            print(f"[ABLATION] {record_path}: {state['state']}: {state['note'] or state['missing']} "
                  "-- it cannot be certified")
            continue
        for field in ("eval_protocol.digest", "suite.name", "suite.digest", "suite.geometry_digest",
                      "obs_protocol.identity", "obs_protocol.digest", "judge.id", "assets.declared_digest"):
            value = record.get(rec, field)
            if value is not record._MISSING and (not isinstance(value, str) or not value):
                problems += 1
                print(f"[ABLATION] {record_path}: invalid {field} -- cannot certify")
        for field in ("suite.num_rows", "suite.num_cols", "suite.envs_per_terrain"):
            value = record.get(rec, field)
            if value is not record._MISSING and value != record.UNKNOWN and (type(value) is not int or value <= 0):
                problems += 1
                print(f"[ABLATION] {record_path}: invalid {field} -- cannot certify")
        terrains = record.get(rec, "suite.terrains")
        if (terrains is not record._MISSING and terrains != record.UNKNOWN
                and (not isinstance(terrains, list) or any(not isinstance(name, str) or not name for name in terrains))):
            problems += 1
            print(f"[ABLATION] {record_path}: invalid suite.terrains -- cannot certify")
        if rec["run"].get("run_id") != run_id:
            problems += 1
            print(f"[ABLATION] {record_path}: record run_id differs from row -- cannot certify")
        if "variant" in row and row["variant"] != (rec["run"].get("variant") or ""):
            problems += 1
            print(f"[ABLATION] {path}: {run_id}: variant differs from {record_path} -- cannot certify")
        row_id = row.get("persist_id") or ""
        record_id = (rec.get("run") or {}).get("persist_id") or ""
        if row_id != record_id:
            problems += 1
            print(f"[ABLATION] {path}: {run_id}: persist_id differs from {record_path} -- cannot certify")
            continue
        if not row_id:
            problems += 1
            print(f"[ABLATION] {path}: {run_id}: generation unverified (legacy row and record)")
        if path.parent.name != _SMOKE_GROUP:
            kind = (rec.get("policy") or {}).get("kind")
            if kind is None:
                print(f"[ABLATION] {record_path}: no policy.kind -- identity uncertified "
                      "(written before the field existed), not refused")
            elif kind != "checkpoint":
                problems += 1
                print(f"[ABLATION] {record_path}: policy.kind={kind!r}, not a checkpoint: "
                      f"a diagnostic row in a scores table; use --group {_SMOKE_GROUP}")
        records.append((record_path, rec))
    for index, (left_path, left) in enumerate(records):
        for right_path, right in records[index + 1:]:
            result = record.conditions_conflict(left, right, a_path=left_path, b_path=right_path)
            moved = result["conflicts"]
            if not moved and not result["unproven"]:
                continue
            if (any("declared_as" not in values for values in moved.values()) or
                    any(name in record.CONDITION_IDENTITIES and
                        (record.get(left, name) is record._MISSING or record.get(right, name) is record._MISSING)
                        for name in result["unproven"])):
                problems += 1
            print(f"[ABLATION] {left_path} vs {right_path}:")
            for name, values in sorted(moved.items()):
                tail = f" (declared as {values['declared_as']})" if "declared_as" in values else ""
                print(f"    {name}: {values['a']} -> {values['b']}{tail}")
            if result["unproven"]:
                print(f"    unproven: {', '.join(result['unproven'])}")
    for lock in lock_paths:
        if lock != protocol_dir / ".summary-write.lock" and lock.exists():
            problems += 1
            print(f"[ABLATION] {lock}: write in progress or stale lock -- cannot certify")
    return problems


_TERRAIN_COLUMNS = ["run_id", "protocol", "task", "mode", "seed", "iteration",
                    "terrain", "completion", "fall_rate", "success_rate", "source"]


def _collect_terrain_rows(protocol_dir: pathlib.Path, group: str | None) -> list[dict]:
    """Per-terrain rows read back from eval.json (the stored truth), for one group or all."""
    dirs = [protocol_dir / group] if group else [
        protocol_dir, *sorted(p for p in protocol_dir.iterdir() if p.is_dir())
    ]
    rows: list[dict] = []
    for folder in dirs:
        for json_path in sorted(folder.glob("*/eval.json")):
            with open(json_path, encoding="utf-8") as f:
                j = json.load(f)
            match = re.search(r"model_(\d+)\.pt", str(j.get("checkpoint", "")))
            for name, terrain in j.get("terrains", {}).items():
                rows.append({
                    "run_id": json_path.parent.name, "_source": str(json_path),
                    "source": json_path.relative_to(protocol_dir).as_posix(),
                    "protocol": j["protocol"], "task": j["task"],
                    "mode": j["mode"], "seed": j["seed"],
                    "iteration": int(match.group(1)) if match else -1, "terrain": name,
                    "completion": terrain["completion"], "fall_rate": terrain["fall_rate"],
                    "success_rate": terrain["success_rate"],
                })
    return rows


def _terrain_pivot(rows: list[dict], metric: str) -> None:
    """terrain x run table; refuse columns that combine distinct sources."""
    sources = {}
    seen = set()
    for row in rows:
        key = (row["iteration"], row["mode"])
        source = row.get("_source", row["run_id"])
        cell = (key, row["terrain"])
        if (key in sources and sources[key] != source) or cell in seen:
            raise ValueError(f"terrain pivot collision {key}: {sources.get(key)} vs {source}")
        sources[key] = source
        seen.add(cell)
    runs = sorted(sources)
    cells = {(r["iteration"], r["mode"], r["terrain"]): r[metric] for r in rows}
    labels = [("smoke" if it < 0 else str(it)) + "/" + mode for it, mode in runs]
    width = max(11, *(len(x) for x in labels)) + 1
    print(f"\n[terrain x run] {metric}")
    print("terrain".ljust(13) + "".join(x.rjust(width) for x in labels))
    for terrain in dict.fromkeys(r["terrain"] for r in rows):
        print(terrain.ljust(13) + "".join(
            f"{cells[(it, mode, terrain)]:.2f}".rjust(width) if (it, mode, terrain) in cells
            else "-".rjust(width)
            for it, mode in runs))


def _by_terrain(args_cli) -> int:
    protocol_dir = _HARNESS_DIR / "results" / args_cli.protocol
    scope = protocol_dir / args_cli.group if args_cli.group else protocol_dir
    rows = _collect_terrain_rows(protocol_dir, args_cli.group)
    if not rows:
        print(f"[ABLATION] no eval.json under {scope}")
        return 0
    out_csv = scope / "terrains.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_TERRAIN_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[ABLATION] wrote {out_csv} ({len(rows)} rows)")
    try:
        for metric in ("completion", "fall_rate", "success_rate"):
            _terrain_pivot(rows, metric)
    except ValueError as exc:
        print(f"[ABLATION] {exc}; pivot not printed")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="Locomotion ablation scheduler.")
    parser.add_argument("--spec", type=str, default=None, help="Sweep spec yaml (runs: [...]).")
    parser.add_argument("--summarize", action="store_true", help="Print the protocol summary table.")
    parser.add_argument("--by-terrain", action="store_true",
                        help="Write terrains.csv (run x terrain, long) and print terrain x run pivots.")
    parser.add_argument("--protocol", type=str, default="locomotion_eval_v3")
    parser.add_argument("--group", type=str, default=None,
                        help="Restrict --summarize/--by-terrain to one campaign folder under the protocol.")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument(
        "--python", type=str, default=None,
        help="Python executable for train/eval subprocesses (default: paths.yaml "
             "'python:', else this interpreter).",
    )
    args_cli = parser.parse_args()
    args_cli.python = args_cli.python or host_paths.venv_python(_ISAAC_ROOT) or sys.executable
    if args_cli.summarize:
        sys.exit(_summarize(args_cli))
    if args_cli.by_terrain:
        sys.exit(_by_terrain(args_cli))
    if args_cli.spec is None:
        parser.error("--spec, --summarize or --by-terrain is required")
    failures = _sweep(args_cli) + _summarize(args_cli)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
