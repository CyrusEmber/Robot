# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Run checkpoint metrics and the labeled video matrix in separate simulator processes."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from ablation_harness.experiment_eval import experiment_files
from rl_exp.tools.runrecord.binding import sha256_file

_REPO = Path(__file__).resolve().parents[1]
PROTOCOLS = tuple(sorted(path.stem for path in Path(__file__).with_name("protocols").glob("*.yaml")))


def _run(command: list[str], output: Path, log_name: str) -> int:
    output.mkdir(parents=True, exist_ok=True)
    receipt = {"command": command, "cwd": str(_REPO), "started_at": datetime.now(timezone.utc).isoformat()}
    code = 1
    try:
        with (output / log_name).open("x", encoding="utf-8") as log:
            code = subprocess.run(command, cwd=_REPO, stdout=log, stderr=subprocess.STDOUT).returncode
    finally:
        receipt.update(ended_at=datetime.now(timezone.utc).isoformat(), exit_code=code)
        (output / "execution.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return code


def evaluate(checkpoint: Path, protocol: str, mode: str = "robust", *, exp: Path | None = None,
             seed: int = 123, device: str | None = None) -> int:
    """Collect metrics and video, returning nonzero if either child fails."""
    checkpoint = checkpoint.resolve()
    experiment_files(checkpoint, exp)
    checkpoint_sha = sha256_file(checkpoint)
    if checkpoint_sha is None:
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
    if protocol not in PROTOCOLS:
        raise ValueError(f"Unknown evaluation protocol: {protocol}")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output = checkpoint.parent / "evaluation" / f"{timestamp}_{uuid4().hex[:8]}"
    output.mkdir(parents=True)
    print(f"Evaluation directory: {output}", flush=True)
    metrics_dir, video_dir = output / "metrics", output / "video"
    common = ["--ckpt", str(checkpoint), "--checkpoint-sha256", checkpoint_sha,
              "--seed", str(seed), "--viz", "none"]
    if device is not None:
        common += ["--device", device]
    experiment = ["--exp", str(exp.resolve())] if exp is not None else []

    metrics_code = _run([sys.executable, str(_REPO / "ablation_harness/eval.py"), *common, *experiment,
                         "--protocol", protocol, "--mode", mode, "--output-dir", str(metrics_dir)],
                        metrics_dir, "eval.log")
    if metrics_code == 0 and (metrics_dir / "eval.json").is_file():
        report = json.loads((metrics_dir / "eval.json").read_text(encoding="utf-8"))
        print(json.dumps(report["global"], ensure_ascii=False, indent=2), flush=True)
        clearance = report.get("report_only", {}).get("fall_clearance")
        if clearance and clearance.get("missing_reason"):
            print(f"Fall rate: {clearance['missing_reason']}", flush=True)
    else:
        metrics_code = metrics_code or 1
        print(f"Evaluation failed or produced no report. See {metrics_dir / 'eval.log'}", file=sys.stderr)

    video_code = _run([sys.executable, str(_REPO / "ablation_harness/video_matrix.py"), *common,
                       *experiment, "--out_dir", str(video_dir)], video_dir, "video.log")
    matrix_path = video_dir / "matrix.json"
    if video_code == 0 and matrix_path.is_file():
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        clips = [Path(cell["clip"]) for cell in matrix["cells"]]
        grids = [Path(grid) for grid in matrix.get("grids", [])]
        if len(set(clips)) == 9 and len(grids) == 1 and all(file.is_file() for file in clips + grids):
            print(f"Video matrix: {matrix_path}", flush=True)
        else:
            video_code = 1
            print(f"Incomplete video matrix: {matrix_path}", file=sys.stderr)
    else:
        video_code = video_code or 1
        print(f"Recording failed or produced no matrix. See {video_dir / 'video.log'}", file=sys.stderr)
    return metrics_code or video_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", type=Path, required=True)
    parser.add_argument("--protocol", choices=PROTOCOLS, default="locomotion_eval_v3")
    parser.add_argument("--mode", choices=("robust", "nominal"), default="robust")
    parser.add_argument("--exp", type=Path)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--device")
    args = parser.parse_args()
    try:
        return evaluate(args.ckpt, args.protocol, args.mode, exp=args.exp, seed=args.seed, device=args.device)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
