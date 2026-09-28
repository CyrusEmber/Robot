# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Render a campaign's eval results (eval.json under results/<protocol>[/<group>]).

Two record shapes are read, and the report says which one it got:

* ``baseline-eval-2`` (what ``eval.py`` writes today): a verdict, one boolean per criterion, scalar
  metrics and per-env arrays, and no nominal/robust split or per-terrain grid -- so the report draws
  the gates plus a metrics table instead of the legacy figures.
* legacy ``locomotion_eval_v1`` records: iteration x mode x terrain, for the figures below.

Outputs, both straight off stored data (no re-simulation):
  PNG   (--out_dir):  <prefix>gates.png     per-gate verdict per record (baseline-eval-2)
                     <prefix>trend.png     success / fall / recovery vs checkpoint iteration,
                                                  nominal vs robust (legacy)
                     <prefix>terrains.png  per-terrain completion and fall heatmaps (legacy)
  HTML  (--report):   one self-contained <report_dir>/report.html -- training curves
                      (tb_scalars.csv in that dir) + the figures above + the record table,
                      all as inline SVG. Vector, so zooming is
                      free; no JS, no CDN, single file to share.

Training curves come from the version dir's tb_scalars.csv (dump_tb.py) and reuse
rl_exp\\tools\\trainlog\\plot_tb builders -- one source for "which tags answer which
recipe question". Evaluated checkpoint iterations become the vertical marks, so no
--mark to keep in sync.

Fall here is the protocol's geometric definition (tilt or clearance, sustained),
NOT the training termination term -- the two measure different things (the training
termination panel is shown next to the curves for exactly that reason).

Usage (no Isaac app needed):
    python ablation_harness\\plot_eval.py --protocol lizard2_flat_v2 --group v1 ^
        --report rl_exp\\versions\\lizard2\\main\\v1
    python ablation_harness\\plot_eval.py --protocol locomotion_eval_v1 --group v1 ^
        --out_dir rl_exp\\versions\\lizard\\v1\\plots --prefix v1_eval_
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
#: ``report_format`` of the records ``eval.py`` writes today. The legacy shape has no such field,
#: which is what lets one reader serve both without guessing.
_NEW_FORMAT = "baseline-eval-2"
#: Scalar metrics worth a table column, in reading order. A metric absent from every record is
#: dropped rather than shown empty: this list is a reading preference, not a schema.
_TABLE_METRICS = (
    "forward_mae_mps",
    "forward_displacement_m",
    "expected_displacement_m",
    "command_mps_mean",
    "tilt_max_deg",
    "gait_envs_request_swing_feet_mean",
    "gait_swing_feet_least",
    "non_foot_load_fraction_max",
    "tracking_unclaimed_frames",
)
# resolve() follows the E:\IsaacLab\ablation_harness junction into the repo that
# also holds rl_exp -- that is the one we need here (run_ablation wants the opposite).
_REPO_ROOT = pathlib.Path(__file__).absolute().resolve().parents[1]


def _new_run(record: dict) -> dict:
    """A ``baseline-eval-2`` record -> the fields this report needs.

    The label is the protocol's terrain (the old ``mode`` was nominal/robust, and this shape has no
    such split); the gate names are kept in declaration order so the figure rows read like the
    protocol does.
    """
    protocol = record.get("protocol") or {}
    code = record.get("code") or {}
    checkpoint = record.get("checkpoint")
    checkpoint_path = checkpoint.get("path", "") if isinstance(checkpoint, dict) else str(checkpoint or "")
    match = re.search(r"model_(\d+)\.pt", checkpoint_path)
    return {
        "format": _NEW_FORMAT,
        "iteration": int(match.group(1)) if match else 0,
        "mode": protocol.get("terrain", "?"),
        "protocol": protocol.get("name", "?"),
        "seed": record.get("seed", "?"),
        "verdict": record.get("verdict", "?"),
        "gates": record.get("gates", {}),
        "metrics": record.get("metrics", {}),
        "checkpoint_sha256": checkpoint.get("sha256") if isinstance(checkpoint, dict) else None,
        "rev_lizard": (code.get("repository") or {}).get("rev", "unknown"),
        "rev_isaaclab": (code.get("isaaclab") or {}).get("rev", "unknown"),
    }


