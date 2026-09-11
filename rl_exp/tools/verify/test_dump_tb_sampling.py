# -*- coding: utf-8 -*-
"""tb_scalars sampling offline test (stdlib only, no TensorBoard, no Isaac Sim).

Covers the --max_points contract that keeps the committed per-version record
small (versions/<v>/tb_scalars.csv) while full fidelity stays machine-local
(tb_scalars.full.csv): adaptive stride, first/last sample preserved, equal-length
tags staying equal-length (plot_tb._derive needs `Train/mean_reward` and
`Train/mean_reward/time` on the same grid), sparse tags left alone, pass-through
when sampling is off, and the CLI resample path (dump_tb.py --csv_in/--out).
"""

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from rl_exp.tools.trainlog import dump_tb  # noqa: E402

_REPO = Path(__file__).resolve().parents[3]
_MAX_POINTS = 150


def _rows(*tags: str, n: int = 15000) -> list[dict]:
    return [{"iteration": i, "tag": tag, "value": float(i)}
            for tag in tags for i in range(n)]


def _by_tag(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in rows:
        out.setdefault(row["tag"], []).append(row)
    return out


def _check_sampler(problems: list[str]) -> None:
    full = _rows("Train/mean_reward", "Train/mean_reward/time")

    if dump_tb._sample(full, 0) != full:
        problems.append("max_points=0 must pass rows through untouched")

    sampled = _by_tag(dump_tb._sample(full, _MAX_POINTS))
    if set(sampled) != {"Train/mean_reward", "Train/mean_reward/time"}:
        problems.append("sampling must keep every tag")
    for tag, rows in sampled.items():
        if len(rows) > _MAX_POINTS + 1:
            problems.append(f"{tag}: {len(rows)} rows exceeds max_points+1")
        if rows[0]["iteration"] != 0 or rows[0]["value"] != 0.0:
            problems.append(f"{tag}: first sample (iteration 0) was dropped")
        if rows[-1]["iteration"] != 14999 or rows[-1]["value"] != 14999.0:
            problems.append(f"{tag}: last sample (iteration 14999) was dropped")

    # plot_tb._derive silently skips wall time unless both tags stay the same length
    if len(sampled["Train/mean_reward"]) != len(sampled["Train/mean_reward/time"]):
        problems.append("equal-length tags must stay equal-length after sampling -> wall-time fig would vanish")

    # a tag logged sparsely (fewer rows than max_points) must survive intact
    sparse = _by_tag(dump_tb._sample(_rows("Perf/total_fps", n=7), _MAX_POINTS))
    if len(sparse["Perf/total_fps"]) != 7:
        problems.append("a tag sparser than max_points must not be sampled down")

    for tag, rows in _by_tag(dump_tb._sample(full, _MAX_POINTS)).items():
        if [r["iteration"] for r in rows] != sorted(r["iteration"] for r in rows):
            problems.append(f"{tag}: iteration order broken by sampling")


def _check_cli(problems: list[str], tmp: Path) -> None:
    full = tmp / "tb_scalars.full.csv"
    dump_tb._write_csv(full, _rows("Train/mean_reward", "Train/mean_reward/time"))
    out = tmp / "tb_scalars.csv"

    run = subprocess.run([sys.executable, "rl_exp/tools/trainlog/dump_tb.py", "--csv_in", str(full),
                          "--out", str(out), "--max_points", str(_MAX_POINTS)],
                         cwd=_REPO, capture_output=True, text=True)
    if run.returncode != 0:
        problems.append(f"CLI resample failed: {run.stderr.strip()}")
        return
    got = _by_tag(dump_tb._read_csv(out))
    if len(got.get("Train/mean_reward", [])) != _MAX_POINTS + 1:
        problems.append("CLI resample wrote the wrong number of rows")
    if full.stat().st_size == out.stat().st_size:
        problems.append("CLI resample must shrink the file, not copy it")

    # in-place resampling would destroy the only full copy -> must be refused
    run = subprocess.run([sys.executable, "rl_exp/tools/trainlog/dump_tb.py", "--csv_in", str(full)],
                         cwd=_REPO, capture_output=True, text=True)
    if run.returncode == 0:
        problems.append("--csv_in without --out must be refused")


def _check_committed(problems: list[str]) -> None:
    """The committed record must already be sampled, and still end where the run ended."""
    commit = _REPO / "rl_exp" / "versions" / "lizard" / "v1" / "tb_scalars.csv"
    if not commit.exists():
        return
    got = _by_tag(dump_tb._read_csv(commit))
    lengths = {tag: len(rows) for tag, rows in got.items()}
    if max(lengths.values()) > _MAX_POINTS + 1:
        problems.append(f"committed v1 csv is not sampled: {max(lengths.values())} rows for a tag")
    if len(set(lengths.values())) != 1:
        problems.append("committed v1 csv tags have ragged lengths -> wall-time fig would vanish")
    tail = {tag: rows[-1]["value"] for tag, rows in got.items() if tag.startswith("Train/mean_reward")}
    if abs(tail.get("Train/mean_reward", 0.0) - 7.12) > 0.02:  # v1/NOTES.md: mean_reward 14k = 7.12
        problems.append(f"committed v1 csv lost the run's final mean_reward: {tail}")

    # the silent failure this sampling could cause: uneven/lost tags -> no wall-time fig
    try:
        from rl_exp.tools.trainlog import plot_tb
    except ImportError:  # matplotlib absent -> this one check skipped, sampler checks above still ran
        return
    series = plot_tb._load(commit)
    if "Train/wall_time_h" not in series:
        problems.append("committed v1 csv no longer yields Train/wall_time_h -> wall-time fig would vanish")
    elif len(series["Train/wall_time_h"][0]) != len(series["Train/mean_reward"][0]):
        problems.append("committed v1 csv wall-time series is not on the mean_reward grid")


def main() -> int:
    problems: list[str] = []
    if "tensorboard" in sys.modules:
        problems.append("dump_tb must not import tensorboard at module level (plain python resamples the record)")

    _check_sampler(problems)
    with tempfile.TemporaryDirectory() as td:
        _check_cli(problems, Path(td))
    _check_committed(problems)

    for p in problems:
        print(f"  DRIFT: {p}")
    if problems:
        print(f"DUMP_TB_SAMPLING_DRIFT ({len(problems)})")
        return 1
    print("DUMP_TB_SAMPLING_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
