# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Machine-local host paths: the IsaacLab tree and the interpreter that runs it.

Two questions every entry point used to answer for itself with its own
hardcoding: where is ``<ROOT>`` (the IsaacLab source tree, which owns
``scripts/`` and ``logs/``) and which python owns ``isaaclab``/``rsl_rl``.
``paths.yaml`` in the repo root -- a copy of ``paths.example.yaml``, kept out of
git -- is the record; ``RL_ISAAC_ROOT``/``RL_PYTHON`` override it for one shell.

Stdlib only and no ``rl_exp`` import: the scheduler can be launched by a plain
interpreter precisely to be told where the venv is, so the answer must not
require the venv.

Usage:
    python ablation_harness/host_paths.py --root      # IsaacLab tree only
    python ablation_harness/host_paths.py --python    # venv interpreter only
    python ablation_harness/host_paths.py --check     # both, plus the config state

Exit code is 1 when a requested value is missing, so shell callers can branch.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys

_HARNESS_DIR = pathlib.Path(__file__).absolute().parent
REPO_ROOT = _HARNESS_DIR.parent
CONFIG_PATH = REPO_ROOT / "paths.yaml"
# a directory holding this is an IsaacLab source tree
_ISAAC_MARKER = pathlib.Path("source", "isaaclab")
# conventional venv layouts tried under a discovered root, in order
_VENVS = (pathlib.Path("env_isaaclab", "Scripts", "python.exe"),
          pathlib.Path("env_isaaclab", "bin", "python"))


def _config_values() -> dict[str, str]:
    """``paths.yaml`` as a flat mapping, ``{}`` when absent or unreadable.

    Hand-parsed on purpose: a bootstrap shell asks this module for a python
    before anyone knows whether PyYAML is installed in the interpreter running
    it. Nested maps and blank lines are skipped -- host paths are flat.
    """
    values: dict[str, str] = {}
    try:
        raw = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in raw.splitlines():
        if not line.strip() or line[0] in (" ", "\t", "#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and value:
            values[key] = value.replace("\\", "/")
    return values


def _claimed(kind: str, stated: list[str | None]) -> list[str]:
    """Stated values of one kind, warning about any that name nothing on disk."""
    kept = [c for c in stated if c]
    for cand in kept:
        if not pathlib.Path(cand).is_dir() and not pathlib.Path(cand).is_file():
            print(f"[host_paths] WARN: paths.yaml/env names a missing {kind}: {cand}",
                  file=sys.stderr)
    return kept


def isaac_root(override: str | None = None) -> pathlib.Path | None:
    """IsaacLab source tree, or None when no source names a usable one.

    Order: explicit ``override``, ``RL_ISAAC_ROOT``, ``paths.yaml``
    ``isaac_root``, then the nearest ancestor of the working directory holding
    ``source/isaaclab``. A stated root without that marker is rejected loudly
    rather than probed around, so a typo cannot silently point training at a
    different tree.
    """
    stated = _claimed("isaac_root", [override, os.environ.get("RL_ISAAC_ROOT"),
                                     _config_values().get("isaac_root")])
    for cand in stated:
        root = pathlib.Path(cand)
        if (root / _ISAAC_MARKER).is_dir():
            return root
        print(f"[host_paths] WARN: '{root}' has no {pathlib.Path(_ISAAC_MARKER)} -- ignored",
              file=sys.stderr)
    cwd = pathlib.Path.cwd()
    for root in (cwd, *cwd.parents):
        if (root / _ISAAC_MARKER).is_dir():
            return root
    return None


def venv_python(root: pathlib.Path | None = None, override: str | None = None) -> str | None:
    """Interpreter owning the IsaacLab stack, or None when none is found.

    Order: explicit ``override``, ``RL_PYTHON``, ``paths.yaml`` ``python``, then
    the conventional ``env_isaaclab`` venv under ``root``. Deliberately no
    ``PATH`` fallback: a system python missing ``isaaclab`` fails later with a
    confusing ImportError, so an unanswered question stays visible here.
    """
    stated = _claimed("python", [override, os.environ.get("RL_PYTHON"),
                                 _config_values().get("python")])
    for cand in stated:
        if pathlib.Path(cand).is_file():
            return str(pathlib.Path(cand))
    root = isaac_root() if root is None else root
    if root is not None:
        for layout in _VENVS:
            if (root / layout).is_file():
                return str(root / layout)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Report the machine-local IsaacLab paths.")
    parser.add_argument("--root", action="store_true", help="print only the IsaacLab tree")
    parser.add_argument("--python", action="store_true", help="print only the venv interpreter")
    parser.add_argument("--check", action="store_true", help="print both plus the config state")
    args = parser.parse_args()

    root, python = isaac_root(), venv_python()
    if args.root or args.python:
        want = root if args.root else pathlib.Path(python) if python else None
        print(want if want else "")
        return 0 if want else 1
    print(f"isaac_root: {root or 'NOT FOUND'}")
    print(f"python:     {python or 'NOT FOUND'}")
    print(f"config:     {CONFIG_PATH}"
          + (" (present)" if CONFIG_PATH.is_file()
             else " (absent -- copy paths.example.yaml, or set RL_ISAAC_ROOT/RL_PYTHON)"))
    print(f"cwd python: {shutil.which('python')}")
    return 0 if (root and python) else 1


if __name__ == "__main__":
    sys.exit(main())
