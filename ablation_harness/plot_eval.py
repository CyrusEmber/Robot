# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Plot a campaign's eval results (eval.json under results/<protocol>[/<group>]) to PNGs.

Two figures, both read straight from the stored eval.json (no re-simulation):
  <prefix>trend.png     success / fall / recovery vs checkpoint iteration, nominal vs robust
  <prefix>terrains.png  per-terrain completion and fall heatmaps, one column per checkpoint

Fall here is the protocol's geometric definition (tilt or clearance, sustained),
NOT the training termination term -- the two measure different things.

Usage (no Isaac app needed):
    python ablation_harness\\plot_eval.py --protocol locomotion_eval_v1 --group v1 ^
        --out_dir rl_exp\\versions\\lizard\\v1\\plots --prefix v1_eval_
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_MODES = ("nominal", "robust")
_HEATMAPS = (("completion", "completion"), ("fall_rate", "fall rate"))


def _load_runs(scope: pathlib.Path) -> list[dict]:
    """One dict per eval.json: iteration, mode, global metrics, terrains."""
    runs = []
    for path in sorted(scope.glob("*/eval.json")):
        with open(path, encoding="utf-8") as f:
            j = json.load(f)
        match = re.search(r"model_(\d+)\.pt", str(j.get("checkpoint", "")))
        runs.append({
            "iteration": int(match.group(1)) if match else 0,
            "mode": j["mode"],
            "global": j["global"],
            "recovery": j.get("recovery", {}),
            "terrains": j.get("terrains", {}),
        })
    return sorted(runs, key=lambda r: (r["iteration"], r["mode"]))


def _value(run: dict, key: str):
    """recovery_* live in their own block, everything else in global."""
    return (run["recovery"] if key.startswith("recovery_") else run["global"]).get(key)


def _trend(runs: list[dict], out_dir: pathlib.Path, prefix: str) -> pathlib.Path | None:
    panels = [
        ("success_rate", "success rate", False),
        ("fall_rate", "fall rate (geometric)", False),
        ("recovery_time_mean_s", "recovery after push [s]", True),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), dpi=120)
    for ax, (key, title, robust_only) in zip(axes, panels):
        plotted = False
        for mode in _MODES:
            if robust_only and mode != "robust":
                continue
            pts = [(r["iteration"], _value(r, key)) for r in runs if r["mode"] == mode]
            pts = [(it, v) for it, v in pts if v is not None]
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", linewidth=1.2, markersize=4, label=mode)
                plotted = True
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("iteration", fontsize=8)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
        if not plotted:
            ax.text(0.5, 0.5, "no data", ha="center", va="center", fontsize=8, color="grey")
    fig.suptitle("eval vs checkpoint (protocol Locomotion-Eval-v1)", fontsize=10)
    fig.tight_layout()
    path = out_dir / f"{prefix}trend.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def _terrains(runs: list[dict], out_dir: pathlib.Path, prefix: str) -> pathlib.Path | None:
    names = list(dict.fromkeys(t for r in runs for t in r["terrains"]))
    if not names:
        return None
    columns = {(r["iteration"], r["mode"]): r["terrains"] for r in runs}
    iters = sorted({r["iteration"] for r in runs})
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), dpi=120)
    for (row, (key, label)) in enumerate(_HEATMAPS):
        for col, mode in enumerate(_MODES):
            ax = axes[row, col]
            grid = [[columns.get((it, mode), {}).get(name, {}).get(key) for it in iters] for name in names]
            if any(v is None for line in grid for v in line):
                ax.text(0.5, 0.5, f"{label} {mode}: incomplete grid", ha="center", va="center",
                        fontsize=8, color="grey")
                ax.axis("off")
                continue
            im = ax.imshow(grid, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_title(f"{label} [{mode}]", fontsize=9)
            ax.set_xticks(range(len(iters)), [str(it) for it in iters], fontsize=7, rotation=45)
            ax.set_yticks(range(len(names)), names, fontsize=7)
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("per-terrain metrics (rows = suite terrain, cols = checkpoint)", fontsize=10)
    fig.tight_layout()
    path = out_dir / f"{prefix}terrains.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main():
    parser = argparse.ArgumentParser(description="eval.json -> PNG plots.")
    parser.add_argument("--protocol", type=str, default="locomotion_eval_v1")
    parser.add_argument("--group", type=str, default=None, help="Campaign folder under results/<protocol>/.")
    parser.add_argument("--out_dir", type=str, required=True, help="Folder for the pngs.")
    parser.add_argument("--prefix", type=str, default="", help="File name prefix (e.g. v1_eval_).")
    args = parser.parse_args()

    results = pathlib.Path(__file__).absolute().parent / "results" / args.protocol
    scope = results / args.group if args.group else results
    runs = _load_runs(scope)
    if not runs:
        raise SystemExit(f"ERROR: no eval.json under {scope}")

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = [p for p in (_trend(runs, out_dir, args.prefix), _terrains(runs, out_dir, args.prefix)) if p]
    print(f"[PLOT_EVAL] {len(runs)} runs, {len(written)} png -> {out_dir}")
    for path in written:
        print(f"[PLOT_EVAL]   {path}")


if __name__ == "__main__":
    main()
