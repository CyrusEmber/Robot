# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Plot a training run's TensorBoard curves (from tb_scalars.csv) to PNGs.

Keeps the per-version record readable without a tensorboard session: one png per
question the recipe review asks -- did reward rise, did it die by falling, did
episodes get longer, is the terrain curriculum moving. Training-side fall counts
are the TERMINATION term (base_contact only, blind to lying-down); the harness
geometric fall rate is a different measurement, so never read one as the other.

``figure``/``series_to_figs`` are the shared builders: ablation_harness\\plot_eval.py
imports them to inline the same curves into its single-file HTML report (one source
for "which tags answer which recipe question", so the two views cannot drift).

Usage (from E:\\IsaacLab):
    python rl_exp\\tools\\trainlog\\dump_tb.py --log_dir <run> --out rl_exp\\versions\\lizard\\v1\\tb_scalars.csv
    python rl_exp\\tools\\trainlog\\plot_tb.py --csv rl_exp\\versions\\lizard\\v1\\tb_scalars.csv ^
        --out_dir rl_exp\\versions\\lizard\\v1\\plots --prefix v1_ --mark 2000,4000,6000,8000,10000,13999
"""

from __future__ import annotations

import argparse
import csv
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# (png suffix, title, [(tag, label), ...]) -- one figure per recipe question
FIGURES = [
    ("reward", "Train/mean_reward", [("Train/mean_reward", "mean_reward")]),
    ("termination", "Episode termination (training term, not harness fall)",
     [("Episode_Termination/base_contact", "base_contact"),
      ("Episode_Termination/time_out", "time_out")]),
    ("episode_length", "Train/mean_episode_length", [("Train/mean_episode_length", "mean_episode_length")]),
    ("progress", "Curriculum / success / velocity error",
     [("Curriculum/terrain_levels", "terrain_levels"),
      ("Metrics/success_rate", "train success_rate"),
      ("Metrics/base_velocity/error_vel_xy", "error_vel_xy")]),
]


def _load(csv_path: pathlib.Path) -> dict[str, tuple[list[int], list[float]]]:
    series: dict[str, tuple[list[int], list[float]]] = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            series.setdefault(row["tag"], ([], []))[0].append(int(float(row["iteration"])))
            series[row["tag"]][1].append(float(row["value"]))
    for xs, ys in series.values():
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        xs[:] = [xs[i] for i in order]
        ys[:] = [ys[i] for i in order]
    return series


def figure(title: str, pairs: list[tuple[str, tuple[list[int], list[float]]]],
           marks: list[int], dpi: int = 200):
    """One curve panel: pairs = [(label, (iterations, values))], marks = checkpoint vlines."""
    fig, ax = plt.subplots(figsize=(7, 4), dpi=dpi)
    for label, (xs, ys) in pairs:
        ax.plot(xs, ys, linewidth=1.2, label=label)
        ax.annotate(f"{ys[-1]:.3g}", (xs[-1], ys[-1]), fontsize=8, color="dimgrey",
                    xytext=(3, 0), textcoords="offset points")
    for it in marks:
        ax.axvline(it, color="grey", linestyle=":", linewidth=0.8)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("iteration", fontsize=9)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def series_to_figs(series: dict[str, tuple[list[int], list[float]]], marks: list[int],
                   dpi: int = 200) -> list[tuple[str, object]]:
    """FIGURES panels -> [(png suffix, Figure)]; panels with no matching tag are skipped."""
    figs = []
    for suffix, title, wanted in FIGURES:
        pairs = [(label, series[tag]) for tag, label in wanted if tag in series]
        if not pairs:
            print(f"[PLOT_TB] skip {suffix}: no tag among {[t for t, _ in wanted]}")
            continue
        figs.append((suffix, figure(title, pairs, marks, dpi)))
    return figs


def main():
    parser = argparse.ArgumentParser(description="tb_scalars.csv -> PNG curves.")
    parser.add_argument("--csv", type=str, required=True, help="CSV from dump_tb.py (iteration,tag,value).")
    parser.add_argument("--out_dir", type=str, required=True, help="Folder for the pngs.")
    parser.add_argument("--prefix", type=str, default="", help="File name prefix (e.g. v1_).")
    parser.add_argument("--mark", type=str, default="",
                        help="Comma-separated iterations to draw as vertical lines (evaluated checkpoints).")
    parser.add_argument("--dpi", type=int, default=200, help="PNG density (default 200 = zoomable).")
    args = parser.parse_args()

    series = _load(pathlib.Path(args.csv))
    marks = [int(m) for m in args.mark.split(",") if m.strip()]
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for suffix, fig in series_to_figs(series, marks, args.dpi):
        path = out_dir / f"{args.prefix}{suffix}.png"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)

    print(f"[PLOT_TB] {len(written)} png -> {out_dir}")
    for path in written:
        print(f"[PLOT_TB]   {path}")


if __name__ == "__main__":
    main()
