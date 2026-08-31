# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Ablation scheduler: spec yaml -> sequential train + eval jobs -> summary.

Each spec run is a (task, tag, seed, iterations, checkpoints, modes) tuple.
Training is skipped when the final checkpoint already exists; each eval is
skipped when its eval.json already exists -- so an interrupted sweep simply
re-runs and continues. Nothing here ever edits task source code: component
variants enter via registered task ids or hydra override strings.

Usage (from E:\\IsaacLab):
    python ablation_harness\\run_ablation.py --spec ablation_harness\\specs\\<name>.yaml
    python ablation_harness\\run_ablation.py --summarize --protocol locomotion_eval_v1
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import subprocess
import sys

_HARNESS_DIR = pathlib.Path(__file__).resolve().parent
_ISAAC_ROOT = _HARNESS_DIR.parent
_PYTHON = _ISAAC_ROOT / "env_isaaclab" / "Scripts" / "python.exe"


def _log_dir_for_tag(tag: str) -> pathlib.Path | None:
    """Newest training run directory named ``{timestamp}_{tag}`` (train.py naming).

    Note: tags must not be suffixes of each other ("base" vs "my_base") -- the
    suffix match cannot distinguish them.
    """
    candidates = [
        p for p in _ISAAC_ROOT.glob("logs/rsl_rl/*/*")
        if p.is_dir() and p.name.endswith(f"_{tag}")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _run_train(run: dict, args_cli) -> pathlib.Path | None:
    task = run["task"]
    tag = run["tag"]
    iters = int(run["max_iterations"])
    cmd = [
        str(_PYTHON), "scripts/reinforcement_learning/rsl_rl/train.py",
        "--task", task, "--seed", str(run["seed"]),
        "--max_iterations", str(iters), "--run_name", tag, "--headless",
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
    if log_dir is None or not (log_dir / f"model_{iters}.pt").exists():
        print(f"[ABLATION] ERROR: expected model_{iters}.pt not found under {log_dir}", flush=True)
        return None
    return log_dir


def _run_eval(run: dict, checkpoint: pathlib.Path, iteration: int, mode: str, args_cli) -> bool:
    task = run["task"]
    tag = run["tag"]
    protocol = run.get("protocol", args_cli.protocol)
    eval_tag = f"{tag}_it{iteration}"
    run_id = f"{task.replace('-v0', '')}_{eval_tag}_{mode}_seed{run.get('eval_seed', 123)}"
    out_json = _HARNESS_DIR / "results" / protocol / run_id / "eval.json"
    if out_json.exists():
        print(f"[ABLATION] eval exists, skip: {run_id}", flush=True)
        return True
    cmd = [
        str(_PYTHON), "ablation_harness/eval.py",
        "--task", task, "--checkpoint", str(checkpoint),
        "--protocol", protocol, "--mode", mode,
        "--seed", str(run.get("eval_seed", 123)), "--tag", eval_tag, "--headless",
    ] + (["--device", args_cli.device] if args_cli.device else [])
    print(f"[ABLATION] eval: {run_id}", flush=True)
    result = subprocess.run(cmd, cwd=str(_ISAAC_ROOT), check=False)
    return result.returncode == 0


def _sweep(args_cli) -> int:
    import yaml

    with open(args_cli.spec, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    failures = 0
    for run in spec["runs"]:
        tag = run["tag"]
        iters = int(run["max_iterations"])
        log_dir = _log_dir_for_tag(tag)
        if log_dir is None or not (log_dir / f"model_{iters}.pt").exists():
            log_dir = _run_train(run, args_cli)
            if log_dir is None:
                failures += 1
                continue
        for iteration in run.get("eval_checkpoints", [iters]):
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


def _summarize(args_cli) -> None:
    protocol = args_cli.protocol
    summary_path = _HARNESS_DIR / "results" / protocol / "summary.csv"
    if not summary_path.exists():
        print(f"[ABLATION] no results under results/{protocol}/")
        return
    with open(summary_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"[ABLATION] results/{protocol}/summary.csv is empty")
        return
    columns = [c for c in rows[0].keys() if c != "timestamp"]
    widths = {c: max(len(c), *(len(r.get(c, "")) for r in rows)) for c in columns}
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    divider = "-|-".join("-" * widths[c] for c in columns)
    print(header)
    print(divider)
    for r in sorted(rows, key=lambda r: (r.get("mode", ""), r.get("run_id", ""))):
        print(" | ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))


def main():
    parser = argparse.ArgumentParser(description="Locomotion ablation scheduler.")
    parser.add_argument("--spec", type=str, default=None, help="Sweep spec yaml (runs: [...]).")
    parser.add_argument("--summarize", action="store_true", help="Print the protocol summary table.")
    parser.add_argument("--protocol", type=str, default="locomotion_eval_v1")
    parser.add_argument("--device", type=str, default=None)
    args_cli = parser.parse_args()
    if args_cli.summarize:
        _summarize(args_cli)
        return
    if args_cli.spec is None:
        parser.error("--spec or --summarize is required")
    failures = _sweep(args_cli)
    _summarize(args_cli)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
