# -*- coding: utf-8 -*-
"""Framework pin check: does this IsaacLab tree still provide what we rely on?

The lizard stack leans on several IsaacLab INTERNALS (not public API). Each one
is a silent breakage waiting for an upstream refactor. This script greps the
IsaacLab SOURCE TREE (plain python, no kit/app needed) for the exact symbols
we depend on, and compares the tree's git commit against the pinned SHA that
the whole stack was last verified against.

Pinned IsaacLab: 28a37cecdd433c22d9eabd6a5954add9f13a8951 (tag perf-2026-06-24)

Usage: python rl_exp\\tools\\verify\\framework_pin_check.py [--isaac-root PATH] [--strict]
  --strict also fails on SHA mismatch (default: symbol checks fail, SHA warns)
  Root resolution order: --isaac-root > env RL_ISAAC_ROOT > repo location
  > venv python location (run_offline_checks.bat sets both env var and venv).
"""
import argparse
import pathlib
import re
import subprocess
import sys

PINNED_SHA = "28a37cecdd433c22d9eabd6a5954add9f13a8951"
PINNED_DESC = "perf-2026-06-24 (tested 2026-08-31)"

# (file under <root>, regex, who depends on it)
NEEDLES = [
    ("source/isaaclab/isaaclab/managers/manager_base.py",
     r"term_cfg\.func = term_cfg\.func\(cfg=term_cfg",
     "staged_curriculum._dependency_met (curriculum term cross-reference)"),
    ("source/isaaclab/isaaclab/sensors/ray_caster/base_ray_caster.py",
     r"meshes: ClassVar",
     "teacher_mdp.FootContactNormalsTerm (global wp mesh registry)"),
    ("source/isaaclab/isaaclab/utils/warp/kernels.py",
     r"def raycast_mesh_masked_kernel",
     "teacher_mdp.FootContactNormalsTerm (terrain normal raycast)"),
    ("source/isaaclab/isaaclab/assets/articulation/base_articulation_data.py",
     r"def joint_stiffness",
     "metrics.step_energy (live PD gains readback)"),
    ("source/isaaclab/isaaclab/assets/articulation/base_articulation_data.py",
     r"def joint_damping",
     "metrics.step_energy (live PD gains readback)"),
    ("source/isaaclab/isaaclab/assets/articulation/base_articulation.py",
     r"def write_root_velocity_to_sim",
     "recovery.apply_kick (velocity kick)"),
    ("source/isaaclab/isaaclab/envs/manager_based_env_cfg.py",
     r"seed: int \| None",
     "eval.py env_cfg.seed pinning"),
    ("source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py",
     r"height_scanner\.update_period = self\.decimation \* self\.sim\.dt",
     "family/teacher scanner cadence contract (50 Hz policy rate)"),
]


def detect_root(cli: str | None) -> pathlib.Path | None:
    candidates = []
    if cli:
        candidates.append(pathlib.Path(cli))
    if root := __import__("os").environ.get("RL_ISAAC_ROOT"):
        candidates.append(pathlib.Path(root))
    # absolute() on purpose: keeps a junction path (E:\IsaacLab\rl_exp\...)
    # instead of resolving to the real repo, so parents[3] is the IsaacLab root
    here = pathlib.Path(__file__).absolute()
    candidates.append(here.parents[3] if len(here.parents) > 3 else None)
    # venv sibling of the IsaacLab root: <ROOT>/env_isaaclab/Scripts/python.exe
    exe = pathlib.Path(sys.executable)
    candidates.append(exe.parents[2] if len(exe.parents) > 2 else None)
    for cand in candidates:
        if cand is not None and (cand / "source" / "isaaclab").is_dir():
            return cand
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--isaac-root", default=None)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = detect_root(args.isaac_root)
    if root is None:
        print("FAIL: IsaacLab root not found (pass --isaac-root; auto-detect only "
              "works via the IsaacLab junction layout)")
        return 1
    print(f"IsaacLab root: {root}")

    failures = []
    for rel, pattern, user in NEEDLES:
        path = root / rel
        if not path.is_file():
            failures.append(f"{rel}: file gone ({user})")
            continue
        if not re.search(pattern, path.read_text(encoding="utf-8", errors="replace"), re.M):
            failures.append(f"{rel}: pattern '{pattern}' no longer present ({user})")

    try:
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""
    if not sha:
        print(f"WARN: cannot read IsaacLab git SHA (pin {PINNED_SHA[:12]} unverifiable)")
    elif sha == PINNED_SHA:
        print(f"ISAAC_SHA_MATCH {sha[:12]} ({PINNED_DESC})")
    else:
        msg = (f"ISAAC_SHA_DIFF {sha[:12]} != pinned {PINNED_SHA[:12]} -- "
               "re-run the smoke chain before trusting results")
        print(("FAIL: " if args.strict else "WARN: ") + msg)
        if args.strict:
            failures.append(msg)

    for f in failures:
        print(f"FAIL: {f}")
    if failures:
        print(f"PIN_CHECK_FAILED ({len(failures)}) -- framework moved under us; "
              "fix the dependents or re-pin after a full verification pass")
        return 1
    print("PIN_CHECK_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
