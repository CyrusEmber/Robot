# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Render a campaign's eval results (eval.json under results/<protocol>[/<group>]).

Two outputs, both straight off stored data (no re-simulation):
  PNG   (--out_dir):  <prefix>trend.png     success / fall / recovery vs checkpoint
                                                  iteration, nominal vs robust
                     <prefix>terrains.png  per-terrain completion and fall heatmaps
  HTML  (--report):   one self-contained <report_dir>/report.html -- training curves
                      (tb_scalars.csv in that dir) + the two eval figures + the
                      summary.csv table, all as inline SVG. Vector, so zooming is
                      free; no JS, no CDN, single file to share.

Training curves come from the version dir's tb_scalars.csv (dump_tb.py) and reuse
rl_exp\\tools\\trainlog\\plot_tb builders -- one source for "which tags answer which
recipe question". Evaluated checkpoint iterations become the vertical marks, so no
--mark to keep in sync.

Fall here is the protocol's geometric definition (tilt or clearance, sustained),
NOT the training termination term -- the two measure different things (the training
termination panel is shown next to the curves for exactly that reason).

Usage (no Isaac app needed):
    python ablation_harness\\plot_eval.py --protocol locomotion_eval_v1 --group v1 ^
        --out_dir rl_exp\\versions\\lizard\\v1\\plots --prefix v1_eval_
    python ablation_harness\\plot_eval.py --protocol locomotion_eval_v1 --group v1 ^
        --report rl_exp\\versions\\lizard\\v1
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import pathlib
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_MODES = ("nominal", "robust")
_HEATMAPS = (("completion", "completion"), ("fall_rate", "fall rate"))
# resolve() follows the E:\IsaacLab\ablation_harness junction into the repo that
# also holds rl_exp -- that is the one we need here (run_ablation wants the opposite).
_REPO_ROOT = pathlib.Path(__file__).absolute().resolve().parents[1]


def _load_runs(scope: pathlib.Path) -> list[dict]:
    """One dict per eval.json: iteration, mode, global metrics, terrains, git revs."""
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
            "rev_lizard": j.get("git_rev_lizard", "unknown"),
            "rev_isaaclab": j.get("git_rev_isaaclab", "unknown"),
            "seed": j.get("seed", "?"),
            "protocol": j.get("protocol", "?"),
        })
    return sorted(runs, key=lambda r: (r["iteration"], r["mode"]))


def _value(run: dict, key: str):
    """recovery_* live in their own block, everything else in global."""
    return (run["recovery"] if key.startswith("recovery_") else run["global"]).get(key)


def _trend(runs: list[dict], dpi: int):
    panels = [
        ("success_rate", "success rate", False),
        ("fall_rate", "fall rate (geometric)", False),
        ("recovery_time_mean_s", "recovery after push [s]", True),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), dpi=dpi)
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
    return fig


def _terrains(runs: list[dict], dpi: int):
    names = list(dict.fromkeys(t for r in runs for t in r["terrains"]))
    if not names:
        return None
    columns = {(r["iteration"], r["mode"]): r["terrains"] for r in runs}
    iters = sorted({r["iteration"] for r in runs})
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), dpi=dpi)
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
    return fig


def _train_figs(report_dir: pathlib.Path, marks: list[int], dpi: int):
    """Training curves from <report_dir>/tb_scalars.csv; [] when the csv is absent."""
    csv_path = report_dir / "tb_scalars.csv"
    if not csv_path.exists():
        return []
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from rl_exp.tools.trainlog import plot_tb

    return plot_tb.series_to_figs(plot_tb._load(csv_path), marks, dpi)


def _svg(fig) -> str:
    """Figure -> bare inline <svg> (matplotlib's xml prolog dropped)."""
    buf = io.StringIO()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    text = buf.getvalue()
    return text[text.index("<svg"):]


def _table(rows: list[dict]) -> str:
    if not rows:
        return "<p class='meta'>no summary.csv in this scope</p>"
    columns = list(rows[0].keys())
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in columns) + "</tr>"
        for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


_CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:24px auto;max-width:1280px;color:#111}
h1{font-size:19px}h2{font-size:14px;border-bottom:1px solid #ccc;padding-bottom:3px;margin:26px 0 8px}
p.meta{color:#555;font-size:12px;margin:2px 0}
svg{max-width:100%;height:auto;display:block;margin:6px 0}
table{border-collapse:collapse;font-size:11px}
th,td{border:1px solid #bbb;padding:2px 7px;text-align:right;white-space:nowrap}
th{background:#eee}td:first-child,th:first-child{text-align:left}
.warn{color:#b00;font-size:12px}
"""


def _write_html(runs: list[dict], scope: pathlib.Path, report_dir: pathlib.Path,
                out_name: str, dpi: int) -> pathlib.Path:
    marks = sorted({r["iteration"] for r in runs if r["iteration"] > 0})
    sections: list[tuple[str, list]] = []
    train = [fig for _suffix, fig in _train_figs(report_dir, marks, dpi)]
    if train:
        sections.append(("Training curves (tb_scalars.csv, dotted lines = evaluated checkpoints)", train))
    sections.append(("Eval vs checkpoint", [_trend(runs, dpi)]))
    terrain_fig = _terrains(runs, dpi)
    if terrain_fig:
        sections.append(("Per-terrain", [terrain_fig]))

    rows = []
    summary = scope / "summary.csv"
    if summary.exists():
        with open(summary, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    revs = sorted({(r["rev_lizard"], r["rev_isaaclab"]) for r in runs})
    title = f"{runs[0]['protocol']} report" + (f" / {scope.name}" if scope != scope.parent else "")
    parts = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<p class='meta'>{len(runs)} eval runs · checkpoints {', '.join(map(str, marks)) or '-'} "
        f"· seeds {', '.join(sorted({str(r['seed']) for r in runs}))}</p>",
        "<p class='meta'>git: lizard " + " / ".join(a for a, _ in revs)
        + " · isaaclab " + " / ".join(b for _, b in revs) + "</p>",
    ]
    if len(revs) > 1:
        parts.append("<p class='warn'>mixed git revs across runs -- rows are not directly comparable</p>")
    if not train:
        parts.append("<p class='warn'>no tb_scalars.csv in the report dir -- training curves skipped "
                     "(run dump_tb.py first)</p>")
    for heading, figs in sections:
        parts.append(f"<h2>{html.escape(heading)}</h2>")
        parts.extend(_svg(fig) for fig in figs)
    parts.append("<h2>Summary table</h2>")
    parts.append(_table(rows))
    parts.append("</body></html>")

    out_path = report_dir / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(parts), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="eval.json -> PNG plots and/or one HTML report.")
    parser.add_argument("--protocol", type=str, default="locomotion_eval_v1")
    parser.add_argument("--group", type=str, default=None, help="Campaign folder under results/<protocol>/.")
    parser.add_argument("--out_dir", type=str, default=None, help="Folder for the pngs (omit to skip PNGs).")
    parser.add_argument("--prefix", type=str, default="", help="File name prefix (e.g. v1_eval_).")
    parser.add_argument("--report", type=str, default=None,
                        help="Version dir (holds tb_scalars.csv) -> writes report.html there.")
    parser.add_argument("--report_name", type=str, default="report.html", help="File name inside --report.")
    parser.add_argument("--dpi", type=int, default=200, help="PNG density (default 200 = zoomable).")
    args_cli = parser.parse_args()
    if not args_cli.out_dir and not args_cli.report:
        parser.error("--out_dir and/or --report is required")

    results = pathlib.Path(__file__).absolute().parent / "results" / args_cli.protocol
    scope = results / args_cli.group if args_cli.group else results
    runs = _load_runs(scope)
    if not runs:
        raise SystemExit(f"ERROR: no eval.json under {scope}")

    if args_cli.out_dir:
        out_dir = pathlib.Path(args_cli.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for fig, name in ((_trend(runs, args_cli.dpi), "trend"), (_terrains(runs, args_cli.dpi), "terrains")):
            if fig is None:
                continue
            fig.savefig(out_dir / f"{args_cli.prefix}{name}.png")
            plt.close(fig)
            written.append(out_dir / f"{args_cli.prefix}{name}.png")
        print(f"[PLOT_EVAL] {len(runs)} runs, {len(written)} png -> {out_dir}")
        for path in written:
            print(f"[PLOT_EVAL]   {path}")

    if args_cli.report:
        path = _write_html(runs, scope, pathlib.Path(args_cli.report), args_cli.report_name, args_cli.dpi)
        size_kb = path.stat().st_size / 1024
        print(f"[PLOT_EVAL] report ({len(runs)} runs, {size_kb:.0f} KB) -> {path}")


if __name__ == "__main__":
    main()