def _legacy_run(record: dict) -> dict:
    """A legacy record -> the same keys, with the blocks its figures read."""
    match = re.search(r"model_(\d+)\.pt", str(record.get("checkpoint", "")))
    return {
        "format": "legacy",
        "iteration": int(match.group(1)) if match else 0,
        "mode": record["mode"],
        "global": record["global"],
        "recovery": record.get("recovery", {}),
        "terrains": record.get("terrains", {}),
        "rev_lizard": record.get("git_rev_lizard", "unknown"),
        "rev_isaaclab": record.get("git_rev_isaaclab", "unknown"),
        "seed": record.get("seed", "?"),
        "protocol": record.get("protocol", "?"),
    }


def _load_runs(scope: pathlib.Path) -> list[dict]:
    """One dict per eval.json, in either record shape (``format`` says which)."""
    runs = []
    for path in sorted(scope.glob("*/eval.json")):
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        runs.append(_new_run(record) if record.get("report_format") == _NEW_FORMAT else _legacy_run(record))
    return sorted(runs, key=lambda r: (r["iteration"], r["mode"]))


def _value(run: dict, key: str):
    """recovery_* live in their own block, everything else in global."""
    return (run["recovery"] if key.startswith("recovery_") else run["global"]).get(key)


def _gates(runs: list[dict], dpi: int):
    """Per-record criterion verdicts -- the figure the baseline-eval-2 shape can actually support."""
    gates = list(dict.fromkeys(g for r in runs for g in r.get("gates", {})))
    if not gates:
        return None
    grid = [[1.0 if r.get("gates", {}).get(gate) else 0.0 for r in runs] for gate in gates]
    fig, ax = plt.subplots(figsize=(max(4.0, 1.2 + 1.15 * len(runs)), 0.7 + 0.42 * len(gates)), dpi=dpi)
    ax.imshow(grid, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")
    for row in range(len(gates)):
        for col in range(len(runs)):
            ax.text(col, row, "pass" if grid[row][col] else "FAIL", ha="center", va="center", fontsize=7)
    ax.set_xticks(range(len(runs)), [f"{r['iteration']}\nseed {r['seed']}" for r in runs], fontsize=7)
    ax.set_yticks(range(len(gates)), gates, fontsize=8)
    ax.set_title("criteria per record (red cell = that gate failed)", fontsize=9)
    fig.tight_layout()
    return fig


def _record_rows(runs: list[dict]) -> list[dict]:
    """The table the baseline-eval-2 records carry: identity, verdict, and the scalar metrics."""
    metrics = [key for key in _TABLE_METRICS if any(key in r.get("metrics", {}) for r in runs)]
    return [
        {
            "iteration": r["iteration"],
            "seed": r["seed"],
            "verdict": r["verdict"],
            **{key: r["metrics"].get(key) for key in metrics},
        }
        for r in runs
    ]


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
    fig.suptitle(f"eval vs checkpoint (protocol {runs[0]['protocol']})", fontsize=10)
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
    # Which figures make sense is a property of the record shape, not of the arguments: the legacy
    # shape carried iteration x nominal/robust x terrain, today's carries a verdict and gates.
    new_format = all(r.get("format") == _NEW_FORMAT for r in runs)
    if new_format:
        gates_fig = _gates(runs, dpi)
        if gates_fig:
            sections.append(("Criteria per record", [gates_fig]))
    else:
        sections.append(("Eval vs checkpoint", [_trend(runs, dpi)]))
        terrain_fig = _terrains(runs, dpi)
        if terrain_fig:
            sections.append(("Per-terrain", [terrain_fig]))

    rows = []
    summary = scope / "summary.csv"
    if summary.exists():
        with open(summary, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    table = _table(rows) if rows else (_table(_record_rows(runs)) if new_format else _table([]))

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
    if new_format:
        parts.append("<p class='meta'>records are baseline-eval-2: each carries one verdict, per-criterion "
                     "booleans and scalar metrics. There is no nominal/robust split and no per-terrain "
                     "grid in this shape, so those two legacy figures are not drawn.</p>")
    for heading, figs in sections:
        parts.append(f"<h2>{html.escape(heading)}</h2>")
        parts.extend(_svg(fig) for fig in figs)
    parts.append("<h2>Summary table</h2>")
    parts.append(table)
    parts.append("</body></html>")

    out_path = report_dir / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(parts), encoding="utf-8")
    return out_path


def _self_test() -> int:
    """Both record shapes go through their own adapter, on one hand-written record each.

    The legacy branch cannot be exercised from disk any more -- nothing under ``results/`` carries
    the old shape -- so a change that breaks it would be silent until someone points this tool at an
    archive. These fixtures are the only place that still runs it.
    """
    legacy = {
        "checkpoint": "model_100.pt",
        "mode": "nominal",
        "global": {"success_rate": 0.9},
        "recovery": {"recovery_time_mean_s": 1.5},
        "terrains": {"t1": {"completion": 1.0}},
        "git_rev_lizard": "abc",
        "git_rev_isaaclab": "def",
        "seed": 1,
        "protocol": "locomotion_eval_v1",
    }
    fresh = {
        "report_format": _NEW_FORMAT,
        "protocol": {"name": "Lizard2-Flat-v2", "terrain": "plane"},
        "checkpoint": {"path": "x/model_13999.pt", "sha256": "sha256:0"},
        "seed": 123,
        "verdict": "pass",
        "gates": {"gait": True},
        "metrics": {"forward_mae_mps": 0.03},
        "code": {"repository": {"rev": "r1"}, "isaaclab": {"rev": "r2"}},
    }
    old, new = _legacy_run(legacy), _new_run(fresh)
    checks = [
        ("legacy format", old["format"], "legacy"),
        ("legacy iteration", old["iteration"], 100),
        ("legacy mode", old["mode"], "nominal"),
        ("legacy global", _value(old, "success_rate"), 0.9),
        ("legacy recovery", _value(old, "recovery_time_mean_s"), 1.5),
        ("legacy terrains", sorted(old["terrains"]), ["t1"]),
        ("new format", new["format"], _NEW_FORMAT),
        ("new iteration", new["iteration"], 13999),
        ("new protocol", new["protocol"], "Lizard2-Flat-v2"),
        ("new label", new["mode"], "plane"),
        ("new gates", new["gates"], {"gait": True}),
        ("new metrics", new["metrics"]["forward_mae_mps"], 0.03),
        ("new rev", new["rev_lizard"], "r1"),
        ("new table row", _record_rows([new])[0]["verdict"], "pass"),
    ]
    problems = [f"{name}: got {got!r}, want {want!r}" for name, got, want in checks if got != want]
    for problem in problems:
        print(f"  FAIL {problem}")
    print(f"PLOT_EVAL_SELF_TEST_{'FAILED' if problems else 'OK'} ({len(checks)} fixtures)")
    return 1 if problems else 0


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
    parser.add_argument("--self-test", action="store_true", help="run the record-shape fixtures instead")
    args_cli = parser.parse_args()
    if args_cli.self_test:
        return _self_test()
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
        if all(r.get("format") == _NEW_FORMAT for r in runs):
            figures = ((_gates(runs, args_cli.dpi), "gates"),)
        else:
            figures = ((_trend(runs, args_cli.dpi), "trend"), (_terrains(runs, args_cli.dpi), "terrains"))
        written = []
        for fig, name in figures:
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
    # the exit code is the only thing a caller sees: a failing --self-test must not look like a
    # successful report run (the app teardown swallows exit codes elsewhere in this tree).
    sys.exit(main())
