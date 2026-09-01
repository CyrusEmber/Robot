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
"""

from __future__ import annotations

import argparse
import csv
import pathlib

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


def main():
    parser = argparse.ArgumentParser(description="TensorBoard scalars -> CSV.")
    parser.add_argument("--log_dir", type=str, required=True, help="Training run dir containing tfevents files.")
    parser.add_argument("--out", type=str, default=None, help="Output csv path (default: <log_dir>/tb_scalars.csv).")
    parser.add_argument("--tag_filter", type=str, default="",
                        help="Substring filter on tags (empty = all scalars).")
    parser.add_argument("--list_tags", action="store_true", help="Only list available scalar tags.")
    args = parser.parse_args()

    log_dir = pathlib.Path(args.log_dir)
    if not log_dir.exists():
        raise SystemExit(f"ERROR: log dir not found: {log_dir}")

    accumulator = EventAccumulator(str(log_dir), size_guidance={"scalars": 0})  # 0 = load all
    accumulator.Reload()
    tags = accumulator.Tags()["scalars"]
    if not tags:
        raise SystemExit(f"ERROR: no scalar tags under {log_dir}")
    if args.tag_filter:
        tags = [t for t in tags if args.tag_filter in t]
    if args.list_tags:
        for t in tags:
            print(t)
        return

    out_path = pathlib.Path(args.out) if args.out else log_dir / "tb_scalars.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for tag in tags:
        for point in accumulator.Scalars(tag):
            rows.append({"iteration": point.step, "tag": tag, "value": point.value})
    rows.sort(key=lambda r: (r["iteration"], r["tag"]))
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "tag", "value"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[DUMP_TB] {len(rows)} points, {len(tags)} tags -> {out_path}")


if __name__ == "__main__":
    main()
