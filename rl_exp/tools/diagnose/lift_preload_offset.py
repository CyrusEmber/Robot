# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Next preload offset for the guided lift trial, from a recorded run.

new = old + (q_initial - mean q over the chosen sample slice), for joints with the given
name prefixes. Seed: a slice around the frame where support force reaches body weight
in an unbiased run. Later rounds: a late-settle slice of the biased run. This is a fixed
point iteration on measured posture, not a statics model; it may not converge.
"""

import argparse
import json
from pathlib import Path

import numpy as np


def next_offset(report, ik, start, stop, prefixes):
    meta, samples = report["metadata"], report["samples"][start:stop]
    if not samples:
        raise ValueError("empty sample slice")
    names, initial = meta["joints"], ik["samples"][0]["q_rad"]
    old = meta.get("offset") or {}
    unknown = set(old) - set(initial)
    if unknown:
        raise ValueError(f"offset names not controlled: {sorted(unknown)}")
    q = np.mean([s["q"] for s in samples], axis=0)
    return {n: old.get(n, 0.) + float(initial[n] - q[names.index(n)])
            for n in initial if n.startswith(tuple(prefixes))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True, help="first sample index (0-based)")
    parser.add_argument("--stop", type=int, required=True, help="end sample index (exclusive)")
    parser.add_argument("--prefix", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    ik = json.loads(Path(report["metadata"]["ik"]).read_text(encoding="utf-8"))
    result = next_offset(report, ik, args.start, args.stop, args.prefix)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print("PRELOAD_OFFSET", len(result), json.dumps({k: round(v, 4) for k, v in result.items()}))
