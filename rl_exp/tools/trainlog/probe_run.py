# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""One-shot health probe of a training run (reads tfevents only, no sim).

Resolves the run dir, prints progress against max_iterations (from the run's
params/agent.yaml), latest + windowed trend of core scalars, curriculum,
termination counts, loss/policy stats, iters/h + ETA, and warnings (NaN,
reward collapse, stale events, checkpoint lag). Replaces the ad-hoc
read_curriculum probe.

Usage (from the IsaacLab root):
    python rl_exp\\tools\\trainlog\\probe_run.py                  # most recently active run
    python rl_exp\\tools\\trainlog\\probe_run.py --exp v4         # latest run of exp matching "v4"
    python rl_exp\\tools\\trainlog\\probe_run.py --run logs/rsl_rl/lizard_rough_teacher_v3/2026-09-02_11-33-11
    python rl_exp\\tools\\trainlog\\probe_run.py --exp v3 --window 200 --tags Loss,Policy
"""

from __future__ import annotations

import argparse
import math
import re
import time
from pathlib import Path

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

GROUPS = {
    "CORE": ["Train/mean_reward", "Train/mean_episode_length", "Metrics/success_rate",
             "Metrics/base_velocity/error_vel_xy", "Metrics/base_velocity/error_vel_yaw",
             "Perf/total_fps"],
    "CURRICULUM": None,   # None = all tags with this prefix
    "LOSS": None,
    "TERMINATION": None,
    "REWARDS": None,
}
PREFIXES = {"CURRICULUM": "Curriculum/", "LOSS": ("Loss/", "Policy/"),
            "TERMINATION": "Episode_Termination/", "REWARDS": "Episode_Reward/",
            "CORE": None}


def resolve_run(logs_root: Path, exp: str | None, run: str | None) -> Path:
    """Pick the run dir: explicit --run, latest under exp matching --exp, or the globally newest event."""
    if run:
        p = Path(run)
        if not p.is_dir():
            raise SystemExit(f"ERROR: run dir not found: {p}")
        return p
    if not logs_root.is_dir():
        raise SystemExit(f"ERROR: no {logs_root} (run from the IsaacLab root, or pass --logs/--run)")
    runs = [d for e in sorted(logs_root.iterdir()) if e.is_dir() for d in sorted(e.iterdir()) if d.is_dir()]
    if exp:
        runs = [d for d in runs if exp in str(d.parent)]
    runs = [d for d in runs if list(d.glob("events.out.tfevents.*"))]
    if not runs:
        raise SystemExit(f"ERROR: no runs with tfevents under {logs_root} (filter exp={exp!r})")
    return max(runs, key=lambda d: max(f.stat().st_mtime for f in d.glob("events.out.tfevents.*")))


def load(run: Path) -> dict[str, list[tuple[int, float]]]:
    """tag -> [(step, value)] sorted by step, later samples winning on duplicate steps (resumes)."""
    acc = EventAccumulator(str(run), size_guidance={"scalars": 0})
    acc.Reload()
    out = {}
    for tag in acc.Tags().get("scalars", []):
        merged: dict[int, float] = {}
        for p in acc.Scalars(tag):
            merged[p.step] = p.value
        out[tag] = sorted(merged.items())
    return out


def max_iterations(run: Path) -> int | None:
    yaml = run / "params" / "agent.yaml"
    if yaml.is_file():
        m = re.search(r"^max_iterations:\s*(\d+)", yaml.read_text(encoding="utf-8"), re.M)
        if m:
            return int(m.group(1))
    return None


def fmt_row(tag: str, pts: list[tuple[int, float]], window: int) -> str:
    vals = [v for _, v in pts]
    last = vals[-1]
    w = vals[-window:]
    prev = vals[-2 * window:-window]
    w_mean = sum(w) / len(w)
    trend = ""
    if prev:
        p_mean = sum(prev) / len(prev)
        if abs(p_mean) > 1e-12:
            trend = f"  d{(w_mean - p_mean) / abs(p_mean) * +100:+6.1f}%"
        else:
            trend = f"  d{w_mean - p_mean:+12.4f}"
    return f"  {tag:<44} last {last:>10.4f}  win {w_mean:>10.4f}{trend}"


def main():
    ap = argparse.ArgumentParser(description="tfevents -> training health snapshot.")
    ap.add_argument("--logs", default="logs/rsl_rl", help="logs/rsl_rl root (default: cwd).")
    ap.add_argument("--exp", default=None, help="substring of the experiment dir, e.g. v4.")
    ap.add_argument("--run", default=None, help="explicit run dir (overrides --exp).")
    ap.add_argument("--window", type=int, default=100, help="trend window in samples (default 100).")
    ap.add_argument("--tags", default="", help="comma list: only show tags containing any of these substrings.")
    args = ap.parse_args()

    run = resolve_run(Path(args.logs), args.exp, args.run)
    scalars = load(run)
    if not scalars:
        raise SystemExit(f"ERROR: no scalar tags under {run}")
    filters = [s for s in args.tags.split(",") if s]

    iter_tag = "Train/mean_reward"
    iters = scalars.get(iter_tag, [])
    cur_iter = iters[-1][0] if iters else max((p[-1][0] for p in scalars.values()), default=0)
    total = max_iterations(run)
    ckpts = sorted(int(f.stem.split("_")[1]) for f in run.glob("model_*.pt"))
    newest_event = max(f.stat().st_mtime for f in run.glob("events.out.tfevents.*"))
    age_min = (time.time() - newest_event) / 60.0

    print(f"[PROBE] {run}")
    prog = f"iter {cur_iter}" + (f" / {total} ({cur_iter / total * 100:.1f}%)" if total else "")
    print(f"  {prog}  |  ckpt {ckpts[-1] if ckpts else '-'}  |  last event {age_min:.0f} min ago")

    # Train/mean_reward/time: x-axis is engine wall-clock seconds, y is the reward (rsl_rl convention)
    wt = scalars.get("Train/mean_reward/time", [])
    if len(wt) >= 2 and len(iters) >= 2 and wt[-1][0] > wt[0][0]:
        iters_per_h = (iters[-1][0] - iters[0][0]) / ((wt[-1][0] - wt[0][0]) / 3600.0)
        eta = f"  |  ETA {(total - cur_iter) / iters_per_h:.1f} h" if total and cur_iter < total else ""
        print(f"  {iters_per_h:.0f} iters/h{eta}")

    warnings = []
    for tag, pts in scalars.items():
        bad = [s for s, v in pts[-args.window:] if not math.isfinite(v)]
        if bad:
            warnings.append(f"NaN/inf in {tag} (steps {bad[:3]})")
    if len(iters) >= 2 * args.window:
        vals = [v for _, v in iters]
        w_mean = sum(vals[-args.window:]) / args.window
        p_mean = sum(vals[-2 * args.window:-args.window]) / args.window
        if p_mean > 0 and w_mean < 0.8 * p_mean:
            warnings.append(f"mean_reward dropped {w_mean:.2f} vs prev {p_mean:.2f} (-{(1 - w_mean / p_mean) * 100:.0f}%)")
    if ckpts and cur_iter - ckpts[-1] > 200:
        warnings.append(f"checkpoint lags events by {cur_iter - ckpts[-1]} iters (save gap or crash?)")
    if age_min > 30:
        warnings.append(f"no tfevents write for {age_min:.0f} min (run finished or hung?)")
    if total and cur_iter >= total:
        print("  training target reached")

    def show(tag: str) -> bool:
        if tag.endswith("/time"):  # wall-clock helper axes, consumed for iters/h above
            return False
        return not filters or any(f in tag for f in filters)

    shown = {t: p for t, p in scalars.items() if show(t)}
    for group, explicit in GROUPS.items():
        if explicit:
            tags = [t for t in explicit if t in shown]
            for t in tags:
                shown.pop(t)
        else:
            pre = PREFIXES[group]
            tags = [t for t in sorted(shown) if t.startswith(pre)]
            for t in tags:
                shown.pop(t)
        if not tags:
            continue
        print(f"  -- {group} " + "-" * (60 - len(group)))
        for t in tags:
            print(fmt_row(t, scalars[t], args.window))
    if shown:
        print("  -- OTHER " + "-" * 58)
        for t in sorted(shown):
            print(fmt_row(t, scalars[t], args.window))

    if warnings:
        print("  !! WARNINGS")
        for w in warnings:
            print(f"  !! {w}")
    else:
        print("  no warnings")


if __name__ == "__main__":
    main()
