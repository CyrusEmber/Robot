# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Export TensorBoard scalars of a training run to CSV (per-version records).

Long format: iteration,tag,value -- one row per scalar sample. Feed the csv
into any notebook/sheet, or keep it in versions/<v>/ as the frozen record of
"what happened per iteration" (success_rate, rewards, curriculum levels...).

Usage (from E:\\IsaacLab):
    python rl_exp\\dump_tb.py --log_dir logs/rsl_rl/lizard_rough_teacher/<run> ^
        --out rl_exp\\versions\\v0\\tb_scalars.csv
    python rl_exp\\dump_tb.py --log_dir <run> --list_tags   # inspect first

Sampling (what the committed record holds): --max_points N keeps at most N
samples per tag at an adaptive stride, always keeping each tag's first and last
sample. A run logs ~15000 rows/tag (~52 B/row -> ~20 MB for 29 tags); the
committed versions/<v>/tb_scalars.csv is dumped with --max_points 150 (~200 KB)
and still shows every trend shape the version notes read off it. Full fidelity
stays machine-local as tb_scalars.full.csv (gitignored) -- the committed csv is
regenerable from it without TensorBoard:
    python rl_exp\\dump_tb.py --csv_in <full.csv> --out <sampled.csv> --max_points 150
"""

from __future__ import annotations

import argparse
import csv
import math
import pathlib


def _read_csv(path: pathlib.Path) -> list[dict]:
    """Read a rows file written by this script (iteration,tag,value)."""
    with open(path, encoding="utf-8") as f:
        return [{"iteration": int(float(r["iteration"])), "tag": r["tag"], "value": float(r["value"])}
                for r in csv.DictReader(f)]


def _sample(rows: list[dict], max_points: int) -> list[dict]:
    """Downsample per tag, keeping each tag's first and last sample.

    Adaptive stride instead of a fixed one: every tag in these runs is logged on
    the same 1:1 iteration grid, so a fixed stride is equivalent *today*, but the
    adaptive form cannot flatten a future sparser tag to a couple of points.
    Tags of equal length keep equal lengths (wall-time derivation needs it).
    """
    if max_points <= 0:
        return rows
    by_tag: dict[str, list[dict]] = {}
    for row in rows:
        by_tag.setdefault(row["tag"], []).append(row)
    kept: list[dict] = []
    for tag_rows in by_tag.values():
        stride = max(1, math.ceil(len(tag_rows) / max_points))
        keep = tag_rows[::stride]
        if (len(tag_rows) - 1) % stride:  # tail dropped by the stride -> append it
            keep = keep + [tag_rows[-1]]
        kept.extend(keep)
    return kept


def _write_csv(out_path: pathlib.Path, rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: (r["iteration"], r["tag"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "tag", "value"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="TensorBoard scalars -> CSV.")
    parser.add_argument("--log_dir", type=str, default=None, help="Training run dir containing tfevents files.")
    parser.add_argument("--csv_in", type=str, default=None,
                        help="Resample an existing rows csv instead of reading tfevents (needs no TensorBoard).")
    parser.add_argument("--out", type=str, default=None, help="Output csv path (default: <log_dir>/tb_scalars.csv).")
    parser.add_argument("--tag_filter", type=str, default="",
                        help="Substring filter on tags (empty = all scalars).")
    parser.add_argument("--max_points", type=int, default=0,
                        help="Keep at most N samples per tag (0 = all). First/last sample always kept.")
    parser.add_argument("--list_tags", action="store_true", help="Only list available scalar tags.")
    args = parser.parse_args()

    if bool(args.log_dir) == bool(args.csv_in):
        raise SystemExit("ERROR: pass exactly one of --log_dir / --csv_in")
    if not args.log_dir and not args.out:
        raise SystemExit("ERROR: --csv_in needs --out (never overwrite the full csv in place)")

    if args.csv_in:
        in_path = pathlib.Path(args.csv_in)
        if not in_path.exists():
            raise SystemExit(f"ERROR: rows csv not found: {in_path}")
        rows = _read_csv(in_path)
    else:
        log_dir = pathlib.Path(args.log_dir)
        if not log_dir.exists():
            raise SystemExit(f"ERROR: log dir not found: {log_dir}")
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

        accumulator = EventAccumulator(str(log_dir), size_guidance={"scalars": 0})  # 0 = load all
        accumulator.Reload()
        if not accumulator.Tags()["scalars"]:
            raise SystemExit(f"ERROR: no scalar tags under {log_dir}")
        rows = [{"iteration": point.step, "tag": tag, "value": point.value}
                for tag in accumulator.Tags()["scalars"] for point in accumulator.Scalars(tag)]

    if args.tag_filter:
        rows = [r for r in rows if args.tag_filter in r["tag"]]
    if not rows:
        raise SystemExit("ERROR: no scalars matched")
    if args.list_tags:
        for tag in sorted({r["tag"] for r in rows}):
            print(tag)
        return

    sampled = _sample(rows, args.max_points)
    out_path = pathlib.Path(args.out) if args.out else pathlib.Path(args.log_dir) / "tb_scalars.csv"
    _write_csv(out_path, sampled)
    tags = len({r["tag"] for r in sampled})
    print(f"[DUMP_TB] {len(sampled)} points ({len(rows)} before sampling), {tags} tags -> {out_path}")


if __name__ == "__main__":
    main()
